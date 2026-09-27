using System;
using Oryn.Interaction;
using UnityEngine;

namespace Oryn.Editor
{
    public static class OrynRecoveryTests
    {
        private static int checks;
        public static void Run()
        {
            checks = 0;
            foreach (float y in new[] { 0.9f, 1.2f, 1.8f })
            foreach (float pitch in new[] { -90f, 0f, 60f, 90f })
            {
                var eye = new Pose(new Vector3(2,y,3),Quaternion.Euler(pitch,70,0));
                var pose = OrynObjectPlacement.WithinReach(eye);
                Check(Mathf.Abs(pose.position.y - y + 0.08f) < 0.0001f, "recovery height follows seated/standing eyes, not downward head tilt");
                Check(Mathf.Abs(Vector3.ProjectOnPlane(pose.position - eye.position,Vector3.up).magnitude - 0.45f) < 0.0001f, "model returns close enough for reach");
            }
            var material = new Material(Shader.Find("Unlit/Color"));
            var drone = Model(3, material);
            var avocado = Model(1, material);
            var cubeObject = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var cube = cubeObject.AddComponent<OrynWorkspaceObject>();
            try
            {
                var items = new[] { drone, cube, avocado };
                Check(OrynObjectPlacement.RecoveryTarget(items, cube) == drone, "cube selection does not prevent drone recovery");
                Check(OrynObjectPlacement.RecoveryTarget(items, avocado) == drone, "legacy avocado selection does not hide multipart model");
                Check(OrynObjectPlacement.RecoveryTarget(items, null) == drone, "recovery needs no prior grab");
                var part = drone.Assembly.Parts[0];
                Check(OrynObjectPlacement.RecoveryTarget(items, part) == drone, "part selection recovers entire assembly");
                Check(OrynObjectPlacement.RecoveryTarget(new[] { cube, avocado },cube) == avocado, "single-mesh model recovery supported when no assembly exists");
                Check(OrynObjectPlacement.RecoveryTarget(new[] { cube },cube) == null, "primitive not mistaken for imported model");
                Check(OrynObjectPlacement.RecoveryTarget(Array.Empty<OrynWorkspaceObject>(),null) == null, "empty workspace recovery has no invented model");
                string mapping = part.GeometryPath;
                drone.Assembly.Explode(); drone.Assembly.ToggleIsolate(part);
                var eye = new Pose(new Vector3(0,1.2f,0),Quaternion.identity);
                OrynObjectPlacement.Recover(drone, eye);
                Check(drone.Assembly.Parts.Count == 3 && drone.IsImported, "recovery preserves original asset and part count");
                Check(Vector3.Distance(drone.transform.position, new Vector3(0,1.12f,0.45f)) < 0.0001f, "assembly moves into near-eye recovery position");
                Check(!drone.Assembly.PartsMode && !drone.Assembly.Isolated && drone.Bounds.enabled, "recovery reassembles into grabbable whole object");
                Check(part.gameObject.activeSelf && part.GeometryPath == mapping, "visibility restored and record binding retained");
                Check(drone.State.Scale == 1 && drone.State.HoldCount == 0, "recovery resets scale and holds");
                Vector3 before = drone.transform.position;
                OrynObjectPlacement.Recover(drone, eye);
                Check(drone.transform.position == before && items.Length == 3, "repeated recovery neither duplicates nor reloads model");
                Debug.Log("ORYN_RECOVERY_TESTS_OK checks=" + checks);
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(drone.gameObject); UnityEngine.Object.DestroyImmediate(avocado.gameObject);
                UnityEngine.Object.DestroyImmediate(cubeObject); UnityEngine.Object.DestroyImmediate(material);
            }
        }
        private static OrynWorkspaceObject Model(int count, Material material)
        {
            var model = new GameObject("Recovery fixture").AddComponent<OrynRuntimeModel>();
            for (int i = 0; i < count; i++)
            {
                var geometry = GameObject.CreatePrimitive(PrimitiveType.Cube);
                geometry.transform.SetParent(model.transform,false); geometry.transform.localPosition = Vector3.right * i;
            }
            var root = GameObject.CreatePrimitive(PrimitiveType.Cube);
            root.transform.localScale = Vector3.one * 0.35f;
            var owner = root.AddComponent<OrynWorkspaceObject>(); owner.AttachModel(model,material); return owner;
        }
        private static void Check(bool value, string message)
        { if (!value) throw new InvalidOperationException("Recovery test: " + message); checks++; }
    }
}
