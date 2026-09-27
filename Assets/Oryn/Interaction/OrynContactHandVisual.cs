using System.Collections.Generic;
using UnityEngine;

namespace Oryn.Interaction
{
    // Render-only bone hierarchy. NEVER changes the provider's skeleton, finger
    // strengths, or tracking transforms. Deliberately bounded: not force feedback.
    public sealed class OrynContactHandVisual
    {
        private readonly OVRHand hand;
        private readonly OVRSkeleton skeleton;
        private readonly Transform owner;
        private readonly Dictionary<Transform, Transform> proxies = new Dictionary<Transform, Transform>();
        private readonly List<Transform> roots = new List<Transform>();
        private readonly Transform[] tips = new Transform[5];
        private SkinnedMeshRenderer renderer;
        private Transform[] originalBones, renderBones;
        private Transform originalRoot, proxyRoot, palm;
        private int skeletonVersion;
        private Vector3 palmOffset;
        private readonly Quaternion[] startRotations = new Quaternion[3];
        private readonly Transform[] joints = new Transform[3];
        public OrynContactHandVisual(OVRHand hand, OVRSkeleton skeleton, Transform owner)
        { this.hand = hand; this.skeleton = skeleton; this.owner = owner; }

        public void Update(bool valid, Collider surface)
        {
            if (!valid) { Restore(); return; }
            if (proxyRoot != null && skeletonVersion != skeleton.SkeletonChangedCount) Dispose();
            if (proxyRoot == null && !Initialize()) return;
            foreach (var pair in proxies)
            {
                if (proxies.ContainsKey(pair.Key.parent))
                { pair.Value.localPosition = pair.Key.localPosition; pair.Value.localRotation = pair.Key.localRotation; pair.Value.localScale = pair.Key.localScale; }
                else
                { pair.Value.SetPositionAndRotation(pair.Key.position, pair.Key.rotation); pair.Value.localScale = pair.Key.lossyScale; }
            }
            renderer.bones = renderBones;
            renderer.rootBone = originalRoot != null && proxies.TryGetValue(originalRoot, out Transform root) ? root : originalRoot;
            Vector3 correction = Vector3.zero;
            if (surface != null && palm != null && OrynSurfaceContact.Query(surface, palm.position, out _, out Vector3 palmNormal, out float depth) && depth < 0.018f)
                correction = palmNormal * Mathf.Clamp(0.018f - depth, 0, 0.035f);
            palmOffset = Vector3.Lerp(palmOffset, correction, 1f - Mathf.Exp(-Time.unscaledDeltaTime / 0.035f));
            foreach (Transform rootBone in roots) rootBone.position += palmOffset;
            if (surface == null) return;
            for (int finger = 0; finger < tips.Length; finger++)
            {
                Transform tip = tips[finger];
                if (tip == null || hand.GetFingerConfidence((OVRHand.HandFinger)finger) != OVRHand.TrackingConfidence.High) continue;
                if (!OrynSurfaceContact.Query(surface, tip.position, out Vector3 point, out Vector3 normal, out float distance) || distance >= 0.008f) continue;
                // Preserve bone lengths and keep correction close to the real pose.
                Vector3 target = Vector3.MoveTowards(tip.position, point + normal * 0.008f, 0.045f);
                SolveFinger(tip, target, joints, startRotations);
            }
        }

        // Small CCD solve; 3 finger joints, no wrist rotation or bone stretching.
        public static void SolveFinger(Transform tip, Vector3 target, Transform[] joints, Quaternion[] startRotations)
        {
            Transform joint = tip.parent;
            int count = 0;
            while (joint != null && count < 3)
            { joints[count] = joint; startRotations[count] = joint.localRotation; joint = joint.parent; count++; }
            for (int iteration = 0; iteration < 5; iteration++)
            for (int i = 0; i < count; i++)
            {
                joint = joints[i];
                Vector3 from = tip.position - joint.position, to = target - joint.position;
                if (from.sqrMagnitude < 0.00000001f || to.sqrMagnitude < 0.00000001f) continue;
                joint.rotation = Quaternion.FromToRotation(from, to) * joint.rotation;
                joint.localRotation = Quaternion.RotateTowards(startRotations[i], joint.localRotation, 35f);
            }
        }

        private bool Initialize()
        {
            renderer = hand.GetComponent<SkinnedMeshRenderer>();
            if (renderer == null || renderer.sharedMesh == null || renderer.bones.Length == 0 || !skeleton.IsInitialized) return false;
            originalBones = renderer.bones; originalRoot = renderer.rootBone;
            skeletonVersion = skeleton.SkeletonChangedCount;
            proxyRoot = new GameObject(hand.name + " Contact Visual Bones").transform;
            proxyRoot.SetParent(owner, false);
            foreach (OVRBone bone in skeleton.Bones)
                proxies.Add(bone.Transform, new GameObject(bone.Transform.name + " Visual").transform);
            foreach (var pair in proxies)
            {
                bool hasParent = proxies.TryGetValue(pair.Key.parent, out Transform parent);
                pair.Value.SetParent(hasParent ? parent : proxyRoot, false);
                if (!hasParent) roots.Add(pair.Value);
            }
            renderBones = new Transform[originalBones.Length];
            for (int i = 0; i < originalBones.Length; i++)
            {
                if (!proxies.TryGetValue(originalBones[i], out renderBones[i])) { Dispose(); return false; }
            }
            bool xr = skeleton.GetSkeletonType() == OVRSkeleton.SkeletonType.XRHandLeft || skeleton.GetSkeletonType() == OVRSkeleton.SkeletonType.XRHandRight;
            var ids = xr ? new[] { OVRSkeleton.BoneId.XRHand_ThumbTip, OVRSkeleton.BoneId.XRHand_IndexTip, OVRSkeleton.BoneId.XRHand_MiddleTip, OVRSkeleton.BoneId.XRHand_RingTip, OVRSkeleton.BoneId.XRHand_LittleTip } :
                new[] { OVRSkeleton.BoneId.Hand_ThumbTip, OVRSkeleton.BoneId.Hand_IndexTip, OVRSkeleton.BoneId.Hand_MiddleTip, OVRSkeleton.BoneId.Hand_RingTip, OVRSkeleton.BoneId.Hand_PinkyTip };
            foreach (OVRBone bone in skeleton.Bones)
            {
                for (int f = 0; f < 5; f++) if (bone.Id == ids[f]) tips[f] = proxies[bone.Transform];
                if (bone.Id == (xr ? OVRSkeleton.BoneId.XRHand_Palm : OVRSkeleton.BoneId.Hand_Middle1)) palm = proxies[bone.Transform];
            }
            Debug.Log("ORYN_CONTACT_VISUAL_READY hand=" + hand.name + " bones=" + renderBones.Length);
            return true;
        }
        public void Restore()
        {
            // A provider skeleton rebuild can have already installed NEW bones.
            // Do not replace those with our stale saved binding.
            if (renderer != null && originalBones != null && renderBones != null)
            {
                var current = renderer.bones;
                if (current.Length > 0 && current[0] == renderBones[0])
                { renderer.bones = originalBones; renderer.rootBone = originalRoot; }
            }
            palmOffset = Vector3.zero;
        }
        public void Dispose()
        {
            Restore();
            if (proxyRoot != null) Object.Destroy(proxyRoot.gameObject);
            proxyRoot = null; palm = null; originalBones = renderBones = null;
            proxies.Clear(); roots.Clear();
            for (int i = 0; i < tips.Length; i++) tips[i] = null;
        }
    }
}
