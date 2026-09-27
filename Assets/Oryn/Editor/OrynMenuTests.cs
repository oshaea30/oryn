using System;
using Oryn.Interaction;
using UnityEngine;

namespace Oryn.Editor
{
    public static class OrynMenuTests
    {
        private static int checks;
        public static void Run()
        {
            checks = 0;
            foreach (float height in new[] { 0.9f, 1.2f, 1.75f })
            foreach (float yaw in new[] { 0f, 90f, 180f, 270f })
            foreach (float pitch in new[] { -90f, -45f, 0f, 60f, 90f })
            {
                var eye = new Pose(new Vector3(2, height, -3), Quaternion.Euler(pitch, yaw, 0));
                Pose menu = OrynMenuPlacement.InFrontOf(eye);
                Vector3 center = menu.position + menu.rotation * Vector3.right * OrynMenuPlacement.LayoutCenter;
                Check(Mathf.Abs(center.y - (height - 0.23f)) < 0.0001f, "menu stays 23cm below eyes seated/standing, regardless of head pitch");
                Check(Mathf.Abs(Vector3.ProjectOnPlane(center - eye.position, Vector3.up).magnitude - 0.7f) < 0.0001f, "comfortable horizontal distance");
                Check(Vector3.Dot(menu.rotation * Vector3.up, Vector3.up) > 0.999f, "panel stays upright at steep viewing angles");
                Vector3 offset = new Vector3(1, -2, 3);
                var shifted = OrynMenuPlacement.InFrontOf(new Pose(eye.position + offset, eye.rotation));
                Check(Vector3.Distance(shifted.position, menu.position + offset) < 0.0001f, "tracking-origin changes do not anchor menu to floor");
            }
            var near = Button(new Vector3(0, 1, 0.7f));
            var far = Button(new Vector3(0, 1, 1.5f));
            try
            {
                Physics.SyncTransforms();
                var buttons = new[] { far, near };
                var pointer = new Pose(new Vector3(0, 1, 0), Quaternion.identity);
                Check(OrynMenuPlacement.PointedButton(buttons, pointer, out var hit) == near, "nearest ray button wins independently of array order");
                Check(hit.z > 0.6f && hit.z < 0.7f, "marker lands on button surface");
                Check(OrynMenuPlacement.PointedButton(buttons, new Pose(new Vector3(0, 2, 0), Quaternion.identity), out _) == null, "off-target aim cannot click");
                Check(OrynMenuPlacement.PointedButton(buttons, new Pose(new Vector3(0, 1, -3), Quaternion.identity), out _) == null, "ray is bounded at 2.5m");
                Check(OrynMenuPlacement.PointedButton(buttons, new Pose(new Vector3(0, 1, 2), Quaternion.Euler(0,180,0)), out _) == null, "back of panel is not interactive");
                near.Bounds.enabled = false;
                Check(OrynMenuPlacement.PointedButton(buttons, pointer, out _) == far, "disabled collider excluded");
                near.Bounds.enabled = true; near.gameObject.SetActive(false);
                Check(OrynMenuPlacement.PointedButton(buttons, pointer, out _) == far, "inactive panel excluded");
                far.gameObject.SetActive(false);
                Check(OrynMenuPlacement.PointedButton(buttons, pointer, out _) == null, "hidden menu has no targets");
                near.gameObject.SetActive(true); near.transform.position = new Vector3(0.7f,1,0); near.transform.rotation = Quaternion.Euler(0,90,0);
                Physics.SyncTransforms();
                Check(OrynMenuPlacement.PointedButton(buttons, new Pose(pointer.position,Quaternion.Euler(0,90,0)), out _) == near, "rotated menu works after recenter");
                var latch = new OrynPressLatch();
                Check(!latch.Sample(true, 1), "held trigger/A on startup cannot auto-click");
                Check(!latch.Sample(true, 0) && latch.Sample(true, 1), "fresh trigger/A clicks");
                Check(!latch.Sample(true, 1), "held click never repeats across buttons");
                latch.Sample(false, 0);
                Check(!latch.Sample(true, 1), "focus recovery cannot auto-click");
                latch.Sample(true, 0); latch.Clear();
                Check(!latch.Sample(true, 1), "menu recenter clears pending clicks");
                Debug.Log("ORYN_MENU_TESTS_OK checks=" + checks);
            }
            finally { UnityEngine.Object.DestroyImmediate(near.gameObject); UnityEngine.Object.DestroyImmediate(far.gameObject); }
        }
        private static OrynWorkspaceButton Button(Vector3 position)
        {
            var obj = GameObject.CreatePrimitive(PrimitiveType.Cube);
            obj.transform.position = position; obj.transform.localScale = new Vector3(0.2f,0.08f,0.025f);
            var button = obj.AddComponent<OrynWorkspaceButton>(); button.Bounds = obj.GetComponent<Collider>(); return button;
        }
        private static void Check(bool condition, string message)
        { if (!condition) throw new InvalidOperationException("Menu test: " + message); checks++; }
    }
}
