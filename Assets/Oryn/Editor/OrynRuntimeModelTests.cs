using System;
using System.IO;
using System.Threading.Tasks;
using Oryn.Interaction;
using UnityEditor;
using UnityEngine;

namespace Oryn.Editor
{
    // Execute without -quit: glTF import must be allowed to yield through the
    // editor's main-thread synchronization context before the build begins.
    public static class OrynRuntimeModelTests
    {
        private static Task validation;
        private static double deadline;
        public static void ValidateAndBuild()
        {
            deadline = EditorApplication.timeSinceStartup + 120;
            validation = Validate();
            EditorApplication.update += Poll;
        }
        private static void Poll()
        {
            if (!validation.IsCompleted && EditorApplication.timeSinceStartup < deadline) { EditorApplication.QueuePlayerLoopUpdate(); return; }
            EditorApplication.update -= Poll;
            try
            {
                if (!validation.IsCompleted) throw new TimeoutException("Runtime model test timed out");
                validation.GetAwaiter().GetResult();
                OrynWorkspaceSetup.BuildAndroid();
                EditorApplication.Exit(0);
            }
            catch (Exception error) { Debug.LogException(error); EditorApplication.Exit(1); }
        }
        private static async Task Validate()
        {
            await OrynAssemblyTests.Run();
            OrynPrayerSpreadTests.Run();
            OrynCommandTests.Run();
            await OrynKnowledgeTests.Run();
            int checks = 0;
            var delivery = new OrynGenerationInbox.Delivery { id = new string('a', 32), job_id = new string('b', 32), sha256 = new string('c', 64), demo = true };
            Require(OrynGenerationInbox.ValidDelivery(delivery, delivery.id), "valid delivery manifest"); checks++;
            Require(!OrynGenerationInbox.ValidDelivery(delivery, new string('d', 32)), "manifest cannot redirect to another file"); checks++;
            delivery.id = "../model";
            Require(!OrynGenerationInbox.ValidDelivery(delivery, delivery.id), "path traversal rejected"); checks++;
            delivery.id = new string('a', 32); delivery.sha256 = "invalid";
            Require(!OrynGenerationInbox.ValidDelivery(delivery, delivery.id), "invalid checksum rejected"); checks++;
            Require(!OrynGenerationInbox.ValidDelivery(null, ""), "empty delivery rejected"); checks++;
            string path = Path.GetFullPath("RuntimeAssets/Avocado.glb");
            var model = await OrynRuntimeModel.Load(path);
            try
            {
                Require(model.GetComponentsInChildren<MeshRenderer>(true).Length > 0, "external mesh loaded"); checks++;
                Require(Mathf.Abs(Mathf.Max(model.LocalBounds.size.x, Mathf.Max(model.LocalBounds.size.y, model.LocalBounds.size.z)) - 1f) < 0.001f, "model normalized to unit longest edge"); checks++;
                Require(model.LocalBounds.center == Vector3.zero, "model bounds centered"); checks++;
                Require(model.GetComponentsInChildren<Camera>(true).Length == 0 && model.GetComponentsInChildren<Light>(true).Length == 0, "external cameras and lights excluded"); checks++;
                Require(!model.gameObject.activeSelf, "model hidden until workspace adopts it"); checks++;
                Require(!File.Exists("Assets/StreamingAssets/Avocado.glb") && !AssetDatabase.Contains(model.gameObject), "model is not a compiled asset"); checks++;
                model.gameObject.SetActive(true);
                Capture(model);
            }
            finally { UnityEngine.Object.DestroyImmediate(model.gameObject); }
            try { await OrynRuntimeModel.Load(path + ".missing"); throw new Exception("Missing file accepted"); }
            catch (FileNotFoundException) { checks++; }
            try { await OrynRuntimeModel.Load(path, new System.Threading.CancellationToken(true)); throw new Exception("Cancelled import accepted"); }
            catch (OperationCanceledException) { checks++; }
            string invalid = Path.GetTempFileName();
            try
            {
                File.WriteAllBytes(invalid, new byte[24]);
                try { await OrynRuntimeModel.Load(invalid); throw new Exception("Invalid GLB accepted"); }
                catch (InvalidDataException) { checks++; }
                File.WriteAllBytes(invalid, new byte[4]);
                try { await OrynRuntimeModel.Load(invalid); throw new Exception("Truncated GLB accepted"); }
                catch (InvalidDataException) { checks++; }
            }
            finally { File.Delete(invalid); }
            Debug.Log("ORYN_RUNTIME_TESTS_OK checks=" + checks);
        }
        private static void Capture(OrynRuntimeModel model)
        {
            var cameraObject = new GameObject("Runtime model validation camera", typeof(Camera));
            var lightObject = new GameObject("Runtime model validation light", typeof(Light));
            var target = new RenderTexture(900, 900, 24);
            var pixels = new Texture2D(900, 900, TextureFormat.RGB24, false);
            var old = RenderTexture.active;
            try
            {
                var camera = cameraObject.GetComponent<Camera>();
                camera.transform.position = new Vector3(1.2f, 0.7f, -1.7f); camera.transform.LookAt(Vector3.zero);
                camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0.08f, 0.12f, 0.15f);
                camera.fieldOfView = 40; camera.targetTexture = target;
                var light = lightObject.GetComponent<Light>(); light.type = LightType.Directional; light.intensity = 1.5f;
                light.transform.rotation = Quaternion.Euler(35, -25, 0);
                camera.Render(); RenderTexture.active = target;
                pixels.ReadPixels(new Rect(0, 0, 900, 900), 0, 0); pixels.Apply();
                Directory.CreateDirectory("Builds/Preview"); File.WriteAllBytes("Builds/Preview/RuntimeModel.png", pixels.EncodeToPNG());
            }
            finally
            {
                RenderTexture.active = old;
                UnityEngine.Object.DestroyImmediate(cameraObject); UnityEngine.Object.DestroyImmediate(lightObject);
                UnityEngine.Object.DestroyImmediate(target); UnityEngine.Object.DestroyImmediate(pixels);
            }
        }
        private static void Require(bool condition, string reason) { if (!condition) throw new InvalidOperationException("Runtime import test: " + reason); }
    }
}
