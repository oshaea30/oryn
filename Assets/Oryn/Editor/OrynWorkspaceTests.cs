using System;
using UnityEngine;
using Oryn.Interaction;

namespace Oryn.Editor
{
    public static class OrynWorkspaceTests
    {
        private static int checks;
        public static void Run()
        {
            checks = 0;
            for (int left = 0; left <= 2; left += 2)
            for (int right = 1; right <= 3; right += 2)
            for (int releaseFirst = 0; releaseFirst < 2; releaseFirst++)
            {
                var grips = new[] { Pose.identity, Pose.identity, Pose.identity, Pose.identity };
                grips[left] = new Pose(new Vector3(-0.2f, 1f, 0f), Quaternion.identity);
                grips[right] = new Pose(new Vector3(0.2f, 1f, 0f), Quaternion.identity);
                var start = new Pose(new Vector3(0f, 1f, 0.1f), Quaternion.identity);
                var state = new OrynTwoHandState(start);
                Check(state.Begin(left, grips), "first hand acquires");
                Check(!state.Begin(left, grips), "duplicate source rejected");
                Check(!state.Begin((left + 2) % 4, grips), "same physical hand cannot count twice");
                Check(state.Begin(right, grips), "opposite hand joins");
                state.Step(grips);
                PoseNear(state.ObjectPose, start, "second hand joins without snap");
                Check(state.HoldCount == 2, "two owners");
                Check(!state.Begin((right + 2) % 4, grips), "third source rejected");
                grips[left].position += Vector3.up;
                grips[right].position += Vector3.up;
                state.Step(grips);
                Check(Vector3.Distance(state.ObjectPose.position, start.position + Vector3.up) < 0.001f, "two-hand translation");
                grips[left].position = new Vector3(-0.4f, 2f, 0f);
                grips[right].position = new Vector3(0.4f, 2f, 0f);
                state.Step(grips);
                Check(Mathf.Abs(state.Scale - 1f) < 0.001f, "manipulation never resizes when hands spread");
                Check(Vector3.Distance(state.ObjectPose.position, new Vector3(0f, 2f, 0.1f)) < 0.001f, "spreading cannot shift the object center");
                Quaternion rotate = Quaternion.Euler(0f, 90f, 0f);
                Vector3 middle = new Vector3(0f, 2f, 0f);
                grips[left] = new Pose(middle + rotate * Vector3.left * 0.4f, rotate);
                grips[right] = new Pose(middle + rotate * Vector3.right * 0.4f, rotate);
                state.Step(grips);
                Check(Quaternion.Angle(state.ObjectPose.rotation, rotate) < 0.01f, "two-hand rotation");
                Pose before = state.ObjectPose;
                int released = releaseFirst == 0 ? left : right;
                int remaining = releaseFirst == 0 ? right : left;
                state.End(released, grips);
                state.Step(grips);
                Check(state.Primary == remaining && state.HoldCount == 1, "either hand can remain");
                PoseNear(state.ObjectPose, before, "no jump on 2-to-1 handoff");
                Check(Mathf.Abs(state.Scale - 1f) < 0.001f, "scale retained after handoff");
                grips[remaining].position += Vector3.forward * 0.15f;
                state.Step(grips);
                Check(Vector3.Distance(state.ObjectPose.position, before.position + Vector3.forward * 0.15f) < 0.001f, "remaining hand continues moving");
                before = state.ObjectPose;
                Check(state.Begin(released, grips), "released hand can rejoin");
                state.Step(grips);
                PoseNear(state.ObjectPose, before, "rejoin rebases current pose");
                state.End(released, grips); // Also the route used for lost hand tracking.
                state.End(remaining, grips);
                before = state.ObjectPose;
                grips[remaining].position += Vector3.one;
                state.Step(grips);
                PoseNear(state.ObjectPose, before, "last release freezes pose");
                Check(state.HoldCount == 0, "last release clears ownership");
                state.Reset(start);
                Check(state.Scale == 1f && state.HoldCount == 0, "reset restores size and ownership");
            }
            LimitsAndIndependentObjects();
            GestureModes();
            GestureRecognition();
            SurfaceContacts();
            ResizeContactRegression();
            for (int source = 0; source < 4; source++)
            {
                var latch = new OrynPressLatch();
                Check(!latch.Sample(true, 1), "held input on startup does not activate UI");
                Check(!latch.Sample(true, 0) && latch.Sample(true, 1), "fresh grip/pinch activates once");
                Check(!latch.Sample(true, 1) && !latch.Sample(true, 0.5f), "holding cannot repeat create/delete");
                Check(!latch.Sample(false, 0) && !latch.Sample(true, 1), "tracking restore cannot auto-activate");
                latch.Sample(true, 0); latch.Clear();
                Check(!latch.Sample(true, 1), "focus loss clears input latch");
            }
            Debug.Log("ORYN_M3_TESTS_OK checks=" + checks);
        }
        private static void LimitsAndIndependentObjects()
        {
            var poses = new[] { new Pose(Vector3.left * 0.2f, Quaternion.identity), new Pose(Vector3.right * 0.2f, Quaternion.identity), Pose.identity, Pose.identity };
            var state = new OrynTwoHandState(Pose.identity);
            var resize = new[] { OrynGesture.Resize, OrynGesture.Resize, OrynGesture.Resize, OrynGesture.Resize };
            state.Begin(0, poses, resize); state.Begin(1, poses, resize);
            poses[0].position = Vector3.left * 10; poses[1].position = Vector3.right * 10;
            state.Step(poses, resize); Check(Mathf.Abs(state.Scale - OrynTwoHandState.MaximumScale) < 0.001f, "upper scale clamp");
            poses[0].position = Vector3.left * 0.035f; poses[1].position = Vector3.right * 0.035f;
            state.Step(poses, resize); Check(Mathf.Abs(state.Scale - OrynTwoHandState.MinimumScale) < 0.001f, "lower scale clamp");
            Pose before = state.ObjectPose;
            poses[0].position = poses[1].position = Vector3.zero;
            state.Step(poses, resize); PoseNear(state.ObjectPose, before, "collapsed hand span freezes safely");
            state.ReleaseAll(); Check(state.HoldCount == 0, "pause releases both owners");
            var a = new OrynTwoHandState(Pose.identity);
            var b = new OrynTwoHandState(new Pose(Vector3.one, Quaternion.identity));
            a.Begin(0, poses); b.Begin(1, poses);
            poses[0].position += Vector3.up; poses[1].position += Vector3.right;
            a.Step(poses); b.Step(poses);
            Check(a.ObjectPose.position == Vector3.up, "left hand moves independent object");
            Check(b.ObjectPose.position == Vector3.one + Vector3.right, "right hand moves independent object");
        }
        private static void GestureModes()
        {
            var poses = new[] { new Pose(Vector3.left * 0.2f, Quaternion.identity), new Pose(Vector3.right * 0.2f, Quaternion.identity), Pose.identity, Pose.identity };
            var modes = new[] { OrynGesture.Resize, OrynGesture.Resize, OrynGesture.Resize, OrynGesture.Resize };
            var original = new Pose(new Vector3(0, 0, 0.1f), Quaternion.Euler(10, 20, 30));
            var state = new OrynTwoHandState(original);
            state.Begin(0, poses, modes);
            poses[0].position += Vector3.up;
            state.Step(poses, modes);
            PoseNear(state.ObjectPose, original, "single two-finger pinch waits instead of moving object");
            Check(state.Mode == OrynTwoHandState.Operation.Waiting, "waiting state visible");
            poses[0].position = Vector3.left * 0.2f;
            state.Begin(1, poses, modes);
            state.Step(poses, modes);
            Check(state.Mode == OrynTwoHandState.Operation.Resize, "two pinches enter resize");
            poses[0].position = Vector3.left * 0.205f; poses[1].position = Vector3.right * 0.205f;
            state.Step(poses, modes);
            Check(Mathf.Abs(state.Scale - 1f) < 0.001f, "two-centimeter resize dead zone");
            poses[0] = new Pose(Vector3.up + Vector3.back * 0.4f, Quaternion.Euler(80, 20, 100));
            poses[1] = new Pose(Vector3.up + Vector3.forward * 0.4f, Quaternion.Euler(-80, 70, -100));
            state.Step(poses, modes);
            Check(Mathf.Abs(state.Scale - 1.95f) < 0.001f, "intentional pinch-and-pull resizes");
            PoseNear(state.ObjectPose, original, "resize cannot move or rotate even when wrists and midpoint move");
            float size = state.Scale;
            modes[0] = OrynGesture.Manipulate;
            state.Step(poses, modes);
            Check(state.Mode == OrynTwoHandState.Operation.Waiting, "mixed gestures pause instead of guessing");
            poses[0].position += Vector3.one;
            state.Step(poses, modes);
            PoseNear(state.ObjectPose, original, "mixed gestures do not move object");
            Check(state.Scale == size, "mixed gestures do not resize");
            modes[1] = OrynGesture.Manipulate;
            state.Step(poses, modes);
            PoseNear(state.ObjectPose, original, "switch to manipulation rebases without jump");
            poses[0].position += Vector3.up * 0.3f; poses[1].position += Vector3.up * 0.3f;
            state.Step(poses, modes);
            Check(Vector3.Distance(state.ObjectPose.position, original.position + Vector3.up * 0.3f) < 0.001f, "three-finger manipulation moves object");
            Check(state.Scale == size, "manipulation retains resized size");
            Pose before = state.ObjectPose;
            poses[0].rotation = Quaternion.Euler(0, 0, 179); poses[1].rotation = Quaternion.Euler(0, 0, -179);
            state.Step(poses, modes);
            PoseNear(state.ObjectPose, before, "opposing wrist rolls cannot flip two-hand orientation");
            modes[0] = OrynGesture.Uncertain;
            state.Step(poses, modes); poses[0].position += Vector3.one;
            state.Step(poses, modes); PoseNear(state.ObjectPose, before, "uncertain extra fingers freeze transform");
            state.ReleaseAll();
            poses[0] = new Pose(Vector3.left * 0.2f, Quaternion.identity); poses[1] = new Pose(Vector3.right * 0.2f, Quaternion.identity);
            modes[0] = modes[1] = OrynGesture.Manipulate;
            state.Reset(Pose.identity); state.Begin(0, poses, modes); state.Begin(1, poses, modes);
            poses[0].position = Vector3.forward * 0.2f; poses[1].position = Vector3.back * 0.2f;
            state.Step(poses, modes, 1f / 60f);
            Check(Quaternion.Angle(state.ObjectPose.rotation, Quaternion.identity) <= 4.01f, "rotation speed limit at 60 Hz");
            before = state.ObjectPose;
            poses[0].position = Vector3.back * 0.2f; poses[1].position = Vector3.forward * 0.2f;
            state.Step(poses, modes);
            PoseNear(state.ObjectPose, before, "single-frame tracking reversal is rejected");
        }
        private static void GestureRecognition()
        {
            var classifier = new OrynGestureClassifier();
            var confidence = new[] { true, true, true, true };
            var fingers = new[] { 1f, 0f, 0f, 0f };
            Check(classifier.Sample(fingers, confidence, 0.01f) == OrynGesture.Uncertain, "pinch must settle");
            Check(classifier.Sample(fingers, confidence, 0.2f) == OrynGesture.Resize, "thumb plus index means resize");
            fingers[1] = 1f;
            Check(classifier.Sample(fingers, confidence, 0.1f) == OrynGesture.Manipulate, "thumb plus index and middle means manipulate");
            fingers[1] = 0.5f;
            Check(classifier.Sample(fingers, confidence, 0.1f) == OrynGesture.Manipulate, "finger hysteresis avoids resize flicker");
            fingers[1] = 0f;
            Check(classifier.Sample(fingers, confidence, 0.01f) == OrynGesture.Uncertain, "removing third finger pauses during debounce");
            Check(classifier.Sample(fingers, confidence, 0.2f) == OrynGesture.Resize, "deliberate return to two fingers enables resize");
            confidence[1] = false;
            Check(classifier.Sample(fingers, confidence, 1f) == OrynGesture.Uncertain, "unknown extra finger cannot be assumed open");
            confidence[1] = true;
            classifier.Clear(); fingers[0] = 0; fingers[1] = fingers[2] = 1;
            Check(classifier.Sample(fingers, confidence, 0.1f) == OrynGesture.Manipulate, "thumb plus middle and ring also works");
            fingers[0] = fingers[3] = 1;
            Check(classifier.Sample(fingers, confidence, 0.1f) == OrynGesture.Manipulate, "additional fingers remain manipulation");
            for (int i = 0; i < 4; i++) fingers[i] = 0;
            Check(classifier.Sample(fingers, confidence, 0.1f) == OrynGesture.None, "open hand releases gesture");
        }
        private static void ResizeContactRegression()
        {
            var cube = new GameObject("Resize regression target");
            try
            {
                var box = cube.AddComponent<BoxCollider>(); cube.transform.localScale = Vector3.one * 0.35f;
                Vector3 near = new Vector3(0.27f, 0, 0);
                Check(!OrynSurfaceContact.Touch(box, near, near, false, out _), "resize fixture is not physically touching");
                Check(OrynSurfaceContact.ResizeTarget(box, near, out _), "resize pinch may start near surface");
                Check(!OrynSurfaceContact.ResizeTarget(box, Vector3.right, out _), "resize cannot select distant objects");
                Check(!OrynSurfaceContact.ResizeTarget(box, Vector3.zero, out _), "resize does not acquire deep interior");
                for (int left = 0; left <= 2; left += 2)
                for (int right = 1; right <= 3; right += 2)
                {
                    var poses = new[] { Pose.identity, Pose.identity, Pose.identity, Pose.identity };
                    var points = new[] { Vector3.zero, Vector3.zero, Vector3.zero, Vector3.zero };
                    var gestures = new[] { OrynGesture.Resize, OrynGesture.Resize, OrynGesture.Resize, OrynGesture.Resize };
                    // Both surface anchors may coincide at a corner, while the actual
                    // pinches have ample separation. Acquisition must use the latter.
                    points[left] = Vector3.left * 0.1f; points[right] = Vector3.right * 0.1f;
                    var state = new OrynTwoHandState(Pose.identity);
                    Check(state.Begin(left, poses, gestures, points) && state.Begin(right, poses, gestures, points), "two nearby pinches acquire despite coincident surface anchors");
                    state.Step(poses, gestures, 1, points);
                    Check(Mathf.Abs(state.Scale - 1) < 0.001f, "resize acquisition no jump");
                    points[left] *= 2; points[right] *= 2;
                    state.Step(poses, gestures, 1, points);
                    Check(state.Scale > 1.8f, "actual pinch span enlarges while surface anchors remain stationary");
                    PoseNear(state.ObjectPose, Pose.identity, "resize never moves or rotates contact object");
                    points[left] *= 0.6f; points[right] *= 0.6f;
                    state.Step(poses, gestures, 1, points);
                    Check(state.Scale < 1.2f, "pinching together shrinks");
                    gestures[left] = gestures[right] = OrynGesture.Manipulate;
                    poses[left].position = Vector3.left * 0.15f; poses[right].position = Vector3.right * 0.15f;
                    float scale = state.Scale;
                    state.Step(poses, gestures, 1, points);
                    PoseNear(state.ObjectPose, Pose.identity, "resize to manipulate rebases without snap");
                    poses[left].position += Vector3.up * 0.1f; poses[right].position += Vector3.up * 0.1f;
                    state.Step(poses, gestures, 1, points);
                    Check(Mathf.Abs(state.Scale - scale) < 0.001f && state.ObjectPose.position.y > 0.09f, "manipulation after resize moves with size locked");
                    gestures[left] = gestures[right] = OrynGesture.Resize;
                    state.Step(poses, gestures, 1, points);
                    Check(Mathf.Abs(state.Scale - scale) < 0.001f, "manipulate to resize starts a fresh pinch baseline");
                    state.End(right, poses, gestures, points);
                    points[left] *= 3; state.Step(poses, gestures, 1, points);
                    Check(Mathf.Abs(state.Scale - scale) < 0.001f, "one remaining pinch waits without scaling");
                }
            }
            finally { UnityEngine.Object.DestroyImmediate(cube); }
        }
        private static void SurfaceContacts()
        {
            var cube = new GameObject("Surface contact test cube");
            var sphere = new GameObject("Surface contact test sphere");
            var finger = new GameObject("Visual finger test");
            try
            {
                var box = cube.AddComponent<BoxCollider>();
                box.size = Vector3.one;
                cube.transform.localScale = Vector3.one * 0.35f;
                Check(OrynSurfaceContact.Query(box, new Vector3(0.185f, 0, 0), out Vector3 point, out Vector3 normal, out float depth), "box query supported");
                Check(Vector3.Distance(point, Vector3.right * 0.175f) < 0.0001f && Mathf.Abs(depth - 0.01f) < 0.0001f, "face contact in world metres");
                Check(Vector3.Distance(normal, Vector3.right) < 0.0001f, "face outward normal");
                Check(OrynSurfaceContact.Touch(box, new Vector3(0.18f, 0.18f, 0.18f), Vector3.zero, false, out point), "corners touch without targeting center");
                Check(Vector3.Distance(point, Vector3.one * 0.175f) < 0.0001f, "corner anchor on actual collider");
                Check(!OrynSurfaceContact.Touch(box, Vector3.zero, Vector3.zero, false, out _), "deep interior is not a new surface contact");
                Check(!OrynSurfaceContact.Touch(box, Vector3.right * 0.22f, Vector3.zero, false, out _), "no old ten-centimetre air grab");
                OrynSurfaceContact.Query(box, Vector3.right * 0.17f, out point, out normal, out depth);
                Check(depth < 0 && Vector3.Distance(point, Vector3.right * 0.175f) < 0.0001f, "inside query projects to skin not interior");
                OrynSurfaceContact.Query(box, Vector3.zero, out point, out normal, out depth);
                Check(!float.IsNaN(normal.x) && Mathf.Abs(depth + 0.175f) < 0.0001f, "box center finite deterministic surface");
                Physics.SyncTransforms();
                Check(OrynSurfaceContact.Touch(box, Vector3.right * 0.14f, Vector3.right * 0.22f, true, out point), "swept contact catches crossing");
                Check(!OrynSurfaceContact.Touch(box, Vector3.right * 0.14f, Vector3.right, true, out _), "tracking teleport cannot infer a touch");
                cube.transform.SetPositionAndRotation(new Vector3(2, 1, -1), Quaternion.Euler(10, 32, 25));
                cube.transform.localScale = new Vector3(0.35f, 0.5f, 0.7f);
                Vector3 probe = cube.transform.TransformPoint(new Vector3(0.52f, 0.2f, 0));
                OrynSurfaceContact.Query(box, probe, out point, out normal, out depth);
                Check(Vector3.Distance(point, cube.transform.TransformPoint(new Vector3(0.5f, 0.2f, 0))) < 0.0001f, "rotated scaled box surface");
                Check(Mathf.Abs(depth - 0.007f) < 0.0001f, "nonuniform box distance uses world scale");
                var ball = sphere.AddComponent<SphereCollider>();
                sphere.transform.localScale = Vector3.one * 0.35f;
                ball.radius = 0.5f;
                OrynSurfaceContact.Query(ball, Vector3.up * 0.16f, out point, out normal, out depth);
                Check(Vector3.Distance(point, Vector3.up * 0.175f) < 0.0001f && depth < 0, "sphere inside projects to surface");
                OrynSurfaceContact.Query(ball, Vector3.zero, out point, out normal, out depth);
                Check(!float.IsNaN(point.y) && Mathf.Abs(point.magnitude - 0.175f) < 0.0001f, "sphere center finite fallback");
                ball.enabled = false;
                Check(!OrynSurfaceContact.Touch(ball, Vector3.up * 0.175f, Vector3.zero, false, out _), "disabled object cannot acquire");

                var latch = new OrynContactLatch();
                Check(!latch.Sample(true, 1, true, 0), "initial closed hand cannot grab");
                Check(!latch.Sample(true, 0, false, 0.1f), "opening arms surface grab");
                Check(!latch.Sample(true, 1, false, 0.2f), "closing in air waits for contact");
                Check(latch.Sample(true, 1, true, 0.3f), "touch during grace period acquires");
                Check(!latch.Sample(true, 1, true, 0.4f), "surface grab does not repeat");
                latch.Sample(true, 0, false, 0.5f); latch.Sample(true, 1, false, 0.6f);
                Check(!latch.Sample(true, 1, true, 1f), "old air pinch expires");
                latch.Sample(false, 0, false, 1.1f);
                Check(!latch.Sample(true, 1, true, 1.2f), "tracking restore while closed cannot grab");
                latch.Sample(true, 0, false, 1.3f); latch.Sample(true, 1, false, 1.4f); latch.Clear();
                Check(!latch.Sample(true, 1, true, 1.5f), "UI or pause cancels pending surface grab");
                latch.Sample(true, 0, false, 1.6f); latch.Sample(true, 1, false, 1.7f);
                Check(!latch.Sample(true, 0, true, 1.8f), "opening cancels pending grab");

                var chain = new Transform[4]; chain[0] = finger.transform;
                for (int i = 1; i < chain.Length; i++)
                { chain[i] = new GameObject("joint " + i).transform; chain[i].SetParent(chain[i - 1], false); chain[i].localPosition = Vector3.right * 0.025f; }
                Vector3 target = new Vector3(0.055f, 0.03f, 0);
                float before = Vector3.Distance(chain[3].position, target);
                OrynContactHandVisual.SolveFinger(chain[3], target, new Transform[3], new Quaternion[3]);
                Check(Vector3.Distance(chain[3].position, target) < before, "visual solver brings tip toward contact");
                for (int i = 0; i < 3; i++)
                {
                    Check(Mathf.Abs(Vector3.Distance(chain[i].position, chain[i + 1].position) - 0.025f) < 0.0001f, "contact preserves finger bone length");
                    Check(Quaternion.Angle(chain[i].localRotation, Quaternion.identity) <= 35.01f, "visual deviation bounded per joint");
                }
            }
            finally { UnityEngine.Object.DestroyImmediate(cube); UnityEngine.Object.DestroyImmediate(sphere); UnityEngine.Object.DestroyImmediate(finger); }
        }
        private static void PoseNear(Pose actual, Pose expected, string name)
        {
            Check(Vector3.Distance(actual.position, expected.position) < 0.001f && Quaternion.Angle(actual.rotation, expected.rotation) < 0.02f, name);
        }
        private static void Check(bool pass, string name)
        {
            if (!pass) throw new InvalidOperationException("Oryn workspace test failed: " + name);
            checks++;
        }
    }
}
