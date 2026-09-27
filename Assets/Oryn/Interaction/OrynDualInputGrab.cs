using UnityEngine;

namespace Oryn.Interaction
{
    [DefaultExecutionOrder(1000)]
    public sealed class OrynDualInputGrab : MonoBehaviour
    {
        public OVRCameraRig Rig;
        public Transform Cube;
        public OVRHand LeftHand;
        public OVRHand RightHand;
        public OVRSkeleton LeftSkeleton;
        public OVRSkeleton RightSkeleton;
        public Material GripMarkerMaterial;
        public Mesh GripMarkerMesh;
        public const float ReachMargin = 0.10f;

        private OrynGrabState state;
        private Collider cubeCollider;
        private Renderer cubeRenderer;
        private MaterialPropertyBlock colors;
        private readonly bool[] valid = new bool[4];
        private readonly float[] strength = new float[4];
        private readonly Pose[] poses = new Pose[4];
        private readonly Renderer[] cursors = new Renderer[4];
        private Material cursorMaterial;
        private bool placedAtStartup;
        private static readonly Color RestColor = new Color(0.05f, 0.65f, 1f);
        private static readonly Color HoverColor = new Color(0.1f, 1f, 0.75f);
        private static readonly Color HeldColor = new Color(1f, 0.72f, 0.12f);

        private void Awake()
        {
            state = new OrynGrabState(new Pose(Cube.position, Cube.rotation));
            cubeCollider = Cube.GetComponent<Collider>();
            cubeRenderer = Cube.GetComponent<Renderer>();
            colors = new MaterialPropertyBlock();
            cursorMaterial = new Material(GripMarkerMaterial);
            cursorMaterial.color = Color.white;
            for (int i = 0; i < cursors.Length; i++)
            {
                GameObject cursor = new GameObject("Oryn Grip Marker " + i, typeof(MeshFilter), typeof(MeshRenderer));
                cursor.GetComponent<MeshFilter>().sharedMesh = GripMarkerMesh;
                cursor.transform.SetParent(transform, false);
                cursor.transform.localScale = Vector3.one * 0.018f;
                cursors[i] = cursor.GetComponent<Renderer>();
                cursors[i].sharedMaterial = cursorMaterial;
                cursors[i].enabled = false;
            }
        }

        private void Start()
        {
            FindAnyObjectByType<Meta.XR.ImmersiveDebugger.UserInterface.DebugInterface>()?.Hide();
            Debug.Log("ORYN_M2_READY grip=controller_side_trigger hands=index_pinch release=hover");
        }

        private void LateUpdate()
        {
            bool focused = OVRManager.hasInputFocus && OVRManager.hasVrFocus;
            if (focused && !placedAtStartup && Rig.centerEyeAnchor.position.y > 0.1f)
            {
                ResetToReach();
                placedAtStartup = true;
            }
            ReadController(0, OVRInput.Controller.LTouch, OVRInput.Handedness.LeftHanded, focused);
            ReadController(1, OVRInput.Controller.RTouch, OVRInput.Handedness.RightHanded, focused);
            ReadHand(2, LeftHand, LeftSkeleton, OVRInput.Handedness.LeftHanded, focused);
            ReadHand(3, RightHand, RightSkeleton, OVRInput.Handedness.RightHanded, focused);

            // First invalidate lost sources so switching modes cannot keep a stale owner.
            for (int i = 0; i < 4; i++)
                if (!valid[i]) state.UpdateInput(i, false, 0, Pose.identity, false);
            bool hover = false;
            for (int i = 0; i < 4; i++)
            {
                bool near = valid[i] && IsNear(cubeCollider, poses[i].position);
                hover |= near;
                int previousOwner = state.Owner;
                if (valid[i]) state.UpdateInput(i, true, strength[i], poses[i], near);
                if (state.Owner != previousOwner)
                    Debug.Log("ORYN_M2_GRAB source=" + i + " owner=" + state.Owner);
                cursors[i].enabled = valid[i];
                if (valid[i]) cursors[i].transform.position = poses[i].position;
            }
            if (focused && ((valid[0] && OVRInput.GetDown(OVRInput.Button.Two, OVRInput.Controller.LTouch)) ||
                (valid[1] && OVRInput.GetDown(OVRInput.Button.Two, OVRInput.Controller.RTouch)))) ResetToReach();
            Cube.SetPositionAndRotation(state.ObjectPose.position, state.ObjectPose.rotation);
            colors.SetColor("_Color", state.Owner >= 0 ? HeldColor : hover ? HoverColor : RestColor);
            cubeRenderer.SetPropertyBlock(colors);
        }

