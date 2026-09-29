using UnityEngine;
using Oryn.Interaction;

namespace Oryn.Preview
{
    // Desktop UI uses the exact same runtime component as Quest, without an AI agent.
    public sealed class OrynMechanicalPreview : MonoBehaviour
    {
        public Material Surface;
        public OrynMechanicalBehavior Current { get; private set; }
        private bool engine = true;
        private void Start() { if (Current == null) Show(true); }
        public void Show(bool useEngine)
        {
            if (Current != null) { Current.gameObject.SetActive(false); Destroy(Current.gameObject); }
            engine = useEngine;
            var root = GameObject.CreatePrimitive(PrimitiveType.Cube); root.name = "Authored mechanism demonstration";
            root.GetComponent<Renderer>().sharedMaterial = Surface;
            var owner = root.AddComponent<OrynWorkspaceObject>();
            Current = OrynMechanicalBenchmarks.Attach(owner, engine, Surface, Surface);
            Current.Play();
        }
        private void OnGUI()
        {
            if (Current == null) return;
            GUILayout.BeginArea(new Rect(20,20,440,320),GUI.skin.box);
            GUILayout.Label("ORYN / MECHANICAL BEHAVIOR");
            GUILayout.Label(Current.Definition.Title);
            GUILayout.Label(Current.Status);
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Drone demo")) Show(false);
            if (GUILayout.Button("V8 demo")) Show(true);
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Play / resume")) Current.Play();
            if (GUILayout.Button("Pause")) Current.Pause();
            if (GUILayout.Button("Stop / home")) Current.StopHome();
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Slow 0.15x")) Current.SetSpeed(0.15f);
            if (GUILayout.Button("1x")) Current.SetSpeed(1);
            if (GUILayout.Button("Inspect quarter-cycle")) { Current.Pause(); Current.Seek(0.25); }
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Explode")) Current.GetComponent<OrynAssembly>().Explode();
            if (GUILayout.Button("Reassemble / show all")) Current.GetComponent<OrynAssembly>().Reassemble();
            GUILayout.EndHorizontal();
            if (GUILayout.Button(engine ? "Only rotating assembly" : "Only propulsion")) Current.IsolateSubsystem(engine ? "rotating_assembly" : "propulsion");
            GUILayout.Label(Current.Definition.Explanation);
            GUILayout.Label("Exploded/moved parts retain illustrative motion, not a physically connected assembly.");
            GUILayout.EndArea();
        }
    }
}
