using System;
using UnityEngine;

namespace Oryn.Interaction
{
    // Additive runtime panel: existing serialized menu indices/scene stay intact.
    public sealed class OrynMechanicalControls : MonoBehaviour
    {
        private OrynWorkspace workspace;
        private TextMesh status;
        public static void Install(OrynWorkspace workspace)
        {
            if (workspace.Panel.Find("Mechanical controls") != null) return;
            var root = new GameObject("Mechanical controls"); root.transform.SetParent(workspace.Panel, false);
            var ui = root.AddComponent<OrynMechanicalControls>(); ui.workspace = workspace;
            var source = workspace.Buttons[0].GetComponent<Renderer>().sharedMaterial;
            var plate = GameObject.CreatePrimitive(PrimitiveType.Cube); plate.transform.SetParent(root.transform, false);
            plate.transform.localPosition = new Vector3(0,0.46f,0); plate.transform.localScale = new Vector3(0.91f,0.40f,0.015f);
            plate.GetComponent<Renderer>().sharedMaterial = source; plate.GetComponent<Collider>().enabled = false;
            ui.Label("MECHANICS · AUTHORED DEMONSTRATIONS", new Vector3(0,0.625f,-0.02f), 0.0038f);
            string[] labels = { "DRONE DEMO", "V8 DEMO", "PLAY", "PAUSE", "STOP / HOME", "SLOW", "1x", "SYSTEM / ALL" };
            int old = workspace.Buttons.Length; Array.Resize(ref workspace.Buttons, old + labels.Length);
            for (int i = 0; i < labels.Length; i++)
            {
                var button = GameObject.CreatePrimitive(PrimitiveType.Cube); button.name = labels[i]; button.transform.SetParent(root.transform, false);
                button.transform.localPosition = new Vector3((i % 4 - 1.5f) * 0.222f,0.525f - i / 4 * 0.10f,-0.02f);
                button.transform.localScale = new Vector3(0.205f,0.08f,0.025f); button.GetComponent<Renderer>().sharedMaterial = source;
                var control = button.AddComponent<OrynWorkspaceButton>(); control.Bounds = button.GetComponent<Collider>();
                control.Action = (OrynWorkspaceButton.Command)((int)OrynWorkspaceButton.Command.DroneDemo + i);
                workspace.Buttons[old+i] = control;
                ui.Label(labels[i], button.transform.localPosition + Vector3.back*0.018f,0.0034f);
            }
            ui.status = ui.Label("Select an authored demo to show motion",new Vector3(0,0.325f,-0.025f),0.0033f);
        }
        private TextMesh Label(string text,Vector3 position,float size)
        {
            var go = new GameObject(text); go.transform.SetParent(transform,false); go.transform.localPosition = position;
            var t = go.AddComponent<TextMesh>(); t.text = text; t.font = workspace.Status.font; t.fontSize = 48;
            t.characterSize = size; t.anchor = TextAnchor.MiddleCenter; t.alignment = TextAlignment.Center; t.richText = false;
            go.GetComponent<MeshRenderer>().sharedMaterial = workspace.Status.GetComponent<MeshRenderer>().sharedMaterial;
            return t;
        }
        private void LateUpdate()
        {
            var behavior = workspace.CommandAssembly?.Owner.Mechanical;
            status.text = behavior != null ? behavior.Status : "Generated mesh motion: unsupported / not bound";
        }
    }
}
