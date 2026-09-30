using System.Collections.Generic;
using UnityEngine;

namespace Oryn.Interaction
{
    [DefaultExecutionOrder(1000)]
    public sealed class OrynWorkspace : MonoBehaviour
    {
        public OVRCameraRig Rig;
        public OVRHand LeftHand, RightHand;
        public OVRSkeleton LeftSkeleton, RightSkeleton;
        public Material MarkerMaterial;
        public Mesh MarkerMesh;
        public OrynWorkspaceObject CubePrefab, SpherePrefab;
        public Transform Panel;
        public TextMesh Status;
        public OrynPartInspector Inspector;
        public OrynWorkspaceButton[] Buttons;
        public const int ObjectLimit = 12;
        private readonly List<OrynWorkspaceObject> objects = new List<OrynWorkspaceObject>();
        private readonly OrynWorkspaceObject[] held = new OrynWorkspaceObject[4];
        private readonly OrynPressLatch[] presses = { new OrynPressLatch(), new OrynPressLatch(), new OrynPressLatch(), new OrynPressLatch() };
        private readonly Renderer[] markers = new Renderer[4];
        private readonly LineRenderer[] menuRays = new LineRenderer[2];
        private readonly OrynWorkspaceButton[] hoveredButtons = new OrynWorkspaceButton[4];
        private readonly OrynWorkspaceObject[] hoveredObjects = new OrynWorkspaceObject[4];
        private readonly OrynTrackedInput input = new OrynTrackedInput();
        private readonly Pose[] gripPoses = new Pose[4];
        private readonly Vector3[] gripOffsets = new Vector3[4];
        private readonly Vector3[] surfaceAnchors = new Vector3[4];
        private readonly OrynContactLatch[] contactPresses = { new OrynContactLatch(), new OrynContactLatch(), new OrynContactLatch(), new OrynContactLatch() };
        private readonly OrynWorkspaceObject[] touched = new OrynWorkspaceObject[4];
        private readonly Vector3[] touchPoints = new Vector3[4];
        private readonly float[] touchTimes = { -1, -1, -1, -1 };
        private readonly Vector3[][] previousContacts = { new Vector3[6], new Vector3[6] };
        private readonly bool[][] previousValid = { new bool[6], new bool[6] };
        private readonly OrynContactHandVisual[] handVisuals = new OrynContactHandVisual[2];
        private OrynWorkspaceObject selected;
        private bool initialized;
        private OrynWristMenu wristMenu;
        private int nextNumber = 1;
        private string previousStatus;
        private float confirmationUntil;
        private bool confirmDelete;
        private int confirmationSource;
        private int confirmationFrame;
        private float noticeUntil;
        private bool loadingModel;
        private string modelNotice;
        private float modelNoticeUntil;
        private readonly OrynPrayerSpread prayer = new OrynPrayerSpread();
        private OrynAssembly prayerTarget;
        private bool prayerConsumesHands;
        private bool spreadingAssembly;

        private void Awake()
        {
            for (int i = 0; i < 4; i++)
            {
                var marker = new GameObject("Workspace Grip " + i, typeof(MeshFilter), typeof(MeshRenderer));
                marker.transform.SetParent(transform, false);
                marker.transform.localScale = Vector3.one * 0.018f;
                marker.GetComponent<MeshFilter>().sharedMesh = MarkerMesh;
                markers[i] = marker.GetComponent<Renderer>();
                markers[i].sharedMaterial = MarkerMaterial;
                markers[i].enabled = false;
            }
            Panel.gameObject.SetActive(false);
            for (int i = 0; i < menuRays.Length; i++)
            {
                var line = new GameObject("Menu pointer " + i).AddComponent<LineRenderer>();
                line.transform.SetParent(transform, false);
                line.useWorldSpace = true; line.positionCount = 2;
                line.startWidth = 0.002f; line.endWidth = 0.001f;
                line.sharedMaterial = MarkerMaterial; line.enabled = false;
                menuRays[i] = line;
            }
            handVisuals[0] = new OrynContactHandVisual(LeftHand, LeftSkeleton, transform);
            handVisuals[1] = new OrynContactHandVisual(RightHand, RightSkeleton, transform);
            gameObject.AddComponent<OrynGenerationInbox>().Workspace = this;
            gameObject.AddComponent<OrynCommandBridge>().Workspace = this;
            wristMenu = new OrynWristMenu(this);
        }

        private void Start()
        {
            FindAnyObjectByType<Meta.XR.ImmersiveDebugger.UserInterface.DebugInterface>()?.Hide();
            Debug.Log("ORYN_M3_READY contact=surface_anchors_visual_fingers gestures=two_finger_resize_three_finger_manipulate workspace=session_only");
        }

