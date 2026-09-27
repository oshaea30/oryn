using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Oryn.Interaction;
using UnityEngine;

namespace Oryn.Editor
{
    public static class OrynAssemblyTests
    {
        private static int checks;
        public static async Task Run()
        {
            checks = 0;
            string path = Environment.GetEnvironmentVariable("ORYN_ASSEMBLY_TEST_MODEL");
            OrynRuntimeModel model;
            if (!string.IsNullOrEmpty(path)) model = await OrynRuntimeModel.Load(Path.GetFullPath(path));
            else
            {
                model = new GameObject("Synthetic multipart fixture").AddComponent<OrynRuntimeModel>();
                for (int i = 0; i < 3; i++)
                {
                    var child = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    UnityEngine.Object.DestroyImmediate(child.GetComponent<Collider>());
                    child.transform.SetParent(model.transform, false);
                    child.transform.localPosition = new Vector3(i - 1, 0, 0);
                }
            }
            var root = GameObject.CreatePrimitive(PrimitiveType.Cube);
            root.transform.SetPositionAndRotation(new Vector3(1, 1.3f, 2), Quaternion.Euler(10, 25, 5));
            root.transform.localScale = Vector3.one * 0.35f;
            var owner = root.AddComponent<OrynWorkspaceObject>(); owner.Initialize();
            var outline = new Material(Shader.Find("Unlit/Color"));
            try
            {
                int meshCount = model.GetComponentsInChildren<MeshRenderer>(true).Length;
                var meshes = model.GetComponentsInChildren<MeshFilter>(true).Select(f => f.sharedMesh).ToArray();
                owner.AttachModel(model, outline);
                var assembly = owner.Assembly;
                Check(assembly != null && assembly.Parts.Count == meshCount, "one interaction target per mesh renderer");
                if (!string.IsNullOrEmpty(path)) Check(meshCount == 39, "actual drone imported as 39 parts");
                Check(!assembly.PartsMode && owner.Bounds.enabled, "default whole-object mode");
                Check(assembly.Parts.All(p => !p.Bounds.enabled), "part hit targets disabled in whole mode");
                Check(assembly.Parts.All(p => p.PartOf == assembly && p.transform.IsChildOf(root.transform)), "parts remain owned by assembly");
                Check(meshes.All(m => root.GetComponentsInChildren<MeshFilter>(true).Any(f => f.sharedMesh == m)), "imported mesh resources retained");
                var homes = assembly.Parts.Select(p => p.transform.localPosition).ToArray();
                var rotations = assembly.Parts.Select(p => p.transform.localRotation).ToArray();
                assembly.SetPartsMode(true);
                Check(assembly.PartsMode && !owner.Bounds.enabled && assembly.Parts.All(p => p.Bounds.enabled), "parts and root targets mutually exclusive");
                var first = assembly.Parts[0]; var second = assembly.Parts[1];
                var grips = new Pose[4];
                for (int i = 0; i < 4; i++) grips[i] = new Pose(first.transform.position + Vector3.right * i * 0.1f, Quaternion.identity);
                Check(first.State.Begin(0, grips) && second.State.Begin(1, grips), "opposite hands hold different parts");
                Vector3 secondBefore = second.transform.position;
                grips[0].position += Vector3.up * 0.15f;
                first.State.Step(grips); first.Apply(false, true);
                Check(Vector3.Distance(second.transform.position, secondBefore) < 0.0001f, "moving one part does not move its neighbor");
                Check(Vector3.Distance(first.transform.localPosition, homes[0]) > 0.1f, "part moves independently");
                assembly.ToggleIsolate(first);
                Check(first.State.HoldCount == 0 && second.State.HoldCount == 0, "isolation releases all part state");
                Check(assembly.Isolated && assembly.Parts.Count(p => p.gameObject.activeSelf) == 1, "only selected part visible");
                assembly.ToggleIsolate(first);
                Check(!assembly.Isolated && assembly.Parts.All(p => p.gameObject.activeSelf), "show all restores visibility");
                assembly.Explode();
                Check(assembly.PartsMode && assembly.Parts.All(p => p.Bounds.enabled), "explode enters part mode");
                for (int i = 0; i < homes.Length; i++) Near(assembly.Parts[i].transform.localPosition, homes[i] * 2.1f, "exploded home position");
                assembly.Reassemble();
                Check(!assembly.PartsMode && owner.Bounds.enabled && !assembly.Isolated, "reassembly restores whole mode");
                for (int i = 0; i < homes.Length; i++)
                {
                    Near(assembly.Parts[i].transform.localPosition, homes[i], "reassembled position");
                    Check(Quaternion.Angle(assembly.Parts[i].transform.localRotation, rotations[i]) < 0.001f, "reassembled rotation");
                    Check(!assembly.Parts[i].Bounds.enabled && assembly.Parts[i].State.HoldCount == 0, "reassembled part not held or targetable");
                }
                owner.State.Reset(new Pose(new Vector3(-1, 1, 1), Quaternion.Euler(0, 70, 0))); owner.Apply(false, true);
                assembly.SetPartsMode(true);
                foreach (var part in assembly.Parts) Near(part.State.ObjectPose.position, part.transform.position, "entering part mode rebases after owner move");
                var original = first.transform.position;
                grips[0] = new Pose(original - Vector3.right * 0.1f, Quaternion.identity);
                grips[1] = new Pose(original + Vector3.right * 0.1f, Quaternion.identity);
                var gestures = new[] { OrynGesture.Resize, OrynGesture.Resize, OrynGesture.Manipulate, OrynGesture.Manipulate };
                Check(first.State.Begin(0, grips, gestures) && first.State.Begin(1, grips, gestures), "existing two-hand resize available on part");
                grips[1].position += Vector3.right * 0.2f; first.State.Step(grips, gestures); first.Apply(false, true);
                Check(first.State.Scale > 1.5f, "part scales through unchanged resize state");
                assembly.ResetPart(first);
                Check(first.State.Scale == 1 && first.State.HoldCount == 0, "reset part restores original scale and release");
                Near(first.transform.localPosition, homes[0], "reset part restores assembly-relative home");
                assembly.Reassemble(); assembly.Reassemble();
                Check(assembly.Parts.All(p => p.gameObject.activeSelf), "reassembly idempotent");
                assembly.BeginSpread(); assembly.SetSpread(0.5f);
                Check(assembly.PartsMode && assembly.SpreadAmount == 0.5f, "continuous spread active");
                for (int i = 0; i < homes.Length; i++) Near(assembly.Parts[i].transform.localPosition, homes[i] * 1.55f, "half spread is positional, not mesh scaling");
                Check(assembly.Parts.All(p => p.State.Scale == 1), "spread never changes part sizes");
                assembly.SetSpread(9); Check(assembly.SpreadAmount == 1, "spread cap");
                assembly.SetSpread(-1); Check(assembly.SpreadAmount == 0, "spread lower bound");
                assembly.SetSpread(float.NaN); Check(assembly.SpreadAmount == 0, "nonfinite spread ignored");
                for (int i = 0; i < homes.Length; i++) Near(assembly.Parts[i].transform.localPosition, homes[i], "zero spread restores home positions");
                assembly.Reassemble();
                Debug.Log("ORYN_ASSEMBLY_TESTS_OK checks=" + checks + " parts=" + meshCount);
            }
            finally
            {
                model.ReleaseResources();
                UnityEngine.Object.DestroyImmediate(root);
                UnityEngine.Object.DestroyImmediate(outline);
            }
        }
        private static void Check(bool condition, string message)
        { if (!condition) throw new InvalidOperationException("Assembly test: " + message); checks++; }
        private static void Near(Vector3 a, Vector3 b, string message) { Check(Vector3.Distance(a, b) < 0.0001f, message); }
    }
}
