using System;
using UnityEngine;

namespace Oryn.Interaction
{
    // Placement/visibility has no SDK dependency, so tracking loss and reveal can be tested.
    public sealed class OrynWristReveal
    {
        public bool Visible { get; private set; }
        private float dwell;
        public void Reset() { Visible = false; dwell = 0; }
        public bool Sample(OrynPalmSample palm, Vector3 wrist, Pose eye, bool eligible, float seconds)
        {
            Vector3 toEye = eye.position - wrist;
            bool facing = eligible && palm.Valid && palm.Open && toEye.magnitude >= 0.20f && toEye.magnitude <= 0.85f &&
                Vector3.Dot(palm.Normal, toEye.normalized) > (Visible ? 0.35f : 0.60f) &&
                Vector3.Dot(eye.rotation * Vector3.forward, -toEye.normalized) > 0.50f;
            if (!facing || !float.IsFinite(seconds)) { Reset(); return false; }
            dwell += Mathf.Clamp(seconds, 0, 0.05f);
            Visible = dwell >= 0.20f;
            return Visible;
        }
        public static Pose Placement(Vector3 wrist, Vector3 fingers, Vector3 normal, Pose eye)
        {
            Vector3 center = wrist - fingers.normalized * 0.08f + normal.normalized * 0.09f;
            Vector3 forward = (center - eye.position).normalized;
            if (forward.sqrMagnitude < 0.01f) forward = eye.rotation * Vector3.forward;
            Vector3 up = Vector3.ProjectOnPlane(eye.rotation * Vector3.up, forward).normalized;
            if (up.sqrMagnitude < 0.01f) up = Vector3.ProjectOnPlane(eye.rotation * Vector3.right, forward).normalized;
            return new Pose(center, Quaternion.LookRotation(forward, up));
        }
    }

