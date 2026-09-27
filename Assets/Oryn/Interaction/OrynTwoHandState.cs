using UnityEngine;

namespace Oryn.Interaction
{
    // One atomic pose update per frame; input adapters and scene objects do not own the math.
    public sealed class OrynTwoHandState
    {
        public const float MinimumSpan = 0.06f;
        public const float MinimumScale = 0.25f;
        public const float MaximumScale = 3f;
        public int Primary { get; private set; } = -1;
        public int Secondary { get; private set; } = -1;
        public int HoldCount => Primary < 0 ? 0 : Secondary < 0 ? 1 : 2;
        public Pose ObjectPose { get; private set; }
        public float Scale { get; private set; } = 1f;
        public enum Operation { Released, Manipulate, Resize, Waiting }
        public Operation Mode { get; private set; }
        public const float ResizeDeadZone = 0.02f;
        private Vector3 localOffset;
        private Quaternion rotationOffset;
        private Vector3 startMidpoint;
        private Vector3 lastAxis;
        private Quaternion accumulatedRotation;
        private bool collapsed;
        private Pose startObject;
        private float startSpan;
        private float startScale;

        public OrynTwoHandState(Pose pose) { Reset(pose); }
        public bool IsHeldBy(int source) => source >= 0 && (Primary == source || Secondary == source);

        public bool Begin(int source, Pose[] grips, OrynGesture[] gestures = null, Vector3[] resizePoints = null)
        {
            if (source < 0 || source >= 4 || IsHeldBy(source) || HoldCount == 2) return false;
            // A tracked hand and its controller can never count as two different hands.
            if (Primary >= 0 && source % 2 == Primary % 2) return false;
            if (Primary < 0) { Primary = source; Rebase(grips, gestures, resizePoints); return true; }
            bool resizing = gestures != null && gestures[Primary] == OrynGesture.Resize && gestures[source] == OrynGesture.Resize;
            if (Vector3.Distance(resizing && resizePoints != null ? resizePoints[Primary] : grips[Primary].position,
                resizing && resizePoints != null ? resizePoints[source] : grips[source].position) < MinimumSpan) return false;
            Secondary = source;
            Rebase(grips, gestures, resizePoints);
            return true;
        }

        public void End(int source, Pose[] grips, OrynGesture[] gestures = null, Vector3[] resizePoints = null)
        {
            if (!IsHeldBy(source)) return;
            if (Primary == source) Primary = Secondary;
            Secondary = -1;
            Rebase(grips, gestures, resizePoints);
        }

        public void ReleaseAll() { Primary = Secondary = -1; Mode = Operation.Released; }
        public void Reset(Pose pose) { ReleaseAll(); ObjectPose = pose; Scale = 1f; }

        private void RebaseSingle(Pose grip)
        {
            localOffset = Quaternion.Inverse(grip.rotation) * (ObjectPose.position - grip.position);
            rotationOffset = Quaternion.Inverse(grip.rotation) * ObjectPose.rotation;
        }

        private Operation Resolve(OrynGesture[] gestures)
        {
            if (Primary < 0) return Operation.Released;
            OrynGesture first = gestures == null ? OrynGesture.Manipulate : gestures[Primary];
            if (Secondary < 0) return first == OrynGesture.Manipulate ? Operation.Manipulate : Operation.Waiting;
            OrynGesture second = gestures == null ? OrynGesture.Manipulate : gestures[Secondary];
            if (first == OrynGesture.Manipulate && second == first) return Operation.Manipulate;
            if (first == OrynGesture.Resize && second == first) return Operation.Resize;
            return Operation.Waiting;
        }
        private void Rebase(Pose[] grips, OrynGesture[] gestures, Vector3[] resizePoints = null)
        {
            Mode = Resolve(gestures);
            startObject = ObjectPose; startScale = Scale; accumulatedRotation = Quaternion.identity;
            collapsed = false;
            if (Primary < 0) return;
            RebaseSingle(grips[Primary]);
            if (Secondary < 0) return;
            startMidpoint = (grips[Primary].position + grips[Secondary].position) * 0.5f;
            Vector3 line = grips[Secondary].position - grips[Primary].position;
            if (Mode == Operation.Resize && resizePoints != null) line = resizePoints[Secondary] - resizePoints[Primary];
            startSpan = line.magnitude; lastAxis = line.normalized;
            collapsed = startSpan < MinimumSpan;
        }

        // Runtime supplies actual delta time; one second is convenient for deterministic pose tests.
        public void Step(Pose[] grips, OrynGesture[] gestures = null, float seconds = 1f, Vector3[] resizePoints = null)
        {
            if (Resolve(gestures) != Mode) { Rebase(grips, gestures, resizePoints); return; }
            if (Primary < 0 || Mode == Operation.Waiting || seconds <= 0) return;
            Pose a = grips[Primary];
            if (Secondary < 0)
            {
                Follow(new Pose(a.position + a.rotation * localOffset, a.rotation * rotationOffset), seconds);
                return;
            }
            Pose b = grips[Secondary];
            Vector3 line = b.position - a.position;
            if (Mode == Operation.Resize && resizePoints != null) line = resizePoints[Secondary] - resizePoints[Primary];
            float span = line.magnitude;
            if (span < MinimumSpan) { collapsed = true; return; }
            if (collapsed) { Rebase(grips, gestures, resizePoints); return; }
            if (Mode == Operation.Resize)
            {
                float difference = span - startSpan;
                float effectiveSpan = startSpan + Mathf.Sign(difference) * Mathf.Max(0, Mathf.Abs(difference) - ResizeDeadZone);
                float target = Mathf.Clamp(startScale * effectiveSpan / startSpan, MinimumScale, MaximumScale);
                Scale = Mathf.Lerp(Scale, target, 1f - Mathf.Exp(-seconds / 0.06f));
                return; // Resize stays centered and cannot rotate or translate the object.
            }
            Vector3 axis = line / span;
            float angle = Vector3.Angle(lastAxis, axis);
            if (angle > 100f) { Rebase(grips, gestures); return; } // Reject a tracking flip rather than teleporting.
            if (angle > 0.6f)
            {
                accumulatedRotation = Quaternion.FromToRotation(lastAxis, axis) * accumulatedRotation;
                lastAxis = axis;
            }
            Follow(new Pose(startObject.position + (a.position + b.position) * 0.5f - startMidpoint,
                accumulatedRotation * startObject.rotation), seconds);
        }
        private void Follow(Pose target, float seconds)
        {
            Vector3 filtered = Vector3.Lerp(ObjectPose.position, target.position, 1f - Mathf.Exp(-seconds / 0.045f));
            ObjectPose = new Pose(Vector3.MoveTowards(ObjectPose.position, filtered, 2f * seconds),
                Quaternion.RotateTowards(ObjectPose.rotation, target.rotation, 240f * seconds));
        }
    }

    public sealed class OrynPressLatch
    {
        private bool armed;
        public void Clear() { armed = false; }
        public bool Sample(bool valid, float strength)
        {
            if (!valid) { Clear(); return false; }
            if (strength <= OrynGrabState.EndThreshold) { armed = true; return false; }
            if (strength < OrynGrabState.BeginThreshold || !armed) return false;
            armed = false;
            return true;
        }
    }
}
