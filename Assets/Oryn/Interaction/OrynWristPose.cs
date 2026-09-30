using UnityEngine;

namespace Oryn.Interaction
{
    // Bone geometry, not thumb-to-finger pinch strength: a fist with the thumb out is not a pinch.
    public static class OrynWristPose
    {
        private static bool Finite(Vector3 p) => float.IsFinite(p.x) && float.IsFinite(p.y) && float.IsFinite(p.z);
        public static bool Matches(bool tracked, Vector3 wrist, Vector3 thumbBase, Vector3 thumbJoint, Vector3 thumbTip,
            Vector3[] bases, Vector3[] joints, Vector3[] tips, bool[] confident)
        {
            if (!tracked || bases == null || joints == null || tips == null || confident == null ||
                bases.Length != 4 || joints.Length != 4 || tips.Length != 4 || confident.Length != 4) return false;
            if (!Finite(wrist) || !Finite(thumbBase) || !Finite(thumbJoint) || !Finite(thumbTip)) return false;
            for (int i=0;i<4;i++) if (!Finite(bases[i]) || !Finite(joints[i]) || !Finite(tips[i])) return false;
            Vector3 forward = bases[1] - wrist, outward = bases[0] - bases[3];
            float scale = forward.magnitude / 0.08f;
            if (scale < 0.4f || scale > 2 || outward.magnitude < 0.025f * scale) return false;
            for (int i = 0; i < 4; i++)
            {
                Vector3 first = joints[i] - bases[i], last = tips[i] - joints[i];
                if (!confident[i] || first.magnitude < 0.008f * scale || last.magnitude < 0.008f * scale ||
                    Vector3.Dot(first.normalized, last.normalized) > 0.45f ||
                    Vector3.Dot(tips[i] - bases[i], forward.normalized) > 0.035f * scale) return false;
            }
            Vector3 thumbFirst = thumbJoint - thumbBase, thumbLast = thumbTip - thumbJoint;
            return thumbFirst.magnitude > 0.008f * scale && thumbLast.magnitude > 0.008f * scale &&
                Vector3.Dot(thumbFirst.normalized, thumbLast.normalized) > 0.65f &&
                Vector3.Dot((thumbTip - thumbBase).normalized, outward.normalized) > 0.45f &&
                Vector3.Distance(thumbTip, bases[0]) > 0.04f * scale;
        }
    }
}
