using System;
using Oryn.Interaction;
using UnityEngine;

namespace Oryn.Editor
{
    public static class OrynPrayerSpreadTests
    {
        private static int checks;
        private static OrynPalmSample Hand(bool left, float span) => new OrynPalmSample {
            Valid = true, Open = true, Position = new Vector3((left ? -1 : 1) * span / 2f, 1.2f, 0.5f),
            Normal = left ? Vector3.right : Vector3.left, Fingers = Vector3.up };
        private static void Frames(OrynPrayerSpread state, float span, int count, bool eligible = true)
        { for (int i = 0; i < count; i++) state.Sample(Hand(true, span), Hand(false, span), eligible, 1f / 60f); }
        private static OrynPrayerSpread Armed()
        { var state = new OrynPrayerSpread(); Frames(state, 0.10f, 20); Check(state.Active, "prayer dwell arms"); return state; }
        public static void Run()
        {
            checks = 0;
            var s = new OrynPrayerSpread();
            Frames(s, 0.10f, 5); Check(!s.Active && s.ConsumesHands, "brief prayer consumes input but cannot move model");
            Frames(s, 0.10f, 20); Check(s.Active && s.Amount == 0, "arm starts assembled");
            Frames(s, 0.375f, 60); Check(Mathf.Abs(s.Amount - 0.5f) < 0.005f, "half span gives half spread");
            Frames(s, 0.95f, 60); Check(s.Amount > 0.99f && s.Amount <= 1, "maximum spread clamped");
            Frames(s, 0.10f, 60); Check(s.Amount == 0, "hands together return fully assembled");
            s.Reset(); Frames(s, 0.4f, 100); Check(!s.Active && !s.ConsumesHands, "open hands apart do not trigger");
            Frames(s, 0.1f, 100, false); Check(!s.Active, "no eligible assembly or held object cannot arm");
            var a = Hand(true, .1f); var b = Hand(false, .1f);
            a.Open = false;
            for (int i = 0; i < 40; i++) s.Sample(a, b, true, 1f / 60f);
            Check(!s.Active, "pinch/curl excluded");
            a = Hand(true, .1f); a.Normal = Vector3.left;
            for (int i = 0; i < 40; i++) s.Sample(a, b, true, 1f / 60f);
            Check(!s.Active, "palms facing away cannot arm");
            a = Hand(true, .1f); a.Fingers = Vector3.down;
            for (int i = 0; i < 40; i++) s.Sample(a, b, true, 1f / 60f);
            Check(!s.Active, "opposed finger directions cannot arm");
            a = Hand(true, .1f); a.Valid = false;
            for (int i = 0; i < 40; i++) s.Sample(a, b, true, 1f / 60f);
            Check(!s.Active, "one lost hand cannot arm");
            s = Armed(); Frames(s, .4f, 60); float frozen = s.Amount;
            s.Sample(a, b, true, 1f / 60f);
            Check(!s.Active && s.Amount == frozen, "tracking loss freezes amount");
            Frames(s, .4f, 40); Check(!s.Active, "reacquired hands apart cannot silently resume");
            Frames(s, .1f, 20); Check(s.Active, "fresh prayer resumes deliberately");
            Frames(s, .4f, 30); s.Sample(Hand(true,.4f),Hand(false,.4f),false,1f/60f);
            Check(!s.Active, "eligibility loss ends control");
            s = Armed(); Frames(s, .4f, 30); a=Hand(true,.4f);a.Open=false;
            s.Sample(a,Hand(false,.4f),true,1f/60f);Check(!s.Active,"closing hand releases");
            s = Armed(); a=Hand(true,.4f);a.Normal=Vector3.back;
            s.Sample(a,Hand(false,.4f),true,1f/60f);Check(!s.Active,"turning palm releases");
            s = Armed(); a=Hand(true,.4f);a.Position=new Vector3(float.NaN,0,0);
            s.Sample(a,Hand(false,.4f),true,1f/60f);Check(!s.Active&&float.IsFinite(s.Amount),"invalid tracking rejected");
            s = Armed();Frames(s,1.4f,1);Check(!s.Active,"tracking jump outside plausible reach rejected");
            s = new OrynPrayerSpread();s.Sample(Hand(true,.1f),Hand(false,.1f),true,10);
            Check(!s.Active,"single stalled frame cannot arm");
            foreach (bool left in new[] { true, false })
            {
                Vector3 wrist=new Vector3(left?-.05f:.05f,1,0);
                var palm=OrynPrayerSpread.FromBones(true,left,wrist,wrist+Vector3.up*.08f,
                    wrist+new Vector3(0,.075f,-.03f),wrist+new Vector3(0,.07f,.03f),
                    wrist+new Vector3(0,.16f,-.03f),wrist+Vector3.up*.18f,0);
                Check(palm.Valid&&palm.Open,"open skeleton recognized");
                Check(Vector3.Dot(palm.Normal,left?Vector3.right:Vector3.left)>.99f,"left/right palm normals face inward");
                palm=OrynPrayerSpread.FromBones(true,left,wrist,wrist+Vector3.up*.08f,
                    wrist+new Vector3(0,.075f,-.03f),wrist+new Vector3(0,.07f,.03f),
                    wrist+new Vector3(0,.16f,-.03f),wrist+Vector3.up*.18f,.8f);
                Check(!palm.Open,"pinch strength excludes open-palm gesture");
            }
            Debug.Log("ORYN_PRAYER_TESTS_OK checks="+checks);
        }
        private static void Check(bool value,string why)
        { if(!value)throw new InvalidOperationException("Prayer spread test: "+why);checks++; }
    }
}
