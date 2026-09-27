using UnityEngine;

namespace Oryn.Interaction
{
    // Shared input sampling for workspace manipulation and its physical panel.
    public sealed class OrynTrackedInput
    {
        public readonly bool[] Valid = new bool[4];
        public readonly float[] Strength = new float[4];
        public readonly Pose[] Poses = new Pose[4];
        public readonly OrynGesture[] Gestures = new OrynGesture[4];
        public readonly Vector3[] AimPoints = new Vector3[4];
        public readonly OrynPalmSample[] Palms = new OrynPalmSample[2];
        // Thumb, index, middle, ring, little, palm. Raw tracking only: visual
        // contact constraints must never feed back into gesture/input sampling.
        public readonly Vector3[][] Contacts = { new Vector3[6], new Vector3[6] };
        public readonly bool[][] ContactValid = { new bool[6], new bool[6] };
        private readonly OrynGestureClassifier[] classifiers = { new OrynGestureClassifier(), new OrynGestureClassifier() };
        private readonly float[][] fingers = { new float[4], new float[4] };
        private readonly bool[][] confidence = { new bool[4], new bool[4] };
        private readonly bool[] controllerGrip = new bool[2];
        private readonly bool[] controllerPinch = new bool[2];
        public void Read(OVRCameraRig rig, OVRHand left, OVRHand right, OVRSkeleton leftSkeleton, OVRSkeleton rightSkeleton, bool focused)
        {
            Controller(0, rig, OVRInput.Controller.LTouch, OVRInput.Handedness.LeftHanded, focused);
            Controller(1, rig, OVRInput.Controller.RTouch, OVRInput.Handedness.RightHanded, focused);
            Hand(2, left, leftSkeleton, OVRInput.Handedness.LeftHanded, focused);
            Hand(3, right, rightSkeleton, OVRInput.Handedness.RightHanded, focused);
        }
        private void Controller(int id, OVRCameraRig rig, OVRInput.Controller controller, OVRInput.Handedness side, bool focused)
        {
            Valid[id] = focused && OVRInput.GetActiveControllerForHand(side) == controller &&
                OVRInput.GetControllerPositionTracked(controller) && OVRInput.GetControllerOrientationTracked(controller);
            if (!Valid[id]) { Gestures[id] = OrynGesture.None; controllerGrip[id] = controllerPinch[id] = false; return; }
            Poses[id] = new Pose(rig.trackingSpace.TransformPoint(OVRInput.GetLocalControllerPosition(controller)),
                rig.trackingSpace.rotation * OVRInput.GetLocalControllerRotation(controller));
            AimPoints[id] = Poses[id].position;
            float grip = OVRInput.Get(OVRInput.Axis1D.PrimaryHandTrigger, controller);
            float trigger = OVRInput.Get(OVRInput.Axis1D.PrimaryIndexTrigger, controller);
            if (grip >= 0.7f) controllerGrip[id] = true; else if (grip <= 0.35f) controllerGrip[id] = false;
            if (trigger >= 0.7f) controllerPinch[id] = true; else if (trigger <= 0.35f) controllerPinch[id] = false;
            Gestures[id] = controllerGrip[id] ? OrynGesture.Manipulate : controllerPinch[id] ? OrynGesture.Resize : OrynGesture.None;
            Strength[id] = Mathf.Max(grip, trigger);
        }
        private void Hand(int id, OVRHand hand, OVRSkeleton skeleton, OVRInput.Handedness side, bool focused)
        {
            OVRInput.Controller active = OVRInput.GetActiveControllerForHand(side);
            bool controllerActive = active == OVRInput.Controller.LTouch || active == OVRInput.Controller.RTouch;
            Valid[id] = focused && !controllerActive && hand.IsTracked && hand.IsDataValid && hand.IsDataHighConfidence &&
                !hand.IsSystemGestureInProgress && skeleton.IsInitialized && skeleton.IsDataValid && skeleton.IsDataHighConfidence &&
                hand.GetFingerConfidence(OVRHand.HandFinger.Thumb) == OVRHand.TrackingConfidence.High;
            int index = id - 2;
            Palms[index] = default;
            for (int n = 0; n < 6; n++) ContactValid[index][n] = false;
            if (!Valid[id]) { classifiers[index].Clear(); Gestures[id] = OrynGesture.None; return; }
            float strongest = 0f;
            for (int finger = 0; finger < 4; finger++)
            {
                var fingerId = (OVRHand.HandFinger)(finger + 1);
                confidence[index][finger] = hand.GetFingerConfidence(fingerId) == OVRHand.TrackingConfidence.High;
                fingers[index][finger] = hand.GetFingerPinchStrength(fingerId);
                if (confidence[index][finger]) strongest = Mathf.Max(strongest, fingers[index][finger]);
            }
            Gestures[id] = classifiers[index].Sample(fingers[index], confidence[index], Time.unscaledDeltaTime);
            Strength[id] = strongest;
            bool xr = skeleton.GetSkeletonType() == OVRSkeleton.SkeletonType.XRHandLeft || skeleton.GetSkeletonType() == OVRSkeleton.SkeletonType.XRHandRight;
            var thumbId = xr ? OVRSkeleton.BoneId.XRHand_ThumbTip : OVRSkeleton.BoneId.Hand_ThumbTip;
            Transform thumb = null, indexTip = null, wrist = null, knuckle = null, indexBase = null, littleBase = null;
            Vector3 activeTips = Vector3.zero;
            int activeCount = 0;
            foreach (OVRBone bone in skeleton.Bones)
            {
                if (bone.Id == thumbId) thumb = bone.Transform;
                if (bone.Id == (xr ? OVRSkeleton.BoneId.XRHand_Wrist : OVRSkeleton.BoneId.Hand_WristRoot)) wrist = bone.Transform;
                if (bone.Id == (xr ? OVRSkeleton.BoneId.XRHand_MiddleProximal : OVRSkeleton.BoneId.Hand_Middle1)) knuckle = bone.Transform;
                if (bone.Id == (xr ? OVRSkeleton.BoneId.XRHand_IndexProximal : OVRSkeleton.BoneId.Hand_Index1)) indexBase = bone.Transform;
                if (bone.Id == (xr ? OVRSkeleton.BoneId.XRHand_LittleProximal : OVRSkeleton.BoneId.Hand_Pinky1)) littleBase = bone.Transform;
                int finger = FingerIndex(bone.Id, xr);
                if (finger == 0) indexTip = bone.Transform;
                if (finger >= 0)
                { Contacts[index][finger + 1] = bone.Transform.position; ContactValid[index][finger + 1] = confidence[index][finger]; }
                if (finger >= 0 && confidence[index][finger] && fingers[index][finger] > 0.35f)
                { activeTips += bone.Transform.position; activeCount++; }
            }
            Valid[id] = thumb != null && indexTip != null;
            if (!Valid[id]) return;
            Contacts[index][0] = thumb.position; ContactValid[index][0] = true;
            Vector3 palm = wrist != null && knuckle != null ? Vector3.Lerp(wrist.position, knuckle.position, 0.55f) : hand.transform.position;
            Contacts[index][5] = palm; ContactValid[index][5] = wrist != null && knuckle != null;
            Vector3 point = Gestures[id] == OrynGesture.Manipulate && activeCount >= 2
                ? (thumb.position + activeTips) / (activeCount + 1) : (thumb.position + indexTip.position) * 0.5f;
            AimPoints[id] = point;
            // A stable palm origin avoids jumps as additional fingertips join.
            Poses[id] = new Pose(palm, hand.transform.rotation);
            if (wrist != null && knuckle != null && indexBase != null && littleBase != null && ContactValid[index][1] && ContactValid[index][2])
                Palms[index] = OrynPrayerSpread.FromBones(Valid[id], index == 0, wrist.position, knuckle.position,
                    indexBase.position, littleBase.position, Contacts[index][1], Contacts[index][2], strongest);
        }
        private static int FingerIndex(OVRSkeleton.BoneId bone, bool xr)
        {
            if (bone == (xr ? OVRSkeleton.BoneId.XRHand_IndexTip : OVRSkeleton.BoneId.Hand_IndexTip)) return 0;
            if (bone == (xr ? OVRSkeleton.BoneId.XRHand_MiddleTip : OVRSkeleton.BoneId.Hand_MiddleTip)) return 1;
            if (bone == (xr ? OVRSkeleton.BoneId.XRHand_RingTip : OVRSkeleton.BoneId.Hand_RingTip)) return 2;
            if (bone == (xr ? OVRSkeleton.BoneId.XRHand_LittleTip : OVRSkeleton.BoneId.Hand_PinkyTip)) return 3;
            return -1;
        }
    }
}
