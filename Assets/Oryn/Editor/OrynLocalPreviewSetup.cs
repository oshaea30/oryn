using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.XR.Management;
using UnityEditor.XR.Management;
using Oryn.Preview;

namespace Oryn.Editor
{
    [InitializeOnLoad]
    public static class OrynLocalPreviewSetup
    {
        public const string PreviewScene = "Assets/Oryn/Scenes/LocalPreview.unity";
        private const string VerificationKey = "Oryn.VerifyDesktop";
        private static double started;
        private static bool runtimeError;

        static OrynLocalPreviewSetup()
        {
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
        }

        [MenuItem("Oryn/Local Preview/Open and Play")]
        public static void OpenAndPlay()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) return;
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Generate();
            EditorApplication.ExecuteMenuItem("Window/General/Game");
            EditorApplication.isPlaying = true;
        }

        [MenuItem("Oryn/Local Preview/Recreate from Quest Scene")]
        private static void GenerateFromMenu()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) return;
            if (EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) Generate();
        }

        // Batch entry point; intentionally does not regenerate the original Quest scene.
        public static void Generate()
        {
            RepairOpenXRSettings();
            if (!File.Exists(OrynMilestoneOneSetup.ScenePath))
                throw new FileNotFoundException("The Oryn Quest scene is missing.", OrynMilestoneOneSetup.ScenePath);
            if (!EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Standalone, BuildTarget.StandaloneOSX))
                throw new InvalidOperationException("Could not select the Mac preview target.");
            XRGeneralSettings desktopXR = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(BuildTargetGroup.Standalone);
            if (desktopXR != null)
            {
                desktopXR.InitManagerOnStart = false;
                EditorUtility.SetDirty(desktopXR);
            }
            Scene source = EditorSceneManager.OpenScene(OrynMilestoneOneSetup.ScenePath, OpenSceneMode.Single);
            if (!EditorSceneManager.SaveScene(source, PreviewScene, true))
                throw new IOException("Could not create the preview scene copy.");
            Scene scene = EditorSceneManager.OpenScene(PreviewScene, OpenSceneMode.Single);
            foreach (GameObject root in scene.GetRootGameObjects())
                if (root.GetComponentInChildren<OVRManager>(true) != null ||
                    root.GetComponentInChildren<OVRPassthroughLayer>(true) != null)
                    UnityEngine.Object.DestroyImmediate(root);

            var cameraObject = new GameObject("Desktop Preview Camera", typeof(Camera), typeof(AudioListener));
            Camera camera = cameraObject.GetComponent<Camera>();
            cameraObject.tag = "MainCamera";
            cameraObject.transform.SetPositionAndRotation(new Vector3(1.15f, 1.65f, -0.65f),
                Quaternion.LookRotation(new Vector3(0f, 1.35f, 1.75f) - new Vector3(1.15f, 1.65f, -0.65f)));
            camera.fieldOfView = 62f;
            camera.nearClipPlane = 0.05f;
            camera.farClipPlane = 40f;
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.06f, 0.08f, 0.10f);
            cameraObject.AddComponent<OrynDesktopCamera>();

            if (!AssetDatabase.IsValidFolder("Assets/Oryn/Preview/Materials"))
                AssetDatabase.CreateFolder("Assets/Oryn/Preview", "Materials");
            Material floor = Material("Floor", new Color(0.22f, 0.25f, 0.28f));
            Material wall = Material("Wall", new Color(0.42f, 0.46f, 0.48f));
            Material lines = Material("Grid", new Color(0.30f, 0.35f, 0.38f));
            GameObject room = new GameObject("Synthetic Room - Preview Only");
            Block("Floor", new Vector3(0,-0.06f,1.5f), new Vector3(6,0.1f,7), floor, room.transform);
            Block("Back wall", new Vector3(0,1.5f,5), new Vector3(6,3,0.1f), wall, room.transform);
            Block("Left wall", new Vector3(-3,1.5f,1.5f), new Vector3(0.1f,3,7), wall, room.transform);
            Block("Right wall", new Vector3(3,1.5f,1.5f), new Vector3(0.1f,3,7), wall, room.transform);
            for (int x = -3; x <= 3; x++)
                Block("Metre grid X " + x, new Vector3(x,0,1.5f), new Vector3(0.012f,0.006f,7), lines, room.transform);
            for (int z = -2; z <= 5; z++)
                Block("Metre grid Z " + z, new Vector3(0,0,z), new Vector3(6,0.006f,0.012f), lines, room.transform);
            RenderSettings.skybox = null;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.55f,0.58f,0.62f);
            if (!EditorSceneManager.SaveScene(scene, PreviewScene)) throw new IOException("Could not save preview.");
            AssetDatabase.SaveAssets();
            Validate();
            Debug.Log("ORYN_LOCAL_PREVIEW_GENERATED " + PreviewScene);
        }

        private static Material Material(string name, Color color)
        {
            string path = "Assets/Oryn/Preview/Materials/" + name + ".mat";
            Material material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material != null) return material;
            Shader shader = Shader.Find("Standard");
            if (shader == null) throw new InvalidOperationException("Standard shader is unavailable.");
            material = new Material(shader) { name = name, color = color };
            material.SetFloat("_Glossiness", 0.15f);
            AssetDatabase.CreateAsset(material, path);
            return material;
        }

        private static void Block(string name, Vector3 position, Vector3 scale, Material material, Transform parent)
        {
            GameObject block = GameObject.CreatePrimitive(PrimitiveType.Cube);
            block.name = name;
            block.transform.SetParent(parent);
            block.transform.position = position;
            block.transform.localScale = scale;
            block.GetComponent<Renderer>().sharedMaterial = material;
        }

        public static void Validate()
        {
            if (SceneManager.GetActiveScene().path != PreviewScene) throw new InvalidOperationException("Wrong preview scene.");
            if (UnityEngine.Object.FindAnyObjectByType<OVRManager>() != null ||
                UnityEngine.Object.FindAnyObjectByType<OVRPassthroughLayer>() != null)
                throw new InvalidOperationException("Desktop preview contains a headset component.");
            if (Camera.main == null || Camera.main.GetComponent<OrynDesktopCamera>() == null)
                throw new InvalidOperationException("Desktop navigation camera is missing.");
            if (GameObject.Find("MilestoneCube")?.GetComponent<MeshRenderer>() == null)
                throw new InvalidOperationException("The source cube is missing.");
            foreach (EditorBuildSettingsScene scene in EditorBuildSettings.scenes)
                if (scene.enabled && scene.path == PreviewScene)
                    throw new InvalidOperationException("Desktop preview must not enter the Quest build scene list.");
            Debug.Log("ORYN_LOCAL_PREVIEW_VALIDATION_OK");
        }

        // Run with -batchmode -executeMethod ...VerifyPlayMode, WITHOUT -quit or -nographics.
        public static void PrepareAndVerify()
        {
            RepairOpenXRSettings();
            OrynMilestoneOneSetup.Configure();
            OrynMilestoneOneSetup.Validate();
            VerifyPlayMode();
        }

        public static void VerifyPlayMode()
        {
            Generate();
            SessionState.SetBool(VerificationKey, true);
            EditorApplication.isPlaying = true;
        }

        // Unity's newer OpenXR package assumes feature references are non-null.
        // Drop only missing references left by the sample's older package version;
        // preserve every valid feature and its enabled state, then let OpenXR add new types.
        [MenuItem("Oryn/Tools/Repair Missing OpenXR Feature References")]
        public static void RepairOpenXRSettings()
        {
            const string path = "Assets/XR/Settings/OpenXR Package Settings.asset";
            int removed = 0;
            foreach (UnityEngine.Object asset in AssetDatabase.LoadAllAssetsAtPath(path))
            {
                if (asset == null) continue;
                var serialized = new SerializedObject(asset);
                SerializedProperty features = serialized.FindProperty("features");
                if (features == null || !features.isArray) continue;
                for (int i = features.arraySize - 1; i >= 0; i--)
                {
                    if (features.GetArrayElementAtIndex(i).objectReferenceValue != null) continue;
                    features.DeleteArrayElementAtIndex(i);
                    removed++;
                }
                serialized.ApplyModifiedPropertiesWithoutUndo();
            }
            if (removed == 0) return;
            AssetDatabase.SaveAssets();
            UnityEditor.XR.OpenXR.Features.FeatureHelpers.RefreshFeatures(BuildTargetGroup.Standalone);
            UnityEditor.XR.OpenXR.Features.FeatureHelpers.RefreshFeatures(BuildTargetGroup.Android);
            AssetDatabase.SaveAssets();
            Debug.Log("ORYN_OPENXR_REPAIRED missingReferences=" + removed);
        }

        private static void OnPlayModeChanged(PlayModeStateChange state)
        {
            if (!SessionState.GetBool(VerificationKey, false) || state != PlayModeStateChange.EnteredPlayMode) return;
            runtimeError = false;
            started = EditorApplication.timeSinceStartup;
            Application.logMessageReceived += OnLog;
            EditorApplication.update += VerifyFrame;
        }

        private static void OnLog(string message, string trace, LogType type)
        {
            if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert) runtimeError = true;
        }

        private static void VerifyFrame()
        {
            if (EditorApplication.timeSinceStartup - started < 3) return;
            EditorApplication.update -= VerifyFrame;
            SessionState.SetBool(VerificationKey, false);
            try
            {
                Validate();
                if (runtimeError) throw new InvalidOperationException("Runtime errors occurred in preview.");
                Camera camera = Camera.main;
                OrynDesktopCamera controller = camera.GetComponent<OrynDesktopCamera>();
                Vector3 start = camera.transform.position;
                Transform cube = GameObject.Find("MilestoneCube").transform;
                Vector3 cubePosition = cube.position;
                Vector3 before = camera.WorldToViewportPoint(cubePosition);
                controller.Navigate(Vector3.right, Vector2.zero, false, 0.25f);
                Vector3 after = camera.WorldToViewportPoint(cubePosition);
                if (Vector3.Distance(start, camera.transform.position) < 0.1f || Mathf.Abs(before.x - after.x) < 0.01f)
                    throw new InvalidOperationException("Camera movement/parallax check failed.");
                if (cube.position != cubePosition) throw new InvalidOperationException("Navigation moved the object.");
                controller.Navigate(Vector3.zero, new Vector2(15f, 10f), false, 0.1f);
                controller.ResetView();
                if (Vector3.Distance(start, camera.transform.position) > 0.001f)
                    throw new InvalidOperationException("Camera reset failed.");
                Directory.CreateDirectory("Builds/Preview");
                RenderTexture target = new RenderTexture(1280, 800, 24);
                RenderTexture previous = RenderTexture.active;
                camera.targetTexture = target;
                camera.Render();
                RenderTexture.active = target;
                Texture2D capture = new Texture2D(1280, 800, TextureFormat.RGB24, false);
                capture.ReadPixels(new Rect(0,0,1280,800),0,0);
                capture.Apply();
                File.WriteAllBytes("Builds/Preview/LocalPreview.png", capture.EncodeToPNG());
                RenderTexture.active = previous;
                camera.targetTexture = null;
                UnityEngine.Object.Destroy(capture);
                UnityEngine.Object.Destroy(target);
                Debug.Log("ORYN_LOCAL_PLAYMODE_OK navigation=pass parallax=pass reset=pass cubeStable=pass screenshot=Builds/Preview/LocalPreview.png");
                Application.logMessageReceived -= OnLog;
                EditorApplication.Exit(0);
            }
            catch (Exception exception)
            {
                Application.logMessageReceived -= OnLog;
                Debug.LogException(exception);
                EditorApplication.Exit(1);
            }
        }
    }
}