    public sealed class OrynWristMenu
    {
        public const int PageCount = 4;
        private readonly OrynWorkspace workspace;
        private readonly OrynWristReveal reveal = new OrynWristReveal();
        private readonly TextMesh title, status, details;
        private readonly TextMesh[] captions = new TextMesh[6];
        private readonly OrynWorkspaceButton[] slots = new OrynWorkspaceButton[6];
        private bool controllerOpen;
        private int page;
        private static readonly string[] Titles = { "OBJECT", "MOTION", "LIBRARY", "DETAILS" };
        private static readonly string[][] Labels = {
            new[] { "Bring model", "Parts / whole", "Take apart", "Reassemble", "Isolate / all", "Reset" },
            new[] { "Play", "Pause", "Stop / home", "Slow", "Normal speed", "System / all" },
            new[] { "Drone demo", "V8 demo", "Cube", "Sphere", "Delete", "" },
            new[] { "< Label", "Label >", "Save label", "", "", "" }
        };
        private static readonly OrynWorkspaceButton.Command[][] Actions = {
            new[] { OrynWorkspaceButton.Command.LoadModel, OrynWorkspaceButton.Command.Parts, OrynWorkspaceButton.Command.Explode,
                OrynWorkspaceButton.Command.Reassemble, OrynWorkspaceButton.Command.Isolate, OrynWorkspaceButton.Command.Reset },
            new[] { OrynWorkspaceButton.Command.MotionPlay, OrynWorkspaceButton.Command.MotionPause, OrynWorkspaceButton.Command.MotionStop,
                OrynWorkspaceButton.Command.MotionSlow, OrynWorkspaceButton.Command.MotionNormal, OrynWorkspaceButton.Command.MotionIsolate },
            new[] { OrynWorkspaceButton.Command.DroneDemo, OrynWorkspaceButton.Command.V8Demo, OrynWorkspaceButton.Command.Cube,
                OrynWorkspaceButton.Command.Sphere, OrynWorkspaceButton.Command.Delete, OrynWorkspaceButton.Command.Delete },
            new[] { OrynWorkspaceButton.Command.PreviousLabel, OrynWorkspaceButton.Command.NextLabel, OrynWorkspaceButton.Command.SaveLabel,
                OrynWorkspaceButton.Command.SaveLabel, OrynWorkspaceButton.Command.SaveLabel, OrynWorkspaceButton.Command.SaveLabel }
        };
        public OrynWristMenu(OrynWorkspace owner)
        {
            workspace = owner;
            Material buttons = owner.Buttons[0].GetComponent<Renderer>().sharedMaterial;
            Material backing = owner.Panel.Find("Panel Backing").GetComponent<Renderer>().sharedMaterial;
            // Retain serialized references for inspector/status writers, but remove their old board from view.
            foreach (Transform child in owner.Panel) child.gameObject.SetActive(false);
            owner.Panel.name = "ORYN left wrist menu";
            owner.Panel.localScale = Vector3.one;
            var plate = GameObject.CreatePrimitive(PrimitiveType.Cube);
            plate.name = "Wrist backing"; plate.transform.SetParent(owner.Panel, false);
            plate.transform.localScale = new Vector3(0.30f, 0.33f, 0.008f);
            plate.GetComponent<Renderer>().sharedMaterial = backing; plate.GetComponent<Collider>().enabled = false;
            title = Label("ORYN / OBJECT", new Vector3(0,0.139f,-0.01f), 0.0033f);
            status = Label("Raise left palm · right pinch", new Vector3(0,0.105f,-0.01f), 0.0022f);
            details = Label("", new Vector3(-0.13f,0.078f,-0.01f), 0.0020f);
            details.anchor = TextAnchor.UpperLeft; details.alignment = TextAlignment.Left;
            owner.Buttons = new OrynWorkspaceButton[8];
            for (int i = 0; i < 6; i++)
            {
                slots[i] = Button(buttons, Vector3.zero, new Vector3(0.13f,0.045f,0.012f));
                captions[i] = Label("", Vector3.zero, 0.0028f);
                owner.Buttons[i] = slots[i];
            }
            owner.Buttons[6] = Button(buttons, new Vector3(-0.072f,-0.137f,-0.012f), new Vector3(0.13f,0.034f,0.012f));
            owner.Buttons[6].Action = OrynWorkspaceButton.Command.MenuPrevious;
            owner.Buttons[7] = Button(buttons, new Vector3(0.072f,-0.137f,-0.012f), new Vector3(0.13f,0.034f,0.012f));
            owner.Buttons[7].Action = OrynWorkspaceButton.Command.MenuNext;
            Label("< Previous", new Vector3(-0.072f,-0.137f,-0.022f), 0.0026f);
            Label("Next >", new Vector3(0.072f,-0.137f,-0.022f), 0.0026f);
            ChangePage(0);
            owner.Panel.gameObject.SetActive(false);
        }
        private OrynWorkspaceButton Button(Material material, Vector3 position, Vector3 size)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube); go.name = "Wrist action";
            go.transform.SetParent(workspace.Panel, false); go.transform.localPosition = position; go.transform.localScale = size;
            go.GetComponent<Renderer>().sharedMaterial = material;
            var button = go.AddComponent<OrynWorkspaceButton>(); button.Bounds = go.GetComponent<Collider>(); return button;
        }
        private TextMesh Label(string value, Vector3 position, float size)
        {
            var text = new GameObject("Wrist caption").AddComponent<TextMesh>();
            text.transform.SetParent(workspace.Panel, false); text.transform.localPosition = position;
            text.font = workspace.Status.font; text.fontSize = 48; text.characterSize = size;
            text.anchor = TextAnchor.MiddleCenter; text.alignment = TextAlignment.Center; text.richText = false;
            text.text = value; text.GetComponent<Renderer>().sharedMaterial = workspace.Status.GetComponent<Renderer>().sharedMaterial;
            return text;
        }
        public void ChangePage(int delta)
        {
            page = (page + delta + PageCount) % PageCount;
            title.text = "ORYN / " + Titles[page] + "   " + (page + 1) + "/" + PageCount;
            details.gameObject.SetActive(page == 3);
            for (int i = 0; i < slots.Length; i++)
            {
                bool active = Labels[page][i].Length > 0;
                slots[i].gameObject.SetActive(active); captions[i].gameObject.SetActive(active);
                slots[i].Action = Actions[page][i]; captions[i].text = Labels[page][i];
                Vector3 pos = page == 3 ? new Vector3((i-1)*0.093f,-0.09f,-0.012f) :
                    new Vector3((i%2-0.5f)*0.144f,0.055f-i/2*0.057f,-0.012f);
                slots[i].transform.localPosition = pos;
                slots[i].transform.localScale = new Vector3(page == 3 ? 0.086f : 0.13f,0.045f,0.012f);
                captions[i].transform.localPosition = pos + Vector3.back*0.010f;
            }
        }
        // Called with raw tracking before UI hit tests, never from constrained hand visuals.
        public bool Update(OrynTrackedInput input, Pose eye, bool eligible, bool toggleController)
        {
            bool wasVisible = workspace.Panel.gameObject.activeSelf;
            bool visible = false; Pose pose = default;
            if (!eligible) { controllerOpen = false; reveal.Reset(); }
            else if (input.Valid[2] && input.WristValid[0])
            {
                controllerOpen = false;
                visible = reveal.Sample(input.Palms[0], input.Wrists[0], eye, true, Time.unscaledDeltaTime);
                pose = OrynWristReveal.Placement(input.Wrists[0], input.Palms[0].Fingers, input.Palms[0].Normal, eye);
            }
            else if (input.Valid[0])
            {
                reveal.Reset();
                if (toggleController) controllerOpen = !controllerOpen;
                visible = controllerOpen;
                pose = OrynWristReveal.Placement(input.Poses[0].position, input.Poses[0].rotation * Vector3.forward,
                    (eye.position-input.Poses[0].position).normalized, eye);
            }
            else { reveal.Reset(); controllerOpen = false; }
            workspace.Panel.gameObject.SetActive(visible);
            if (visible) workspace.Panel.SetPositionAndRotation(pose.position, pose.rotation);
            Refresh();
            return wasVisible != visible;
        }
        public void Refresh()
        {
            string value = page == 1 ? workspace.CommandAssembly?.Owner.Mechanical?.Status : workspace.Status.text;
            if (page == 1 && string.IsNullOrEmpty(value)) value = "No supported motion on this object";
            if (page == 2) value = "Demos are authored test objects";
            status.text = Wrap(value ?? "", 38, 2);
            if (page == 3) details.text = Wrap(workspace.Inspector?.Details?.text ?? "Select a part to inspect.", 43, 12);
        }
        private static string Wrap(string value, int width, int maxLines)
        {
            var result = new System.Text.StringBuilder(); int col = 0, lines = 1;
            foreach (char c in value)
            {
                if (c == '\n' || col >= width)
                {
                    if (++lines > maxLines) { result.Append('…'); break; }
                    result.Append('\n'); col = 0; if (c == '\n') continue;
                }
                result.Append(c); col++;
            }
            return result.ToString();
        }
    }
}
