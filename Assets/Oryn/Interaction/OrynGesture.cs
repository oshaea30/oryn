using UnityEngine;

namespace Oryn.Interaction
{
    public enum OrynGesture { None, Resize, Manipulate, Uncertain }

    // Thumb + one fingertip = two fingers. Thumb + two or more = manipulation.
    public sealed class OrynGestureClassifier
    {
        private readonly bool[] pinching = new bool[4];
        public OrynGesture Current { get; private set; }
        private OrynGesture candidate;
        private float candidateTime;
        public void Clear()
        {
            for (int i = 0; i < 4; i++) pinching[i] = false;
            Current = candidate = OrynGesture.None;
            candidateTime = 0;
        }
        public OrynGesture Sample(float[] strengths, bool[] confidence, float seconds)
        {
            int count = 0;
            bool uncertain = false;
            for (int i = 0; i < 4; i++)
            {
                if (!confidence[i]) { uncertain = true; continue; }
                if (strengths[i] >= 0.7f) pinching[i] = true;
                else if (strengths[i] <= 0.35f) pinching[i] = false;
                if (pinching[i]) count++;
            }
            OrynGesture next = count >= 2 ? OrynGesture.Manipulate : uncertain ? OrynGesture.Uncertain :
                pinching[0] ? OrynGesture.Resize : OrynGesture.None;
            // Never infer "only two fingers" when additional fingers cannot be observed.
            if (next == OrynGesture.Uncertain) { Current = next; candidateTime = 0; candidate = next; return Current; }
            if (next != candidate) { candidate = next; candidateTime = 0; }
            candidateTime += Mathf.Max(0, seconds);
            float settle = next == OrynGesture.Resize ? 0.15f : 0.08f;
            if (next == OrynGesture.None || candidateTime >= settle) Current = next;
            else if (Current != next) Current = OrynGesture.Uncertain;
            return Current;
        }
    }
}
