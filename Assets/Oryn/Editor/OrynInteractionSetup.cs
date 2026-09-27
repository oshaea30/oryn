using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Oryn.Interaction;

namespace Oryn.Editor
{
    public static class OrynInteractionSetup
    {
        public const string ScenePath = "Assets/Oryn/Scenes/MilestoneTwoInteraction.unity";
        public const string BuildPath = "Builds/Android/OrynInteraction.apk";
        private static int checks;

        [MenuItem("Oryn/Interaction/Create or Open Quest Scene")]
        public static void OpenScene()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) return;
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            if (!File.Exists(ScenePath)) Generate();
            else EditorSceneManager.OpenScene(ScenePath);
        }

        // Explicitly creates the second milestone; never edits the working M1 scene.
        public static void Generate()
        {
            if (File.Exists(ScenePath)) throw new InvalidOperationException("Interaction scene already exists; open it instead of regenerating it.");
            Scene source = EditorSceneManager.OpenScene(OrynMilestoneOneSetup.ScenePath, OpenSceneMode.Single);
            if (!EditorSceneManager.SaveScene(source, ScenePath, true)) throw new IOException("Scene copy failed.");
            Scene scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            OVRCameraRig rig = UnityEngine.Object.FindAnyObjectByType<OVRCameraRig>();
            GameObject cube = GameObject.Find("MilestoneCube");
            cube.transform.position = new Vector3(0f, 1.2f, 0.65f);
            Rigidbody body = cube.AddComponent<Rigidbody>();
            body.isKinematic = true;
            body.useGravity = false;
            var driver = new GameObject("Oryn Dual Input Interaction").AddComponent<OrynDualInputGrab>();
            driver.Rig = rig;
            driver.Cube = cube.transform;
            driver.LeftHand = CreateHand(rig.transform.Find("TrackingSpace/LeftHandAnchor"), true);
            driver.RightHand = CreateHand(rig.transform.Find("TrackingSpace/RightHandAnchor"), false);
            driver.LeftSkeleton = driver.LeftHand.GetComponent<OVRSkeleton>();
            driver.RightSkeleton = driver.RightHand.GetComponent<OVRSkeleton>();
            const string materialPath = "Assets/Oryn/Materials/GripMarker.mat";
            Material marker = AssetDatabase.LoadAssetAtPath<Material>(materialPath);
            if (marker == null)
            {
                marker = new Material(Shader.Find("Unlit/Color")) { name = "GripMarker", color = Color.white };
                AssetDatabase.CreateAsset(marker, materialPath);
            }
            driver.GripMarkerMaterial = marker;
            EnsureMarkerMesh(driver);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new IOException("Interaction scene save failed.");
            AssetDatabase.SaveAssets();
            Validate();
            Debug.Log("ORYN_M2_SCENE_READY " + ScenePath);
        }

        private static OVRHand CreateHand(Transform anchor, bool left)
        {
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>("Packages/com.meta.xr.sdk.core/Prefabs/OVRHandPrefab.prefab");
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab, anchor);
            instance.name = left ? "Oryn Left Tracked Hand" : "Oryn Right Tracked Hand";
            instance.transform.SetLocalPositionAndRotation(Vector3.zero, Quaternion.identity);
            OVRHand hand = instance.GetComponent<OVRHand>();
            SetInt(hand, "HandType", (int)(left ? OVRHand.Hand.HandLeft : OVRHand.Hand.HandRight));
            // Match the project's skeleton version instead of assuming legacy OVR bone IDs.
            SetInt(instance.GetComponent<OVRSkeleton>(), "_skeletonType",
                (int)((OVRSkeleton.IOVRSkeletonDataProvider)hand).GetSkeletonType());
            SetInt(instance.GetComponent<OVRMesh>(), "_meshType", (int)((OVRMesh.IOVRMeshDataProvider)hand).GetMeshType());
            return hand;
        }

        private static void SetInt(UnityEngine.Object target, string property, int value)
        {
            var serialized = new SerializedObject(target);
            var field = serialized.FindProperty(property);
            if (field == null) throw new InvalidOperationException("Missing Meta property: " + property);
            field.intValue = value;
            serialized.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void EnsureMarkerMesh(OrynDualInputGrab driver)
        {
            if (driver.GripMarkerMesh != null) return;
            // Serialize the mesh so player stripping cannot remove a runtime primitive dependency.
            GameObject probe = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            driver.GripMarkerMesh = probe.GetComponent<MeshFilter>().sharedMesh;
            UnityEngine.Object.DestroyImmediate(probe);
            EditorUtility.SetDirty(driver);
        }

        public static void Validate()
        {
            var driver = UnityEngine.Object.FindAnyObjectByType<OrynDualInputGrab>();
            Check(SceneManager.GetActiveScene().path == ScenePath, "Correct scene");
            Check(driver != null && driver.Rig != null && driver.Cube != null, "Interaction references");
            Check(driver.LeftHand != null && driver.RightHand != null && driver.LeftSkeleton != null && driver.RightSkeleton != null,
                "Both tracked hands");
            Check(driver.LeftHand != driver.RightHand && driver.GripMarkerMaterial != null, "Distinct hands and included marker shader");
            Check(driver.GripMarkerMesh != null, "Included marker mesh without runtime collider dependency");
            Check(driver.LeftSkeleton.GetSkeletonType() == ((OVRSkeleton.IOVRSkeletonDataProvider)driver.LeftHand).GetSkeletonType(), "Left skeleton version");
            Check(driver.RightSkeleton.GetSkeletonType() == ((OVRSkeleton.IOVRSkeletonDataProvider)driver.RightHand).GetSkeletonType(), "Right skeleton version");
            Check(driver.Cube.GetComponent<Rigidbody>().isKinematic && !driver.Cube.GetComponent<Rigidbody>().useGravity, "Release stays suspended");
            Check(driver.Rig.GetComponent<OVRManager>().isInsightPassthroughEnabled, "Passthrough retained");
            Check(UnityEngine.Object.FindAnyObjectByType<OVRPassthroughLayer>() != null, "Passthrough layer retained");
            Debug.Log("ORYN_M2_SCENE_VALIDATED");
        }

        public static void BuildAndroid()
        {
            RunTests();
            if (!EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android))
                throw new InvalidOperationException("Android target unavailable.");
            OrynLocalPreviewSetup.RepairOpenXRSettings();
            OrynMilestoneOneSetup.ConfigurePlayer();
            OrynMilestoneOneSetup.ConfigureMetaProject();
            var config = OVRProjectConfig.CachedProjectConfig;
            config.handTrackingSupport = OVRProjectConfig.HandTrackingSupport.ControllersAndHands;
            OVRProjectConfig.CommitProjectConfig(config);
            PlayerSettings.productName = "Oryn Interaction";
            PlayerSettings.bundleVersion = "1.1";
            PlayerSettings.Android.bundleVersionCode = 2;
            if (!File.Exists(ScenePath)) Generate();
            else EditorSceneManager.OpenScene(ScenePath);
            EnsureMarkerMesh(UnityEngine.Object.FindAnyObjectByType<OrynDualInputGrab>());
            EditorSceneManager.SaveScene(SceneManager.GetActiveScene());
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Validate();
            Directory.CreateDirectory("Builds/Android");
            BuildReport report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { ScenePath }, locationPathName = BuildPath,
                target = BuildTarget.Android, targetGroup = BuildTargetGroup.Android, options = BuildOptions.Development
            });
            if (report.summary.result != BuildResult.Succeeded)
                throw new BuildFailedException("Interaction build failed: " + report.summary.result);
            Debug.Log("ORYN_M2_BUILD_OK path=" + BuildPath + " duration=" + report.summary.totalTime.TotalSeconds);
        }

        [MenuItem("Oryn/Interaction/Run Grab Logic Checks")]
        public static void RunTests()
        {
            checks = 0;
            Pose origin = new Pose(new Vector3(0f, 1f, 1f), Quaternion.identity);
            for (int source = 0; source < 4; source++)
            {
                var state = new OrynGrabState(origin);
                Pose grip = new Pose(origin.position + Vector3.right * 0.1f, Quaternion.identity);
                state.UpdateInput(source, true, 1f, grip, true);
                Check(state.Owner == -1, "Must open grip before first grab");
                state.UpdateInput(source, true, 0f, grip, true);
                state.UpdateInput(source, true, 1f, grip, true);
                Check(state.Owner == source, "Every hand/controller source can grab");
                Check(Vector3.Distance(state.ObjectPose.position, origin.position) < 0.001f, "No snap on acquire");
                Pose moved = new Pose(grip.position + Vector3.up, Quaternion.Euler(0f, 90f, 0f));
                state.UpdateInput(source, true, 0.5f, moved, false);
                Check(state.Owner == source, "Hysteresis holds beyond proximity volume");
                Check(Vector3.Distance(state.ObjectPose.position, moved.position + moved.rotation * Vector3.left * 0.1f) < 0.001f,
                    "Translation and rotation preserve relative grip");
                Check(Quaternion.Angle(state.ObjectPose.rotation, moved.rotation) < 0.01f, "Object rotates with grip");
                int other = (source + 1) % 4;
                state.UpdateInput(other, true, 0f, moved, true);
                state.UpdateInput(other, true, 1f, moved, true);
                Check(state.Owner == source, "Second source cannot steal object");
                Pose released = state.ObjectPose;
                state.UpdateInput(source, true, 0f, moved, true);
                state.UpdateInput(source, true, 0f, origin, true);
                Check(state.Owner == -1 && state.ObjectPose.position == released.position, "Release remains stationary");
                state.UpdateInput(source, true, 1f, moved, false);
                Check(state.Owner == -1, "No distance grab");
                state.UpdateInput(source, true, 1f, moved, true);
                Check(state.Owner == -1, "Entering while pinched requires release and repinch");
                state.UpdateInput(source, true, 0f, moved, true);
                state.UpdateInput(source, true, 1f, moved, true);
                state.UpdateInput(source, false, 1f, origin, true);
                Check(state.Owner == -1 && state.ObjectPose.position == released.position, "Tracking loss freezes object");
                state.UpdateInput(source, true, 1f, origin, true);
                Check(state.Owner == -1, "Tracking recovery cannot auto-grab");
                state.UpdateInput(other, true, 0f, moved, true);
                state.UpdateInput(other, true, 1f, moved, true);
                Check(state.Owner == other, "Another input can acquire after release");
                state.ReleaseAll();
                Check(state.Owner == -1, "Pause/focus loss releases ownership");
                state.UpdateInput(other, true, 1f, moved, true);
                Check(state.Owner == -1, "Resume requires fresh gesture");
                state.Reset(origin);
                Check(state.Owner == -1 && state.ObjectPose.position == origin.position, "Reset releases and restores pose");
            }
            GameObject probe = GameObject.CreatePrimitive(PrimitiveType.Cube);
            try
            {
                probe.transform.position = new Vector3(10f, 10f, 10f);
                probe.transform.localScale = Vector3.one * 0.35f;
                Physics.SyncTransforms();
                Check(OrynDualInputGrab.IsNear(probe.GetComponent<Collider>(), probe.transform.position + Vector3.right * 0.25f), "Near surface accepted");
                Check(!OrynDualInputGrab.IsNear(probe.GetComponent<Collider>(), probe.transform.position + Vector3.right * 0.4f), "Distant surface rejected");
            }
            finally { UnityEngine.Object.DestroyImmediate(probe); }
            Debug.Log("ORYN_M2_TESTS_OK checks=" + checks);
        }

        private static void Check(bool condition, string description)
        {
            if (!condition) throw new InvalidOperationException("Oryn interaction check failed: " + description);
            checks++;
        }
    }
}