        private void LateUpdate()
        {
            bool focused = OVRManager.hasInputFocus && OVRManager.hasVrFocus;
            if (!initialized && focused && Rig.centerEyeAnchor.position.y > 0.1f)
            {
                initialized = true;
                LoadStartupModel();
            }
            input.Read(Rig, LeftHand, RightHand, LeftSkeleton, RightSkeleton, focused);
            bool toggleMenu = focused && input.Valid[0] && OVRInput.GetDown(OVRInput.Button.Two, OVRInput.Controller.LTouch);
            Inspector?.Bind(selected);
            UpdatePrayerSpread();
            bool menuChanged = wristMenu.Update(input, new Pose(Rig.centerEyeAnchor.position, Rig.centerEyeAnchor.rotation),
                focused && initialized && held[0] == null && held[2] == null && !prayerConsumesHands, toggleMenu);
            if (menuChanged)
            {
                confirmDelete = false;
                for (int i = 0; i < 4; i++) { presses[i].Clear(); contactPresses[i].Clear(); }
            }
            for (int i = 0; i < 4; i++)
            {
                gripPoses[i] = input.Poses[i];
                if (held[i] != null) gripPoses[i].position += gripPoses[i].rotation * gripOffsets[i];
            }
            // All poses are sampled before membership changes or object transforms.
            for (int i = 0; i < 4; i++)
            {
                if (held[i] != null && (!input.Valid[i] || input.Strength[i] <= OrynGrabState.EndThreshold))
                {
                    held[i].State.End(i, gripPoses, input.Gestures, input.AimPoints);
                    Debug.Log("ORYN_M3_RELEASE source=" + i + " remaining=" + held[i].State.HoldCount);
                    held[i] = null;
                    touched[i] = null; touchTimes[i] = -1;
                }
            }
            foreach (var item in InteractionObjects())
            {
                var previousMode = item.State.Mode;
                item.State.Step(gripPoses, input.Gestures, Time.unscaledDeltaTime, input.AimPoints);
                if (previousMode != item.State.Mode) Debug.Log("ORYN_MODE object=" + item.Number + " mode=" + item.State.Mode);
                item.Apply(false, item == selected);
            }
            Physics.SyncTransforms();
            for (int i = 0; i < 4; i++)
            {
                if (prayerConsumesHands && i >= 2)
                {
                    hoveredButtons[i] = null; hoveredObjects[i] = null;
                    touched[i] = null; touchTimes[i] = -1;
                    presses[i].Clear(); contactPresses[i].Clear(); markers[i].enabled = false;
                    continue;
                }
                bool menuSource = (i == 1 || i == 3) && Panel.gameObject.activeInHierarchy;
                hoveredButtons[i] = menuSource && input.Valid[i] && held[i] == null ? NearestButton(input.AimPoints[i]) : null;
                bool pointingAtMenu = false;
                Vector3 menuEndpoint = input.AimPoints[i];
                if (i < 2)
                {
                    if (menuSource && input.Valid[i] && held[i] == null && hoveredButtons[i] == null)
                    {
                        hoveredButtons[i] = OrynMenuPlacement.PointedButton(Buttons, input.Poses[i], out menuEndpoint);
                        pointingAtMenu = hoveredButtons[i] != null;
                    }
                    menuRays[i].enabled = pointingAtMenu;
                    if (pointingAtMenu) { menuRays[i].SetPosition(0, input.Poses[i].position); menuRays[i].SetPosition(1, menuEndpoint); }
                }
                hoveredObjects[i] = input.Valid[i] && hoveredButtons[i] == null ? ContactObject(i) : null;
                if (!input.Valid[i]) { touched[i] = null; touchTimes[i] = -1; }
                markers[i].enabled = input.Valid[i];
                if (input.Valid[i]) markers[i].transform.position = held[i] != null ? held[i].transform.TransformPoint(surfaceAnchors[i]) :
                    pointingAtMenu ? menuEndpoint : hoveredObjects[i] != null ? hoveredObjects[i].transform.TransformPoint(touchPoints[i]) : input.AimPoints[i];
                bool gestureReady = input.Gestures[i] == OrynGesture.Manipulate || input.Gestures[i] == OrynGesture.Resize;
                // Preserve the fresh press while the finger classifier settles; do not consume it early.
                float activation = gestureReady ? input.Strength[i] : Mathf.Min(input.Strength[i], 0.6f);
                float menuActivation = i == 3 && input.ContactValid[1][1] ? RightHand.GetFingerPinchStrength(OVRHand.HandFinger.Index) : activation;
                if (i < 2)
                {
                    var controller = i == 0 ? OVRInput.Controller.LTouch : OVRInput.Controller.RTouch;
                    menuActivation = Mathf.Max(OVRInput.Get(OVRInput.Axis1D.PrimaryIndexTrigger, controller),
                        OVRInput.Get(OVRInput.Button.One, controller) ? 1f : 0f);
                }
                // Sample even off-target: dragging an already held trigger onto UI cannot click.
                bool panelPress = presses[i].Sample(input.Valid[i] && menuSource && !menuChanged, menuActivation);
                bool objectPress = contactPresses[i].Sample(input.Valid[i], activation, gestureReady && hoveredObjects[i] != null, Time.unscaledTime);
                if (held[i] != null) continue;
                if (hoveredButtons[i] != null)
                { if (panelPress) Execute(hoveredButtons[i].Action, i); contactPresses[i].Clear(); }
                else if (objectPress && hoveredObjects[i] != null)
                {
                    Vector3 anchor = hoveredObjects[i].transform.TransformPoint(touchPoints[i]);
                    gripOffsets[i] = Quaternion.Inverse(input.Poses[i].rotation) * (anchor - input.Poses[i].position);
                    gripPoses[i] = new Pose(anchor, input.Poses[i].rotation);
                    if (!hoveredObjects[i].State.Begin(i, gripPoses, input.Gestures, input.AimPoints)) continue;
                    held[i] = hoveredObjects[i];
                    surfaceAnchors[i] = touchPoints[i];
                    selected = held[i];
                    confirmDelete = false;
                    Debug.Log("ORYN_M3_GRAB source=" + i + " object=" + selected.Number + " hands=" + selected.State.HoldCount + " mode=" + selected.State.Mode);
                }
            }
            for (int hand = 0; hand < 2; hand++)
            {
                int source = hand + 2;
                OrynWorkspaceObject target = prayerConsumesHands ? null : held[source] != null ? held[source] : VisualContactObject(hand);
                handVisuals[hand].Update(input.Valid[source], target != null ? target.Bounds : null);
                for (int finger = 0; finger < 6; finger++)
                { previousContacts[hand][finger] = input.Contacts[hand][finger]; previousValid[hand][finger] = input.Valid[source] && input.ContactValid[hand][finger]; }
            }
            foreach (var item in InteractionObjects())
            {
                bool hover = false;
                for (int i = 0; i < 4; i++) hover |= hoveredObjects[i] == item;
                item.Apply(hover, item == selected);
            }
            foreach (var button in Buttons)
            {
                bool hover = false;
                for (int i = 0; i < 4; i++) hover |= hoveredButtons[i] == button;
                button.ShowState(CanExecute(button.Action), hover);
            }
            if (confirmDelete && Time.unscaledTime > confirmationUntil) confirmDelete = false;
            string message = prayer.Active ? "SPREAD " + Mathf.RoundToInt(prayer.Amount * 100) + "% | hands apart / together" :
                prayer.ArmProgress > 0 ? "Hold prayer pose..." : loadingModel ? "Loading external model..." : Time.unscaledTime < modelNoticeUntil ? modelNotice :
                Time.unscaledTime < noticeUntil ? "Move an object aside to make space" : confirmDelete ? "Pinch / grip DELETE again to confirm" :
                selected == null ? "No selection - create an object" : "Selected: " + selected.ShapeName + " " + selected.Number +
                "  |  " + Mathf.RoundToInt(selected.State.Scale * 100f) + "%  |  " +
                (selected.PartOf != null ? "PART / " : selected.Assembly != null ? (selected.Assembly.PartsMode ? "PARTS MODE / " : "WHOLE / ") : "") + ModeLabel(selected.State);
            if (message != previousStatus)
            { Status.text = message; Status.characterSize = message.Length > 45 ? 0.0035f : 0.0045f; previousStatus = message; }
            Inspector?.Bind(selected);
            wristMenu.Refresh();
        }

