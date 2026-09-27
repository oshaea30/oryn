using UnityEngine;

namespace Oryn.Interaction
{
    // Device-independent single-owner manipulation. The adapters supply only poses and intent.
    public sealed class OrynGrabState
    {
        public const int SourceCount = 4; // Left/right controller, left/right hand.
        public const float BeginThreshold = 0.7f;
        public const float EndThreshold = 0.35f;
        private readonly bool[] armed = new bool[SourceCount];
        private Vector3 offsetPosition;
        private Quaternion offsetRotation;

        public int Owner { get; private set; } = -1;
        public Pose ObjectPose { get; private set; }

        public OrynGrabState(Pose initialPose) { Reset(initialPose); }

        public void Reset(Pose pose)
        {
            ReleaseAll();
            ObjectPose = pose;
        }

        public void ReleaseAll()
        {
            Owner = -1;
            for (int i = 0; i < armed.Length; i++) armed[i] = false;
        }

        public void UpdateInput(int source, bool valid, float strength, Pose grip, bool near)
        {
            if (source < 0 || source >= SourceCount) throw new System.ArgumentOutOfRangeException(nameof(source));
            if (!valid)
            {
                if (Owner == source) Owner = -1;
                armed[source] = false;
                return;
            }
            if (strength <= EndThreshold)
            {
                if (Owner == source) Owner = -1;
                armed[source] = true;
                return;
            }
            if (Owner == source)
            {
                ObjectPose = new Pose(grip.position + grip.rotation * offsetPosition,
                    grip.rotation * offsetRotation);
                return;
            }
            if (strength < BeginThreshold || !armed[source]) return;
            armed[source] = false;
            if (Owner != -1 || !near) return;
            Owner = source;
            offsetPosition = Quaternion.Inverse(grip.rotation) * (ObjectPose.position - grip.position);
            offsetRotation = Quaternion.Inverse(grip.rotation) * ObjectPose.rotation;
        }
    }
}
