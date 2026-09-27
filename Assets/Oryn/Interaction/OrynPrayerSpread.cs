using UnityEngine;

namespace Oryn.Interaction
{
    public struct OrynPalmSample
    {
        public bool Valid, Open;
        public Vector3 Position, Normal, Fingers;
    }

    // Pure recognizer; no scene mutation, SDK poses, or pinch-resize math here.
    public sealed class OrynPrayerSpread
    {
        public const float ArmSpan = 0.16f, ArmSeconds = 0.28f, MaximumSpan = 0.65f;
        public bool Active { get; private set; }
        public bool Started { get; private set; }
        public float Amount { get; private set; }
        public float ArmProgress => held / ArmSeconds;
        public bool ConsumesHands => Active || held > 0;
        private float held, startSpan;

        public void Reset() { Active = Started = false; held = 0; }

        public static OrynPalmSample FromBones(bool tracked, bool left, Vector3 wrist, Vector3 middleBase,
            Vector3 indexBase, Vector3 littleBase, Vector3 indexTip, Vector3 middleTip, float pinch)
        {
            Vector3 forward = middleBase - wrist, across = indexBase - littleBase;
            Vector3 normal = Vector3.Cross(forward, across) * (left ? -1f : 1f);
            bool geometry = forward.magnitude > 0.02f && across.magnitude > 0.02f && normal.sqrMagnitude > 0.00000001f;
            bool straight = Vector3.Dot((indexTip - indexBase).normalized, forward.normalized) > 0.65f &&
                Vector3.Dot((middleTip - middleBase).normalized, forward.normalized) > 0.65f &&
                Vector3.Distance(indexTip, wrist) > Vector3.Distance(indexBase, wrist) * 1.35f &&
                Vector3.Distance(middleTip, wrist) > forward.magnitude * 1.35f;
            return new OrynPalmSample { Valid = tracked && geometry, Open = straight && pinch < 0.4f,
                Position = Vector3.Lerp(wrist, middleBase, 0.55f), Normal = normal.normalized, Fingers = forward.normalized };
        }

        public void Sample(OrynPalmSample left, OrynPalmSample right, bool eligible, float seconds)
        {
            Started = false;
            if (!float.IsFinite(seconds)) { Reset(); return; }
            float dt = Mathf.Clamp(seconds, 0, 0.05f);
            Vector3 line = right.Position - left.Position;
            float span = line.magnitude;
            bool facing = left.Valid && right.Valid && left.Open && right.Open && float.IsFinite(span) &&
                span >= 0.015f && span <= 1.3f &&
                Vector3.Dot(left.Normal, line.normalized) > 0.45f && Vector3.Dot(right.Normal, -line.normalized) > 0.45f &&
                Vector3.Dot(left.Normal, right.Normal) < -0.45f;
            if (!eligible || !facing) { Reset(); return; } // Freeze on loss; fresh prayer required to resume.
            if (!Active)
            {
                bool prayer = span <= ArmSpan && Vector3.Dot(left.Fingers, right.Fingers) > 0.7f &&
                    Vector3.Dot(left.Fingers, Vector3.up) > 0.4f && Vector3.Dot(right.Fingers, Vector3.up) > 0.4f;
                if (!prayer) { held = 0; return; }
                held = Mathf.Min(ArmSeconds, held + dt);
                if (held < ArmSeconds) return;
                Active = Started = true;
                Amount = 0;
                startSpan = Mathf.Max(0.08f, span);
                return;
            }
            float target = Mathf.InverseLerp(startSpan, MaximumSpan, span);
            Amount = Mathf.Clamp01(Mathf.Lerp(Amount, target, 1f - Mathf.Exp(-dt / 0.07f)));
            if (target == 0 && Amount < 0.015f) Amount = 0;
        }
    }
}