        private OrynWorkspaceObject ContactObject(int source)
        {
            if (held[source] != null) return held[source];
            OrynWorkspaceObject nearest = null;
            Vector3 contact = Vector3.zero;
            float distance = float.PositiveInfinity;
            foreach (var item in InteractionObjects())
            {
                if (input.Gestures[source] == OrynGesture.Resize && OrynSurfaceContact.ResizeTarget(item.Bounds, input.AimPoints[source], out Vector3 resizeSurface))
                {
                    float score = Vector3.Distance(input.AimPoints[source], resizeSurface);
                    // Prefer the opposite hand's object when both are in reach.
                    if (item.State.HoldCount == 1 && item.State.Primary % 2 != source % 2) score -= 0.15f;
                    if (score < distance) { distance = score; nearest = item; contact = resizeSurface; }
                    continue;
                }
                int count = source < 2 ? 1 : 6;
                for (int finger = 0; finger < count; finger++)
                {
                    if (source >= 2 && !input.ContactValid[source - 2][finger]) continue;
                    Vector3 point = source < 2 ? input.AimPoints[source] : input.Contacts[source - 2][finger];
                    Vector3 previous = source < 2 ? point : previousContacts[source - 2][finger];
                    bool validPrevious = source >= 2 && previousValid[source - 2][finger];
                    if (!OrynSurfaceContact.Touch(item.Bounds, point, previous, validPrevious, out Vector3 surface)) continue;
                    float current = Vector3.Distance(point, surface);
                    // Fingertips win close ties against the broader palm probe.
                    if (finger == 5) current += 0.008f;
                    if (current < distance) { distance = current; nearest = item; contact = surface; }
                }
            }
            if (nearest != null)
            {
                touched[source] = nearest;
                touchPoints[source] = nearest.transform.InverseTransformPoint(contact);
                touchTimes[source] = Time.unscaledTime;
            }
            // Remember first contact while the fingertips close into the gesture.
            if (touched[source] != null && Time.unscaledTime - touchTimes[source] <= OrynSurfaceContact.ContactMemory &&
                Vector3.Distance(input.Gestures[source] == OrynGesture.Resize ? input.AimPoints[source] : input.Poses[source].position,
                    touched[source].transform.TransformPoint(touchPoints[source])) < 0.18f)
                return touched[source];
            touched[source] = null;
            return null;
        }
        private OrynWorkspaceObject VisualContactObject(int hand)
        {
            if (!input.Valid[hand + 2]) return null;
            OrynWorkspaceObject nearest = null;
            float distance = 0.07f;
            foreach (var item in InteractionObjects())
            for (int finger = 0; finger < 6; finger++)
            {
                if (!input.ContactValid[hand][finger] || !OrynSurfaceContact.Query(item.Bounds, input.Contacts[hand][finger], out _, out _, out float depth)) continue;
                if (Mathf.Abs(depth) < distance) { distance = Mathf.Abs(depth); nearest = item; }
            }
            return nearest;
        }
        private static string ModeLabel(OrynTwoHandState state)
        {
            switch (state.Mode)
            {
                case OrynTwoHandState.Operation.Resize: return "RESIZE";
                case OrynTwoHandState.Operation.Manipulate: return "MOVE / ROTATE";
                case OrynTwoHandState.Operation.Waiting: return state.HoldCount == 1 ? "ADD PINCH OR THIRD FINGER" : "MATCH FINGER GESTURES";
                default: return "RELEASED";
            }
        }
        private OrynWorkspaceButton NearestButton(Vector3 point)
        {
            if (!Panel.gameObject.activeInHierarchy) return null;
            return OrynMenuPlacement.NearButton(Buttons, point);
        }

