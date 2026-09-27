using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Oryn.Interaction;
using UnityEngine;

namespace Oryn.Editor
{
    public static class OrynKnowledgeTests
    {
        private static int checks;
        public static async Task Run()
        {
            checks = 0;
            string folder = Path.Combine(Path.GetTempPath(), "oryn-knowledge-test-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(folder);
            try
            {
                var store = new OrynKnowledgeStore(folder);
                string asset = new string('a', 64), address = "renderer-path-v1/0/1";
                Check(store.ResumeModel() == null, "new installation has no saved model");
                var empty = store.Ensure(asset, address, "Object_006");
                Check(empty.Status == "unidentified" && empty.Label == "" && empty.Revision == 0, "mesh names never imply identities");
                Check(empty.partId == OrynKnowledgeStore.PartId(asset, address), "stable content-scoped ID");
                Check(empty.partId != OrynKnowledgeStore.PartId(new string('b',64), address), "asset revisions cannot inherit labels");
                Check(empty.partId != OrynKnowledgeStore.PartId(asset, address + "/0"), "different geometry cannot inherit labels");
                var note = store.Annotate(empty, "Motor");
                Check(note.Status == "user_annotation" && note.Revision == 1, "save creates unverified annotation");
                Check(note.history[0].source == "local_user" && note.history[0].verification == "unverified", "attribution preserved");
                var reloaded = new OrynKnowledgeStore(folder).Read(asset, address, "Object_006");
                Check(reloaded.Label == "Motor" && reloaded.partId == note.partId, "new store reloads label and identity");
                Check(store.Annotate(reloaded, "Motor").Revision == 1, "identical save is idempotent");
                Reject(() => store.Annotate(empty, "Battery"), "stale record cannot overwrite a correction");
                var corrected = store.Annotate(reloaded, "Housing");
                Check(corrected.Revision == 2 && corrected.history[0].label == "Motor", "correction retains prior assertion");
                var cleared = store.Annotate(corrected, "");
                Check(cleared.Status == "unidentified" && cleared.Revision == 3 && cleared.history[1].label == "Housing", "clear appends retraction, not deletion");
                Check(store.Read(asset, address + "/0", "Object_006").Label == "", "same name elsewhere stays unknown");
                Check(store.Read(new string('b',64), address, "Object_006").Label == "", "different asset stays unknown");
                Reject(() => store.Read("../escape", address, "Object_006"), "path traversal rejected");
                Reject(() => store.Read(asset, address, "changed"), "geometry binding mismatch fails closed");
                foreach (var label in new[] { "<b>Motor</b>", "Motor\nBattery", new string('x', 61), " Motor", null })
                    Reject(() => store.Annotate(cleared, label), "invalid label rejected");
                string path = Path.Combine(folder,"Records",asset,empty.partId + ".json");
                Check(File.Exists(path + ".bak"), "previous revision retained as backup");
                string valid = File.ReadAllText(path);
                File.WriteAllText(path, "{ broken");
                Reject(() => store.Read(asset, address, "Object_006"), "corrupt record not silently reset");
                Check(File.ReadAllText(path) == "{ broken", "corrupt original preserved");
                File.WriteAllText(path, valid.Replace("unverified", "verified"));
                Reject(() => store.Read(asset, address, "Object_006"), "unsupported verified assertion rejected");
                File.WriteAllText(path, valid.Replace("\"schema\": 1", "\"schema\": 99"));
                Reject(() => store.Read(asset, address, "Object_006"), "unknown schema rejected");

                string modelPath = Environment.GetEnvironmentVariable("ORYN_ASSEMBLY_TEST_MODEL");
                if (string.IsNullOrEmpty(modelPath)) modelPath = "RuntimeAssets/Avocado.glb";
                modelPath = Path.GetFullPath(modelPath);
                string hash = OrynKnowledgeStore.HashFile(modelPath);
                store.RememberModel(modelPath, hash);
                var resumed = new OrynKnowledgeStore(folder).ResumeModel();
                Check(resumed != modelPath && OrynKnowledgeStore.HashFile(resumed) == hash, "saved model is an independent checksum-verified copy");
                store.RememberModel(resumed, hash);
                Check(store.ResumeModel() == resumed, "remember cached source is idempotent");
                Reject(() => store.RememberModel(modelPath, asset), "wrong source checksum rejected");
                var first = await OrynRuntimeModel.Load(modelPath);
                var second = await OrynRuntimeModel.Load(resumed);
                var root = GameObject.CreatePrimitive(PrimitiveType.Cube);
                var material = new Material(Shader.Find("Unlit/Color"));
                try
                {
                    string[] original = first.GetComponentsInChildren<MeshRenderer>(true).Select(r => OrynKnowledgeStore.GeometryPath(r.transform, first.transform)).ToArray();
                    string[] again = second.GetComponentsInChildren<MeshRenderer>(true).Select(r => OrynKnowledgeStore.GeometryPath(r.transform, second.transform)).ToArray();
                    Check(first.SourceHash == hash && second.SourceHash == hash, "filename/delivery independent asset identity");
                    Check(original.SequenceEqual(again), "geometry addresses survive complete reimport");
                    Check(original.Distinct().Count() == original.Length, "unique renderer addresses");
                    var item = root.AddComponent<OrynWorkspaceObject>();
                    item.AttachModel(first, material);
                    if (item.Assembly != null)
                    {
                        Check(item.Assembly.Parts.Select(p => p.GeometryPath).SequenceEqual(original), "wrapping does not change recorded addresses");
                        var part = item.Assembly.Parts[0];
                        var partRecord = store.Ensure(hash, part.GeometryPath, part.GeometryName);
                        store.Annotate(partRecord, "Housing");
                        item.Assembly.Explode(); item.Assembly.Reassemble();
                        Check(store.Read(hash, part.GeometryPath, part.GeometryName).Label == "Housing", "gesture transforms do not change identity");
                        string secondName = second.GetComponentsInChildren<MeshRenderer>(true)[0].name;
                        Check(new OrynKnowledgeStore(folder).Read(hash, again[0], secondName).Label == "Housing", "real GLB reimport restores annotation on same geometry");
                        var inspector = root.AddComponent<OrynPartInspector>();
                        typeof(OrynPartInspector).GetField("store", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic).SetValue(inspector, store);
                        inspector.Details = new GameObject("Test inspector text").AddComponent<TextMesh>();
                        inspector.Details.transform.SetParent(root.transform);
                        inspector.Bind(item);
                        Check(!inspector.CanEdit && !inspector.CanSave, "whole assembly cannot receive a part label");
                        inspector.Bind(part);
                        Check(inspector.CanEdit && !inspector.CanSave && inspector.Details.text.Contains("Housing"), "inspector reads current annotation");
                        inspector.Cycle(1);
                        Check(inspector.CanSave && store.Read(hash, part.GeometryPath, part.GeometryName).Label == "Housing", "cycling is a draft, not a write");
                        inspector.Bind(item.Assembly.Parts[1]); inspector.Bind(part);
                        Check(!inspector.CanSave, "changing selection discards draft instead of applying to another part");
                        inspector.Cycle(1); inspector.Save();
                        Check(store.Read(hash, part.GeometryPath, part.GeometryName).Label == "Fastener" && !inspector.CanSave, "explicit Save persists inspector draft");
                        inspector.Cycle(1); inspector.Cycle(1); inspector.Save();
                        Check(store.Read(hash, part.GeometryPath, part.GeometryName).Status == "unidentified", "picker clears assertion without deleting history");
                        Check(inspector.Details.text.Contains("unverified") && inspector.Details.text.Contains("unknown"), "inspector never promotes annotation to verified evidence");
                        inspector.Bind(null);
                        Check(!inspector.CanEdit && !inspector.CanSave, "deleted/unselected target disables editing");
                    }
                }
                finally
                {
                    first.ReleaseResources(); second.ReleaseResources();
                    UnityEngine.Object.DestroyImmediate(root); UnityEngine.Object.DestroyImmediate(second.gameObject);
                    UnityEngine.Object.DestroyImmediate(material);
                }
                File.WriteAllText(resumed, "corrupted");
                Reject(() => store.ResumeModel(), "corrupt cached model rejected");
                File.WriteAllText(Path.Combine(folder,"last-model.txt"), "../outside");
                Reject(() => store.ResumeModel(), "invalid resume pointer rejected");
                Debug.Log("ORYN_KNOWLEDGE_TESTS_OK checks=" + checks);
            }
            finally { Directory.Delete(folder, true); } // Only this unique test-owned directory.
        }
        private static void Check(bool value, string message)
        { if (!value) throw new InvalidOperationException("Knowledge test: " + message); checks++; }
        private static void Reject(Action action, string message)
        {
            try { action(); }
            catch (Exception error) when (error is InvalidDataException || error is InvalidOperationException || error is ArgumentException) { checks++; return; }
            throw new Exception("Knowledge test accepted invalid operation: " + message);
        }
    }
}