        public static bool IsNear(Collider target, Vector3 point)
        {
            return (target.ClosestPoint(point) - point).sqrMagnitude <= ReachMargin * ReachMargin;
        }

        private void ReadController(int id, OVRInput.Controller controller, OVRInput.Handedness side, bool focused)
        {
            valid[id] = focused && OVRInput.GetActiveControllerForHand(side) == controller &&
                OVRInput.GetControllerPositionTracked(controller) && OVRInput.GetControllerOrientationTracked(controller);
            if (!valid[id]) return;
            // Query this device explicitly, rather than an anchor shared with hand tracking.
            poses[id] = new Pose(Rig.trackingSpace.TransformPoint(OVRInput.GetLocalControllerPosition(controller)),
                Rig.trackingSpace.rotation * OVRInput.GetLocalControllerRotation(controller));
            strength[id] = OVRInput.Get(OVRInput.Axis1D.PrimaryHandTrigger, controller);
        }

        private void ReadHand(int id, OVRHand hand, OVRSkeleton skeleton, OVRInput.Handedness side, bool focused)
        {
            OVRInput.Controller active = OVRInput.GetActiveControllerForHand(side);
            bool controllerActive = active == OVRInput.Controller.LTouch || active == OVRInput.Controller.RTouch;
            valid[id] = focused && !controllerActive && hand.IsTracked && hand.IsDataValid &&
                hand.IsDataHighConfidence && !hand.IsSystemGestureInProgress && skeleton.IsInitialized &&
                skeleton.IsDataValid && skeleton.IsDataHighConfidence &&
                hand.GetFingerConfidence(OVRHand.HandFinger.Index) == OVRHand.TrackingConfidence.High &&
                hand.GetFingerConfidence(OVRHand.HandFinger.Thumb) == OVRHand.TrackingConfidence.High;
            if (!valid[id]) return;
            Transform thumb = null, index = null;
            bool xr = skeleton.GetSkeletonType() == OVRSkeleton.SkeletonType.XRHandLeft ||
                skeleton.GetSkeletonType() == OVRSkeleton.SkeletonType.XRHandRight;
            var thumbId = xr ? OVRSkeleton.BoneId.XRHand_ThumbTip : OVRSkeleton.BoneId.Hand_ThumbTip;
            var indexId = xr ? OVRSkeleton.BoneId.XRHand_IndexTip : OVRSkeleton.BoneId.Hand_IndexTip;
            foreach (OVRBone bone in skeleton.Bones)
            {
                if (bone.Id == thumbId) thumb = bone.Transform;
                if (bone.Id == indexId) index = bone.Transform;
            }
            valid[id] = thumb != null && index != null;
            if (!valid[id]) return;
            poses[id] = new Pose((thumb.position + index.position) * 0.5f, hand.transform.rotation);
            strength[id] = hand.GetFingerPinchStrength(OVRHand.HandFinger.Index);
        }

        private void ResetToReach()
        {
            Transform head = Rig.centerEyeAnchor;
            Vector3 forward = Vector3.ProjectOnPlane(head.forward, Vector3.up).normalized;
            if (forward.sqrMagnitude < 0.01f) forward = Vector3.forward;
            Vector3 position = head.position + forward * 0.65f + Vector3.down * 0.25f;
            position.y = Mathf.Max(0.45f, position.y);
            state.Reset(new Pose(position, Quaternion.identity));
            Cube.SetPositionAndRotation(position, Quaternion.identity);
            Debug.Log("ORYN_M2_RESET");
        }

        private void OnDisable() { state?.ReleaseAll(); }
        private void OnApplicationPause(bool paused) { if (paused) state?.ReleaseAll(); }
        private void OnApplicationFocus(bool focused) { if (!focused) state?.ReleaseAll(); }
        private void OnDestroy() { if (cursorMaterial != null) Destroy(cursorMaterial); }
    }
}
