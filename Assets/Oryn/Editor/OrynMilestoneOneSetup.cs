using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace Oryn.Editor
{
    /// <summary>
    /// Creates and builds the smallest Oryn Quest passthrough scene.
    /// Run from the command line with -executeMethod Oryn.Editor.OrynMilestoneOneSetup.Configure
    /// or -executeMethod Oryn.Editor.OrynMilestoneOneSetup.ConfigureAndBuildAndroid.
    /// </summary>
    public static class OrynMilestoneOneSetup
    {
        public const string ScenePath = "Assets/Oryn/Scenes/MilestoneOnePassthrough.unity";
        public const string MaterialPath = "Assets/Oryn/Materials/MilestoneCube.mat";
        public const string DefaultBuildPath = "Builds/Android/OrynMilestoneOne.apk";

        private const string CameraRigPath = "Packages/com.meta.xr.sdk.core/Prefabs/OVRCameraRig.prefab";
        private const string ApplicationId = "com.oryn.milestoneone";

        public static void Configure()
        {
            EnsureFolder("Assets/Oryn");
            EnsureFolder("Assets/Oryn/Editor");
            EnsureFolder("Assets/Oryn/Materials");
            EnsureFolder("Assets/Oryn/Scenes");

            if (!EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android))
            {
                throw new InvalidOperationException(
                    "Unity could not switch to Android. Verify Android Build Support is installed for this editor.");
            }

            ConfigurePlayer();
            ConfigureMetaProject();
            CreateScene();

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"ORYN_M1_SETUP_OK scene={ScenePath} applicationId={ApplicationId}");
        }

        public static void ConfigureAndBuildAndroid()
        {
            Configure();
            BuildAndroid();
        }

        // Build authored content without regenerating or overwriting the Quest scene.
        public static void BuildAndroid()
        {
            if (!EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android))
                throw new InvalidOperationException("Could not select the Android build target.");
            ConfigurePlayer();
            ConfigureMetaProject();
            AssetDatabase.SaveAssets();
            Validate();

            string buildPath = GetCommandLineValue("-orynBuildPath") ?? DefaultBuildPath;
            string buildDirectory = Path.GetDirectoryName(buildPath);
            if (!string.IsNullOrEmpty(buildDirectory))
            {
                Directory.CreateDirectory(buildDirectory);
            }

            var options = new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = buildPath,
                target = BuildTarget.Android,
                targetGroup = BuildTargetGroup.Android,
                options = BuildOptions.Development
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            BuildSummary summary = report.summary;
            if (summary.result != BuildResult.Succeeded)
            {
                throw new BuildFailedException(
                    $"Oryn Milestone 1 Android build failed: {summary.result}, errors={summary.totalErrors}");
            }

            Debug.Log(
                $"ORYN_M1_BUILD_OK path={Path.GetFullPath(buildPath)} bytes={summary.totalSize} " +
                $"duration={summary.totalTime.TotalSeconds:F1}s warnings={summary.totalWarnings}");
        }

        public static void Validate()
        {
            if (!File.Exists(ScenePath))
            {
                throw new FileNotFoundException("The Milestone 1 scene has not been generated.", ScenePath);
            }

            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);

            GameObject cameraRig = GameObject.Find("OVRCameraRig");
            Require(cameraRig != null, "OVRCameraRig is present");

            OVRManager manager = cameraRig.GetComponent<OVRManager>();
            Require(manager != null, "OVRManager is present on OVRCameraRig");
            Require(manager.isInsightPassthroughEnabled, "passthrough is enabled on OVRManager");
            Require(manager.trackingOriginType == OVRManager.TrackingOrigin.Stage, "tracking origin is Stage");

            Camera centerCamera = cameraRig.transform.Find("TrackingSpace/CenterEyeAnchor")?.GetComponent<Camera>();
            Require(centerCamera != null, "CenterEyeAnchor camera is present");
            Require(centerCamera.clearFlags == CameraClearFlags.SolidColor, "camera uses a solid-color clear");
            Require(Mathf.Approximately(centerCamera.backgroundColor.a, 0f), "camera background alpha is zero");

            GameObject passthrough = GameObject.Find("Passthrough");
            Require(passthrough != null && passthrough.GetComponent<OVRPassthroughLayer>() != null,
                "OVRPassthroughLayer is present");

            GameObject cube = GameObject.Find("MilestoneCube");
            Require(cube != null, "MilestoneCube is present");
            Require(cube.GetComponent<MeshRenderer>() != null, "MilestoneCube is renderable");
            Require(cube.GetComponent<BoxCollider>() != null, "MilestoneCube has its default collider");

            OVRProjectConfig config = OVRProjectConfig.CachedProjectConfig;
            Require(config != null, "Meta XR project configuration is present");
            Require(config.insightPassthroughSupport == OVRProjectConfig.FeatureSupport.Supported,
                "passthrough capability is supported");
            Require(config.targetDeviceTypes.Count == 1 &&
                    config.targetDeviceTypes.Contains(OVRProjectConfig.DeviceType.Quest2),
                "Quest 2 is the only declared target device for this physical milestone");

            Require(EditorUserBuildSettings.activeBuildTarget == BuildTarget.Android,
                "Android is the active build target");
            Require(PlayerSettings.GetScriptingBackend(NamedBuildTarget.Android) == ScriptingImplementation.IL2CPP,
                "Android scripting backend is IL2CPP");
            Require(PlayerSettings.Android.targetArchitectures == AndroidArchitecture.ARM64,
                "Android target architecture is ARM64");
            GraphicsDeviceType[] graphicsApis = PlayerSettings.GetGraphicsAPIs(BuildTarget.Android);
            Require(graphicsApis.Length == 1 && graphicsApis[0] == GraphicsDeviceType.Vulkan,
                "Vulkan is the Android graphics API");
            Require(EditorBuildSettings.scenes.Length == 1 && EditorBuildSettings.scenes[0].path == ScenePath &&
                    EditorBuildSettings.scenes[0].enabled,
                "MilestoneOnePassthrough is the only enabled build scene");

            Debug.Log("ORYN_M1_VALIDATION_OK checks=17");
        }

        internal static void ConfigurePlayer()
        {
            PlayerSettings.companyName = "Oryn";
            PlayerSettings.productName = "Oryn Milestone 1";
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android, ApplicationId);
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel32;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel34;
            PlayerSettings.SetGraphicsAPIs(BuildTarget.Android, new[] { GraphicsDeviceType.Vulkan });

            EditorUserBuildSettings.androidBuildSystem = AndroidBuildSystem.Gradle;
            EditorUserBuildSettings.buildAppBundle = false;
            EditorUserBuildSettings.exportAsGoogleAndroidProject = false;
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        }

        internal static void ConfigureMetaProject()
        {
            OVRProjectConfig config = OVRProjectConfig.CachedProjectConfig;
            if (config == null)
            {
                throw new InvalidOperationException("Meta XR project configuration could not be loaded.");
            }

            config.insightPassthroughSupport = OVRProjectConfig.FeatureSupport.Supported;
            config.targetDeviceTypes.Clear();
            config.targetDeviceTypes.Add(OVRProjectConfig.DeviceType.Quest2);
            OVRProjectConfig.CommitProjectConfig(config);
        }

        private static void CreateScene()
        {
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            GameObject cameraRigPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(CameraRigPath);
            if (cameraRigPrefab == null)
            {
                throw new FileNotFoundException("Meta XR OVRCameraRig prefab was not found.", CameraRigPath);
            }

            var cameraRig = (GameObject)PrefabUtility.InstantiatePrefab(cameraRigPrefab, scene);
            cameraRig.name = "OVRCameraRig";

            OVRManager manager = cameraRig.GetComponent<OVRManager>();
            if (manager == null)
            {
                throw new InvalidOperationException("The OVRCameraRig prefab does not contain OVRManager.");
            }

            manager.trackingOriginType = OVRManager.TrackingOrigin.Stage;
            manager.isInsightPassthroughEnabled = true;

            foreach (Camera camera in cameraRig.GetComponentsInChildren<Camera>(true))
            {
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = Color.clear;
            }

            var passthrough = new GameObject("Passthrough");
            passthrough.AddComponent<OVRPassthroughLayer>();

            GameObject cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cube.name = "MilestoneCube";
            cube.transform.SetPositionAndRotation(new Vector3(0f, 1.35f, 1.75f), Quaternion.identity);
            cube.transform.localScale = Vector3.one * 0.35f;
            cube.GetComponent<Renderer>().sharedMaterial = GetOrCreateCubeMaterial();

            var lightObject = new GameObject("Directional Light");
            Light light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.2f;
            lightObject.transform.rotation = Quaternion.Euler(45f, -30f, 0f);

            RenderSettings.skybox = null;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.35f, 0.35f, 0.35f);

            if (!EditorSceneManager.SaveScene(scene, ScenePath))
            {
                throw new IOException($"Failed to save scene at {ScenePath}.");
            }

            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        }

        private static Material GetOrCreateCubeMaterial()
        {
            Material existing = AssetDatabase.LoadAssetAtPath<Material>(MaterialPath);
            if (existing != null)
            {
                return existing;
            }

            Shader shader = Shader.Find("Standard");
            if (shader == null)
            {
                throw new InvalidOperationException("Unity's Standard shader could not be found.");
            }

            var material = new Material(shader)
            {
                name = "MilestoneCube",
                color = new Color(0.05f, 0.65f, 1f, 1f)
            };
            AssetDatabase.CreateAsset(material, MaterialPath);
            return material;
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path))
            {
                return;
            }

            string parent = Path.GetDirectoryName(path)?.Replace('\\', '/');
            string name = Path.GetFileName(path);
            if (string.IsNullOrEmpty(parent) || string.IsNullOrEmpty(name))
            {
                throw new ArgumentException($"Invalid Unity folder path: {path}");
            }

            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, name);
        }

        private static string GetCommandLineValue(string key)
        {
            string[] args = Environment.GetCommandLineArgs();
            for (int index = 0; index < args.Length - 1; index++)
            {
                if (string.Equals(args[index], key, StringComparison.Ordinal))
                {
                    return args[index + 1];
                }
            }

            return null;
        }

        private static void Require(bool condition, string description)
        {
            if (!condition)
            {
                throw new InvalidOperationException($"Oryn Milestone 1 validation failed: {description}.");
            }
        }
    }
}