        private bool CanExecute(OrynWorkspaceButton.Command action)
        {
            if (action == OrynWorkspaceButton.Command.MenuPrevious || action == OrynWorkspaceButton.Command.MenuNext) return true;
            if (action == OrynWorkspaceButton.Command.DroneDemo || action == OrynWorkspaceButton.Command.V8Demo) return objects.Count < ObjectLimit && !loadingModel;
            if (action >= OrynWorkspaceButton.Command.MotionPlay) return SelectedAssembly()?.Owner.Mechanical != null;
            if (action == OrynWorkspaceButton.Command.PreviousLabel || action == OrynWorkspaceButton.Command.NextLabel)
                return Inspector != null && Inspector.CanEdit;
            if (action == OrynWorkspaceButton.Command.SaveLabel) return Inspector != null && Inspector.CanSave;
            var assembly = SelectedAssembly();
            if (action == OrynWorkspaceButton.Command.Parts || action == OrynWorkspaceButton.Command.Explode || action == OrynWorkspaceButton.Command.Reassemble) return assembly != null;
            if (action == OrynWorkspaceButton.Command.Isolate) return assembly != null && assembly.PartsMode && selected.PartOf != null;
            if (action == OrynWorkspaceButton.Command.Delete && selected != null && selected.PartOf != null) return false;
            if (action == OrynWorkspaceButton.Command.LoadModel) return !loadingModel;
            return action == OrynWorkspaceButton.Command.Cube || action == OrynWorkspaceButton.Command.Sphere
                ? objects.Count < ObjectLimit : selected != null;
        }
        private void Execute(OrynWorkspaceButton.Command action, int source)
        {
            Inspector?.Bind(selected); // Refresh before a same-frame selection/button change.
            if (!CanExecute(action)) return;
            if (action != OrynWorkspaceButton.Command.Delete) confirmDelete = false;
            switch (action)
            {
                case OrynWorkspaceButton.Command.MenuPrevious:
                case OrynWorkspaceButton.Command.MenuNext:
                    wristMenu.ChangePage(action == OrynWorkspaceButton.Command.MenuNext ? 1 : -1);
                    for (int i = 0; i < 4; i++) { presses[i].Clear(); contactPresses[i].Clear(); }
                    break;
                case OrynWorkspaceButton.Command.DroneDemo: SpawnMechanism(false); break;
                case OrynWorkspaceButton.Command.V8Demo: SpawnMechanism(true); break;
                case OrynWorkspaceButton.Command.MotionPlay: SelectedAssembly().Owner.Mechanical.Play(); break;
                case OrynWorkspaceButton.Command.MotionPause: SelectedAssembly().Owner.Mechanical.Pause(); break;
                case OrynWorkspaceButton.Command.MotionStop: SelectedAssembly().Owner.Mechanical.StopHome(); break;
                case OrynWorkspaceButton.Command.MotionSlow: SelectedAssembly().Owner.Mechanical.SetSpeed(0.15f); break;
                case OrynWorkspaceButton.Command.MotionNormal: SelectedAssembly().Owner.Mechanical.SetSpeed(1); break;
                case OrynWorkspaceButton.Command.MotionIsolate:
                    var mechanism = SelectedAssembly(); ReleaseAssembly(mechanism);
                    if (mechanism.Isolated) mechanism.Reassemble();
                    else mechanism.Owner.Mechanical.IsolateSubsystem(mechanism.Owner.Mechanical.Definition.Id.Contains("v8") ? "rotating_assembly" : "propulsion");
                    selected = mechanism.Owner; break;
                case OrynWorkspaceButton.Command.PreviousLabel: Inspector.Cycle(-1); break;
                case OrynWorkspaceButton.Command.NextLabel: Inspector.Cycle(1); break;
                case OrynWorkspaceButton.Command.SaveLabel: Inspector.Save(); break;
                case OrynWorkspaceButton.Command.Cube: Spawn(false); break;
                case OrynWorkspaceButton.Command.Sphere: Spawn(true); break;
                case OrynWorkspaceButton.Command.Reset: ResetSelected(); break;
                case OrynWorkspaceButton.Command.LoadModel: BringModel(); break;
                case OrynWorkspaceButton.Command.Parts:
                case OrynWorkspaceButton.Command.Explode:
                case OrynWorkspaceButton.Command.Isolate:
                case OrynWorkspaceButton.Command.Reassemble:
                    var assembly = SelectedAssembly();
                    ReleaseAssembly(assembly);
                    if (action == OrynWorkspaceButton.Command.Parts) assembly.SetPartsMode(!assembly.PartsMode);
                    if (action == OrynWorkspaceButton.Command.Explode) assembly.Explode();
                    if (action == OrynWorkspaceButton.Command.Isolate) assembly.ToggleIsolate(selected);
                    if (action == OrynWorkspaceButton.Command.Reassemble) assembly.Reassemble();
                    if (action != OrynWorkspaceButton.Command.Isolate) selected = assembly.Owner;
                    modelNotice = assembly.PartsMode ? "PARTS: grab a piece | ASSEMBLE restores all" : "WHOLE: grab or resize the full model";
                    modelNoticeUntil = Time.unscaledTime + 4f;
                    break;
                case OrynWorkspaceButton.Command.Delete:
                    if (!confirmDelete || Time.unscaledTime > confirmationUntil || source != confirmationSource)
                    { confirmDelete = true; confirmationSource = source; confirmationFrame = Time.frameCount; confirmationUntil = Time.unscaledTime + 4f; return; }
                    if (Time.frameCount == confirmationFrame) return;
                    if (selected.Assembly != null) ReleaseAssembly(selected.Assembly); else Release(selected);
                    objects.Remove(selected);
                    selected.gameObject.SetActive(false);
                    Destroy(selected.gameObject);
                    selected = objects.Count == 0 ? null : objects[objects.Count - 1];
                    confirmDelete = false;
                    break;
            }
            Debug.Log("ORYN_M3_PANEL action=" + action + " count=" + objects.Count);
        }
        private void Spawn(bool sphere)
        {
            if (objects.Count >= ObjectLimit) return;
            if (!TrySpawnPose(out Pose pose)) return;
            var item = Instantiate(sphere ? SpherePrefab : CubePrefab, pose.position, pose.rotation);
            Register(item, pose);
        }
        private void SpawnMechanism(bool engine)
        {
            if (objects.Count >= ObjectLimit || !TrySpawnPose(out Pose pose)) return;
            var item = Instantiate(CubePrefab, pose.position, pose.rotation);
            try
            {
                OrynMechanicalBenchmarks.Attach(item, engine, CubePrefab.GetComponent<Renderer>().sharedMaterial, MarkerMaterial);
                Register(item, pose);
                StartupNotice("Authored mechanism demo, not a verified mapping of your generated model");
            }
            catch { Destroy(item.gameObject); throw; }
        }
        private bool TrySpawnPose(out Pose pose)
        {
            pose = ReachPose();
            Vector3 right = Vector3.Cross(Vector3.up, Forward());
            Vector3 center = pose.position;
            bool room = false;
            // Use only nearby clear slots. Do not pile objects up or spawn beyond reach.
            for (int slot = 0; slot < 3; slot++)
            {
                pose.position = center + right * (slot == 0 ? 0f : slot == 1 ? -0.43f : 0.43f);
                var candidate = new Bounds(pose.position, Vector3.one * 0.41f);
                room = true;
                foreach (var existing in InteractionObjects()) if (candidate.Intersects(existing.Bounds.bounds)) { room = false; break; }
                if (room) break;
            }
            if (!room) noticeUntil = Time.unscaledTime + 3f;
            return room;
        }
        private void Register(OrynWorkspaceObject item, Pose pose)
        {
            item.Number = nextNumber++;
            item.name = "Oryn " + item.ShapeName + " " + item.Number;
            item.State.Reset(pose);
            objects.Add(item);
            selected = item;
        }
        private void BringModel()
        {
            var target = OrynObjectPlacement.RecoveryTarget(objects, selected);
            if (target == null) { LoadStartupModel(); return; }
            EndPrayerSpread(); prayer.Reset(); prayerConsumesHands = false;
            if (target.Assembly != null) ReleaseAssembly(target.Assembly); else Release(target);
            OrynObjectPlacement.Recover(target, new Pose(Rig.centerEyeAnchor.position, Rig.centerEyeAnchor.rotation));
            selected = target;
            Inspector?.Bind(selected);
            modelNotice = "Model brought here - labels retained"; modelNoticeUntil = Time.unscaledTime + 4;
        }
        private void StartupNotice(string message)
        {
            if (this != null)
            {
                modelNotice = message; modelNoticeUntil = Time.unscaledTime + 6;
            }
        }
        private async void LoadStartupModel()
        {
            string path = null;
            try { path = new OrynKnowledgeStore(OrynKnowledgeStore.DefaultRoot).ResumeModel(); }
            catch (System.Exception error)
            {
                Debug.LogWarning("ORYN_RESUME_FAILED " + error.GetType().Name);
                modelNotice = "Saved model unavailable; records preserved"; modelNoticeUntil = Time.unscaledTime + 8;
            }
            if (path == null) { StartupNotice("No saved model - send one from the Mac"); return; }
            try
            {
                if (!await ImportModel(path, "saved_knowledge")) StartupNotice("Model waiting - make space, then BRING MODEL");
            }
            catch (System.OperationCanceledException) { }
            catch (System.Exception error) { Debug.LogWarning("ORYN_RESUME_IMPORT_FAILED " + error.GetType().Name); }
        }
        public async System.Threading.Tasks.Task<bool> ImportModel(string path, string source)
        {
            // Do not import repeatedly while the headset is idle or spawn slots are full.
            if (!initialized || loadingModel || !isActiveAndEnabled || !OVRManager.hasVrFocus || objects.Count >= ObjectLimit || !TrySpawnPose(out _)) return false;
            loadingModel = true;
            OrynRuntimeModel model = null;
            OrynWorkspaceObject pendingObject = null;
            float started = Time.realtimeSinceStartup;
            try
            {
                model = await OrynRuntimeModel.Load(path, destroyCancellationToken);
                if (this == null || !isActiveAndEnabled || !OVRManager.hasVrFocus || objects.Count >= ObjectLimit || !TrySpawnPose(out Pose pose)) return false;
                var item = pendingObject = Instantiate(CubePrefab, pose.position, pose.rotation);
                item.AttachModel(model, MarkerMaterial);
                if (source == "demo_usb") item.ShapeName = "Test model";
                else if (source == "generated_usb") item.ShapeName = "Generated model";
                if (item.Assembly != null) item.ShapeName = item.Assembly.Parts.Count + "-part model";
                Register(item, pose);
                if (source == "generated_usb")
                {
                    try { new OrynKnowledgeStore(OrynKnowledgeStore.DefaultRoot).RememberModel(model.SourcePath, model.SourceHash); }
                    catch (System.Exception error)
                    {
                        Debug.LogWarning("ORYN_MODEL_REMEMBER_FAILED " + error.GetType().Name);
                        StartupNotice("Model loaded; startup copy could not be saved");
                    }
                }
                pendingObject = null;
                model = null; // Ownership transferred to the workspace object's hierarchy.
                Debug.Log("ORYN_MODEL_LOADED source=" + source + " seconds=" + (Time.realtimeSinceStartup - started).ToString("F2"));
                return true;
            }
            finally
            {
                if (model != null) { model.ReleaseResources(); Destroy(model.gameObject); }
                if (pendingObject != null) Destroy(pendingObject.gameObject);
                if (this != null) loadingModel = false;
            }
        }
        private void Release(OrynWorkspaceObject item)
        {
            item.State.ReleaseAll();
            for (int i = 0; i < 4; i++)
            {
                if (touched[i] == item) { touched[i] = null; touchTimes[i] = -1; }
                if (held[i] == item) { held[i] = null; presses[i].Clear(); contactPresses[i].Clear(); }
            }
        }
        private void ResetSelected()
        {
            if (selected == null) return;
            if (selected.PartOf != null)
            { Release(selected); selected.PartOf.ResetPart(selected); return; }
            if (selected.Assembly != null) { ReleaseAssembly(selected.Assembly); selected.Assembly.Reassemble(); }
            selected.Mechanical?.StopHome();
            Release(selected);
            selected.State.Reset(ReachPose());
            selected.Apply(false, true);
            confirmDelete = false;
        }
        private Pose ReachPose()
        {
            return OrynObjectPlacement.WithinReach(new Pose(Rig.centerEyeAnchor.position, Rig.centerEyeAnchor.rotation));
        }
        private Vector3 Forward()
        {
            Vector3 forward = Vector3.ProjectOnPlane(Rig.centerEyeAnchor.forward, Vector3.up).normalized;
            return forward.sqrMagnitude < 0.01f ? Vector3.forward : forward;
        }
        private void ReleaseEverything()
        {
            EndPrayerSpread();
            if (Panel != null) Panel.gameObject.SetActive(false);
            foreach (var line in menuRays) if (line != null) line.enabled = false;
            prayer.Reset(); prayerConsumesHands = false;
            foreach (var item in objects)
            {
                item.State.ReleaseAll();
                if (item.Assembly != null) foreach (var part in item.Assembly.Parts) part.State.ReleaseAll();
            }
            for (int i = 0; i < 4; i++) { held[i] = null; touched[i] = null; touchTimes[i] = -1; presses[i].Clear(); contactPresses[i].Clear(); if (markers[i] != null) markers[i].enabled = false; }
            for (int h = 0; h < 2; h++)
            { handVisuals[h]?.Restore(); for (int f = 0; f < 6; f++) previousValid[h][f] = false; }
            confirmDelete = false;
        }
        private void OnDisable() { ReleaseEverything(); }
        private OrynAssembly SelectedAssembly() => selected == null ? null : selected.PartOf != null ? selected.PartOf : selected.Assembly;
        internal OrynAssembly CommandAssembly => SelectedAssembly();
        internal OrynWorkspaceObject CommandSelection => selected;
        internal bool CommandsReady => ExperienceReady && SelectedAssembly() != null;
        internal bool ExperienceReady
        {
            get
            {
                if (!initialized || loadingModel || prayerConsumesHands || spreadingAssembly ||
                    !OVRManager.hasInputFocus || !OVRManager.hasVrFocus || !isActiveAndEnabled) return false;
                foreach (var item in held) if (item != null) return false;
                return true;
            }
        }
        internal void ApplyExperience(OrynExperienceCommand command)
        {
            if (!ExperienceReady) throw new System.InvalidOperationException("Workspace not ready");
            if (command.action == "show_drone")
            {
                var existing = objects.Find(item => item != null && item.Mechanical?.Definition.Id == "authored-drone-propulsion");
                if (existing != null) { selected = existing; ResetSelected(); }
                else
                {
                    int count = objects.Count; SpawnMechanism(false);
                    if (objects.Count == count) throw new System.InvalidOperationException("No space for the drone");
                }
                Inspector?.Bind(selected); return;
            }
            var assembly = SelectedAssembly();
            var mechanism = assembly?.Owner.Mechanical;
            if (mechanism == null) throw new System.InvalidOperationException("Mechanical object unavailable");
            switch (command.action)
            {
                case "select": ApplyCommand("select", mechanism.Component(command.component)); return;
                case "isolate_component": ApplyCommand("isolate", mechanism.Component(command.component)); return;
                case "explode": ApplyCommand("explode", null); return;
                case "reassemble": ApplyCommand("reassemble", null); return;
                case "isolate_subsystem": mechanism.IsolateSubsystem(command.subsystem); selected = assembly.Owner; break;
                case "demonstrate": mechanism.Demonstrate(command.component); if (!string.IsNullOrEmpty(command.component)) selected = mechanism.Component(command.component); break;
                case "play": mechanism.Play(); break;
                case "pause": mechanism.Pause(); break;
                case "slow": mechanism.SetSpeed(0.15f); break;
                case "normal": mechanism.SetSpeed(1); break;
                case "restore": assembly.Reassemble(); mechanism.StopHome(); mechanism.SetSpeed(1); selected = assembly.Owner; break;
                default: throw new System.InvalidOperationException("Unsupported action");
            }
            Inspector?.Bind(selected);
            modelNotice = "ORYN: " + command.action; modelNoticeUntil = Time.unscaledTime + 4;
        }
        // Called only after the bridge validates current context, expiry and target.
        internal void ApplyCommand(string action, OrynWorkspaceObject target)
        {
            var assembly = SelectedAssembly();
            if (!CommandsReady || assembly == null) throw new System.InvalidOperationException("Workspace not ready");
            ReleaseAssembly(assembly);
            switch (action)
            {
                case "select":
                case "isolate":
                    if (target == null || target.PartOf != assembly) throw new System.InvalidOperationException("Part unavailable");
                    if (assembly.Isolated) assembly.ToggleIsolate(target);
                    if (!assembly.PartsMode) assembly.SetPartsMode(true);
                    if (action == "isolate") assembly.ToggleIsolate(target);
                    selected = target;
                    break;
                case "explode": assembly.Explode(); selected = assembly.Owner; break;
                case "reassemble": assembly.Reassemble(); selected = assembly.Owner; break;
                default: throw new System.InvalidOperationException("Unsupported action");
            }
            confirmDelete = false;
            Inspector?.Bind(selected);
            modelNotice = "COMMAND: " + action;
            modelNoticeUntil = Time.unscaledTime + 4f;
        }
        private void UpdatePrayerSpread()
        {
            Vector3 midpoint = (input.Palms[0].Position + input.Palms[1].Position) * 0.5f;
            OrynAssembly candidate = prayerTarget != null ? prayerTarget : SelectedAssembly();
            if (candidate == null)
            {
                // No button needed when exactly one nearby multipart object exists.
                foreach (var item in objects)
                {
                    if (item.Assembly == null || Vector3.Distance(item.transform.position, midpoint) > 0.85f) continue;
                    if (candidate != null) { candidate = null; break; }
                    candidate = item.Assembly;
                }
            }
            bool free = true;
            for (int i = 0; i < 4; i++) free &= held[i] == null;
            bool eligible = candidate != null && free && !loadingModel && Vector3.Distance(candidate.transform.position, midpoint) <= 0.85f;
            // The arming target is stable too; never finish a dwell on another object.
            if (prayerTarget != null && candidate != prayerTarget) { EndPrayerSpread(); prayer.Reset(); }
            bool wasActive = prayer.Active;
            prayer.Sample(input.Palms[0], input.Palms[1], eligible, Time.unscaledDeltaTime);
            prayerConsumesHands = prayer.ConsumesHands;
            if (prayer.ConsumesHands && prayerTarget == null) prayerTarget = candidate;
            if (prayer.Started)
            {
                ReleaseAssembly(prayerTarget);
                prayerTarget.BeginSpread(); selected = prayerTarget.Owner; confirmDelete = false;
                spreadingAssembly = true;
                Debug.Log("ORYN_PRAYER_BEGIN parts=" + prayerTarget.Parts.Count);
            }
            if (prayer.Active) prayerTarget.SetSpread(prayer.Amount);
            if (!prayer.ConsumesHands && prayerTarget != null)
            {
                if (wasActive) Debug.Log("ORYN_PRAYER_END spread=" + prayerTarget.SpreadAmount.ToString("F2"));
                EndPrayerSpread();
            }
        }
        private void EndPrayerSpread()
        {
            if (prayerTarget != null && spreadingAssembly && prayerTarget.SpreadAmount < 0.015f) prayerTarget.Reassemble();
            spreadingAssembly = false;
            prayerTarget = null;
        }
        private void ReleaseAssembly(OrynAssembly assembly)
        {
            if (assembly == null) return;
            Release(assembly.Owner);
            foreach (var part in assembly.Parts) Release(part);
        }
        private IEnumerable<OrynWorkspaceObject> InteractionObjects()
        {
            foreach (var item in objects)
            {
                if (item.Assembly != null && item.Assembly.PartsMode)
                {
                    foreach (var part in item.Assembly.Parts)
                        if (part.gameObject.activeSelf) yield return part;
                }
                else yield return item;
            }
        }
        private void OnDestroy() { for (int h = 0; h < 2; h++) handVisuals[h]?.Dispose(); }
        private void OnApplicationPause(bool paused) { if (paused) ReleaseEverything(); }
        private void OnApplicationFocus(bool focused) { if (!focused) ReleaseEverything(); }
    }
}
