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
    public static class OrynWorkspaceSetup
    {
        public const string ScenePath = "Assets/Oryn/Scenes/MilestoneThreeWorkspace.unity";
        public const string BuildPath = "Builds/Android/OrynWorkspace.apk";
        [MenuItem("Oryn/Workspace/Create or Open Quest Scene")]
        public static void OpenScene()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode || !EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            if (!File.Exists(ScenePath)) Generate();
            else EditorSceneManager.OpenScene(ScenePath);
        }
        public static void Generate()
        {
            if (File.Exists(ScenePath)) throw new InvalidOperationException("Workspace scene already exists; open it to edit.");
            if (!AssetDatabase.IsValidFolder("Assets/Oryn/Workspace")) AssetDatabase.CreateFolder("Assets/Oryn", "Workspace");
            Scene source = EditorSceneManager.OpenScene(OrynInteractionSetup.ScenePath, OpenSceneMode.Single);
            if (!EditorSceneManager.SaveScene(source, ScenePath, true)) throw new IOException("Workspace scene copy failed.");
            Scene scene = EditorSceneManager.OpenScene(ScenePath);
            var old = UnityEngine.Object.FindAnyObjectByType<OrynDualInputGrab>();
            var workspace = new GameObject("Oryn Workspace").AddComponent<OrynWorkspace>();
            workspace.Rig = old.Rig;
            workspace.LeftHand = old.LeftHand; workspace.RightHand = old.RightHand;
            workspace.LeftSkeleton = old.LeftSkeleton; workspace.RightSkeleton = old.RightSkeleton;
            workspace.MarkerMaterial = old.GripMarkerMaterial; workspace.MarkerMesh = old.GripMarkerMesh;
            workspace.CubePrefab = ObjectPrefab("Cube", PrimitiveType.Cube);
            workspace.SpherePrefab = ObjectPrefab("Sphere", PrimitiveType.Sphere);
            UnityEngine.Object.DestroyImmediate(old.Cube.gameObject);
            UnityEngine.Object.DestroyImmediate(old.gameObject);
            BuildPanel(workspace);
            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.SaveAssets();
            Validate();
            Debug.Log("ORYN_M3_SCENE_READY");
        }
        private static OrynWorkspaceObject ObjectPrefab(string shape, PrimitiveType primitive)
        {
            string path = "Assets/Oryn/Workspace/" + shape + ".prefab";
            var existing = AssetDatabase.LoadAssetAtPath<OrynWorkspaceObject>(path);
            if (existing != null) return existing;
            GameObject instance = GameObject.CreatePrimitive(primitive);
            try
            {
                instance.name = "Workspace " + shape;
                instance.transform.localScale = Vector3.one * 0.35f;
                var body = instance.AddComponent<Rigidbody>();
                body.isKinematic = true; body.useGravity = false;
                instance.GetComponent<Renderer>().sharedMaterial = AssetDatabase.LoadAssetAtPath<Material>(OrynMilestoneOneSetup.MaterialPath);
                instance.AddComponent<OrynWorkspaceObject>().ShapeName = shape;
                return PrefabUtility.SaveAsPrefabAsset(instance, path).GetComponent<OrynWorkspaceObject>();
            }
            finally { UnityEngine.Object.DestroyImmediate(instance); }
        }
        private static Material PanelMaterial(string name, Color color)
        {
            string path = "Assets/Oryn/Workspace/" + name + ".mat";
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material != null) return material;
            material = new Material(Shader.Find("Unlit/Color")) { name = name, color = color };
            AssetDatabase.CreateAsset(material, path);
            return material;
        }
        private static void BuildPanel(OrynWorkspace workspace)
        {
            workspace.Panel = new GameObject("Workspace Panel").transform;
            workspace.Panel.position = new Vector3(0, 0.95f, 0.55f);
            Material backing = PanelMaterial("Panel", new Color(0.035f, 0.055f, 0.08f));
            Material buttons = PanelMaterial("Button", new Color(0.10f, 0.30f, 0.40f));
            GameObject plate = GameObject.CreatePrimitive(PrimitiveType.Cube);
            plate.name = "Panel Backing";
            plate.transform.SetParent(workspace.Panel, false);
            plate.transform.localScale = new Vector3(0.67f, 0.36f, 0.015f);
            plate.GetComponent<Renderer>().sharedMaterial = backing;
            UnityEngine.Object.DestroyImmediate(plate.GetComponent<Collider>());
            Label(workspace.Panel, "ORYN / WORKSPACE", new Vector3(0, 0.145f, -0.012f), 0.0085f);
            workspace.Status = Label(workspace.Panel, "Grab an object to select it", new Vector3(0, 0.105f, -0.012f), 0.0045f);
            workspace.Buttons = new OrynWorkspaceButton[4];
            string[] labels = { "+ CUBE", "+ SPHERE", "DELETE", "RESET SELECTED" };
            for (int i = 0; i < 4; i++)
            {
                GameObject button = GameObject.CreatePrimitive(PrimitiveType.Cube);
                button.name = labels[i];
                button.transform.SetParent(workspace.Panel, false);
                button.transform.localPosition = new Vector3(i % 2 == 0 ? -0.16f : 0.16f, i < 2 ? 0.035f : -0.065f, -0.017f);
                button.transform.localScale = new Vector3(0.29f, 0.08f, 0.025f);
                button.GetComponent<Renderer>().sharedMaterial = buttons;
                var control = button.AddComponent<OrynWorkspaceButton>();
                control.Action = (OrynWorkspaceButton.Command)i;
                control.Bounds = button.GetComponent<Collider>();
                workspace.Buttons[i] = control;
                // Labels are siblings, so button's non-uniform scale cannot distort the text.
                Label(workspace.Panel, labels[i], button.transform.localPosition + Vector3.back * 0.016f, 0.0045f);
            }
            Label(workspace.Panel, "Near button: grip or pinch  |  Two hands: resize / rotate", new Vector3(0, -0.145f, -0.012f), 0.0036f);
        }
        private static TextMesh Label(Transform parent, string text, Vector3 position, float size)
        {
            var label = new GameObject(text).AddComponent<TextMesh>();
            label.transform.SetParent(parent, false);
            label.transform.localPosition = position;
            label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label.fontSize = 64; label.characterSize = size;
            label.anchor = TextAnchor.MiddleCenter; label.alignment = TextAlignment.Center;
            label.color = Color.white; label.text = text;
            label.GetComponent<Renderer>().sharedMaterial = label.font.material;
            return label;
        }
        public static void Validate()
        {
            var workspace = UnityEngine.Object.FindAnyObjectByType<OrynWorkspace>();
            Require(SceneManager.GetActiveScene().path == ScenePath && workspace != null, "Workspace scene");
            Require(UnityEngine.Object.FindAnyObjectByType<OrynDualInputGrab>() == null, "No single-object driver conflicts");
            Require(workspace.Rig != null && workspace.LeftHand != null && workspace.RightHand != null && workspace.LeftSkeleton != null && workspace.RightSkeleton != null, "Input references");
            Require(workspace.MarkerMesh != null && workspace.MarkerMaterial != null, "Marker assets retained for stripping");
            Require(workspace.CubePrefab != null && workspace.SpherePrefab != null, "Both spawn prefabs");
            Require(workspace.SpherePrefab.GetComponent<SphereCollider>() != null, "Sphere collider included in player");
            Require(workspace.CubePrefab.GetComponent<Rigidbody>().isKinematic && workspace.SpherePrefab.GetComponent<Rigidbody>().isKinematic, "Hovering objects");
            Require(workspace.Panel != null && workspace.Status.font != null && workspace.Buttons.Length >= 4, "Panel and font");
            foreach (var button in workspace.Buttons) Require(button != null && button.Bounds != null, "Button target");
            Require(workspace.Rig.GetComponent<OVRManager>().isInsightPassthroughEnabled && UnityEngine.Object.FindAnyObjectByType<OVRPassthroughLayer>() != null, "Passthrough retained");
            Debug.Log("ORYN_M3_SCENE_VALIDATED");
        }
        public static void BuildAndroid()
        {
            OrynInteractionSetup.RunTests();
            OrynWorkspaceTests.Run();
            OrynMenuTests.Run();
            OrynWristMenuTests.Run();
            OrynRecoveryTests.Run();
            OrynMechanicalTests.Run();
            OrynCommandTests.Run();
            if (!EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android)) throw new InvalidOperationException("Android unavailable.");
            OrynMilestoneOneSetup.ConfigurePlayer();
            OrynMilestoneOneSetup.ConfigureMetaProject();
            var config = OVRProjectConfig.CachedProjectConfig;
            config.handTrackingSupport = OVRProjectConfig.HandTrackingSupport.ControllersAndHands;
            OVRProjectConfig.CommitProjectConfig(config);
            PlayerSettings.productName = "Oryn Workspace";
            PlayerSettings.bundleVersion = "1.14.1"; PlayerSettings.Android.bundleVersionCode = 19;
            if (!File.Exists(ScenePath)) Generate(); else EditorSceneManager.OpenScene(ScenePath);
            var workspace = UnityEngine.Object.FindAnyObjectByType<OrynWorkspace>();
            EnsureRuntimePanel(workspace);
            IncludeModelShaders();
            foreach (TextMesh label in workspace.Panel.GetComponentsInChildren<TextMesh>())
            {
                if (label.text.StartsWith("Near button:")) label.text = "2 fingers: resize  |  3+ fingers: move / rotate";
                label.characterSize = label.text == "ORYN / WORKSPACE" ? 0.0085f : label.text.StartsWith("Near button:") ? 0.0036f : 0.0045f;
                if (label.text.StartsWith("2 fingers:")) label.characterSize = 0.0036f;
                if (label.text.StartsWith("Prayer hands:")) label.characterSize = 0.0036f;
                if (label.text.StartsWith("Controllers:")) label.characterSize = 0.0033f;
                if (label == workspace.Inspector.Details) label.characterSize = 0.0035f;
                if (label.text == "< LABEL" || label.text == "LABEL >" || label.text == "SAVE") label.characterSize = 0.0035f;
            }
            EditorSceneManager.SaveScene(SceneManager.GetActiveScene());
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            Validate();
            CapturePreview();
            Directory.CreateDirectory("Builds/Android");
            BuildReport report = BuildPipeline.BuildPlayer(new BuildPlayerOptions { scenes = new[] { ScenePath }, locationPathName = BuildPath,
                target = BuildTarget.Android, targetGroup = BuildTargetGroup.Android, options = BuildOptions.Development });
            if (report.summary.result != BuildResult.Succeeded) throw new BuildFailedException("Workspace build failed: " + report.summary.result);
            Debug.Log("ORYN_M3_BUILD_OK seconds=" + report.summary.totalTime.TotalSeconds);
        }
        private static void CapturePreview()
        {
            if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) return;
            var workspace = UnityEngine.Object.FindAnyObjectByType<OrynWorkspace>();
            var cameraObject = new GameObject("Temporary Panel Preview", typeof(Camera));
            var cube = (GameObject)PrefabUtility.InstantiatePrefab(workspace.CubePrefab.gameObject);
            var sphere = (GameObject)PrefabUtility.InstantiatePrefab(workspace.SpherePrefab.gameObject);
            var target = new RenderTexture(1400, 1000, 24);
            var capture = new Texture2D(1400, 1000, TextureFormat.RGB24, false);
            RenderTexture previous = RenderTexture.active;
            try
            {
                cube.transform.position = new Vector3(-0.22f, 1.4f, 0.7f);
                sphere.transform.position = new Vector3(0.22f, 1.4f, 0.7f);
                Camera camera = cameraObject.GetComponent<Camera>();
                camera.transform.position = new Vector3(0.32f, 1.2f, -1.3f);
                camera.transform.LookAt(new Vector3(0.32f, 1.16f, 0.55f));
                camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0.12f, 0.16f, 0.20f);
                camera.fieldOfView = 48; camera.targetTexture = target;
                camera.Render(); RenderTexture.active = target;
                capture.ReadPixels(new Rect(0, 0, 1400, 1000), 0, 0); capture.Apply();
                Directory.CreateDirectory("Builds/Preview");
                File.WriteAllBytes("Builds/Preview/Workspace.png", capture.EncodeToPNG());
                string original = workspace.Inspector.Details.text;
                try
                {
                    workspace.Inspector.Details.text = "PART 39 / KNOWLEDGE\nID: 0123456789  Rev 12\nSaved: Flight controller\nStatus: USER ANNOTATION\nSource: local user / unverified\nEvidence / connections: unknown\n\nDraft: Unidentified (clear)\nDraft only - SAVE to apply";
                    camera.Render(); RenderTexture.active = target;
                    capture.ReadPixels(new Rect(0, 0, 1400, 1000), 0, 0); capture.Apply();
                    File.WriteAllBytes("Builds/Preview/PartInspector.png", capture.EncodeToPNG());
                }
                finally { workspace.Inspector.Details.text = original; }
            }
            finally
            {
                RenderTexture.active = previous;
                UnityEngine.Object.DestroyImmediate(cameraObject); UnityEngine.Object.DestroyImmediate(cube); UnityEngine.Object.DestroyImmediate(sphere);
                UnityEngine.Object.DestroyImmediate(target); UnityEngine.Object.DestroyImmediate(capture);
            }
        }
        private static void EnsureRuntimePanel(OrynWorkspace workspace)
        {
            foreach (TextMesh text in workspace.Panel.GetComponentsInChildren<TextMesh>())
                if (text.text == "LOAD MODEL") text.text = "BRING MODEL";
            string[] labels = { "+ CUBE", "+ SPHERE", "DELETE", "RESET SELECTED", "BRING MODEL", "PARTS / WHOLE", "EXPLODE", "ISOLATE / ALL", "ASSEMBLE", "< LABEL", "LABEL >", "SAVE" };
            int[] slots = { 0, 1, 8, 7, 2, 3, 4, 6, 5 };
            int oldCount = workspace.Buttons.Length;
            if (oldCount != 4 && oldCount != 5 && oldCount != 9 && oldCount != 12) throw new InvalidOperationException("Unexpected workspace button layout");
            Array.Resize(ref workspace.Buttons, labels.Length);
            for (int i = 0; i < labels.Length; i++)
            {
                if (i >= oldCount)
                {
                    var button = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    button.transform.SetParent(workspace.Panel, false);
                    button.GetComponent<Renderer>().sharedMaterial = workspace.Buttons[0].GetComponent<Renderer>().sharedMaterial;
                    var control = button.AddComponent<OrynWorkspaceButton>();
                    control.Action = (OrynWorkspaceButton.Command)i; control.Bounds = button.GetComponent<Collider>();
                    workspace.Buttons[i] = control;
                }
                var target = workspace.Buttons[i].transform;
                target.name = labels[i];
                target.localPosition = i < 9 ? new Vector3((slots[i] % 3 - 1) * 0.29f, 0.065f - slots[i] / 3 * 0.10f, -0.017f) :
                    new Vector3(0.79f + (i - 10) * 0.19f, -0.225f, -0.017f);
                target.localScale = new Vector3(i < 9 ? 0.27f : 0.175f, 0.075f, 0.025f);
                TextMesh caption = null;
                foreach (TextMesh text in workspace.Panel.GetComponentsInChildren<TextMesh>()) if (text.text == labels[i]) caption = text;
                if (caption == null) caption = Label(workspace.Panel, labels[i], Vector3.zero, 0.0045f);
                caption.transform.localPosition = target.localPosition + Vector3.back * 0.016f;
            }
            foreach (TextMesh text in workspace.Panel.GetComponentsInChildren<TextMesh>())
            {
                if (text.text == "ORYN / WORKSPACE") text.transform.localPosition = new Vector3(0, 0.185f, -0.012f);
                if (text.text.StartsWith("2 fingers:") || text.text.StartsWith("Near button:")) text.transform.localPosition = new Vector3(0, -0.215f, -0.012f);
            }
            workspace.Status.transform.localPosition = new Vector3(0, 0.135f, -0.012f);
            bool prayerHint = false;
            foreach (TextMesh text in workspace.Panel.GetComponentsInChildren<TextMesh>())
                prayerHint |= text.text.StartsWith("Prayer hands:");
            if (!prayerHint) Label(workspace.Panel, "Prayer hands: hold close, then open to spread", new Vector3(0, -0.255f, -0.012f), 0.0036f);
            bool controllerHint = false;
            foreach (TextMesh text in workspace.Panel.GetComponentsInChildren<TextMesh>()) controllerHint |= text.text.StartsWith("Controllers:");
            if (!controllerHint) Label(workspace.Panel, "Controllers: aim + trigger / A / X | B / Y: bring menu here", new Vector3(0, -0.30f, -0.012f), 0.0033f);
            Transform backing = workspace.Panel.Find("Panel Backing");
            backing.localScale = new Vector3(0.91f, 0.60f, 0.015f); backing.localPosition = new Vector3(0, -0.06f, 0);
            var inspectorBacking = workspace.Panel.Find("Inspector Backing");
            if (inspectorBacking == null)
            {
                var plate = GameObject.CreatePrimitive(PrimitiveType.Cube);
                plate.name = "Inspector Backing"; plate.transform.SetParent(workspace.Panel, false);
                plate.GetComponent<Renderer>().sharedMaterial = backing.GetComponent<Renderer>().sharedMaterial;
                UnityEngine.Object.DestroyImmediate(plate.GetComponent<Collider>()); inspectorBacking = plate.transform;
            }
            inspectorBacking.localPosition = new Vector3(0.79f, -0.035f, 0);
            inspectorBacking.localScale = new Vector3(0.61f, 0.55f, 0.015f);
            if (workspace.Inspector == null) workspace.Inspector = workspace.gameObject.AddComponent<OrynPartInspector>();
            if (workspace.Inspector.Details == null)
                workspace.Inspector.Details = Label(workspace.Panel, "PART KNOWLEDGE\n\nExplode, then grab a piece.\nNo identities are inferred.\n\nLabels are user annotations.", new Vector3(0.79f, 0.03f, -0.012f), 0.0035f);
            workspace.Inspector.Details.richText = false;
            workspace.Inspector.Details.lineSpacing = 1.15f;
        }
        private static void IncludeModelShaders()
        {
            var settings = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/GraphicsSettings.asset")[0]);
            var shaders = settings.FindProperty("m_AlwaysIncludedShaders");
            foreach (string name in new[] { "glTF/PbrMetallicRoughness", "glTF/PbrSpecularGlossiness", "glTF/Unlit" })
            {
                Shader shader = Shader.Find(name);
                if (shader == null) throw new InvalidOperationException("Missing model shader: " + name);
                bool found = false;
                for (int i = 0; i < shaders.arraySize; i++) found |= shaders.GetArrayElementAtIndex(i).objectReferenceValue == shader;
                if (found) continue;
                int index = shaders.arraySize; shaders.InsertArrayElementAtIndex(index); shaders.GetArrayElementAtIndex(index).objectReferenceValue = shader;
            }
            settings.ApplyModifiedPropertiesWithoutUndo();
        }
        private static void Require(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
    }
}
