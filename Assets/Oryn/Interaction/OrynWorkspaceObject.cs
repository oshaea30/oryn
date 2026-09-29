using UnityEngine;

namespace Oryn.Interaction
{
    public sealed class OrynWorkspaceObject : MonoBehaviour
    {
        public string ShapeName = "Cube";
        public OrynTwoHandState State { get; private set; }
        public Collider Bounds { get; private set; }
        public int Number { get; set; }
        public OrynMechanicalBehavior Mechanical => GetComponent<OrynMechanicalBehavior>();
        public OrynAssembly Assembly { get; private set; }
        public OrynAssembly PartOf { get; private set; }
        public bool IsImported { get; private set; }
        public string GeometryPath { get; internal set; }
        public string GeometryName { get; internal set; }
        private Vector3 originalScale;
        private Renderer surface;
        private MaterialPropertyBlock colors;
        private LineRenderer importOutline;
        private static readonly int[] OutlineOrder = { 0, 1, 3, 2, 0, 4, 5, 1, 5, 7, 3, 7, 6, 2, 6, 4 };
        public void UpdateMechanicalBounds(UnityEngine.Bounds bounds)
        {
            var box = (BoxCollider)Bounds;
            box.center = bounds.center; box.size = Vector3.Max(bounds.size, Vector3.one * 0.015f);
            if (importOutline == null) return;
            for (int i = 0; i < OutlineOrder.Length; i++)
            {
                int c = OutlineOrder[i];
                importOutline.SetPosition(i, box.center + Vector3.Scale(box.size * 0.5f,
                    new Vector3((c & 1) == 0 ? -1 : 1, (c & 2) == 0 ? -1 : 1, (c & 4) == 0 ? -1 : 1)));
            }
        }
        public void AttachModel(OrynRuntimeModel model, Material outlineMaterial)
        {
            Initialize();
            IsImported = true;
            model.transform.SetParent(transform, false);
            ((BoxCollider)Bounds).size = Vector3.Max(model.LocalBounds.size, Vector3.one * 0.02f);
            surface.enabled = false;
            ShapeName = "Model";
            CreateOutline(outlineMaterial);
            model.gameObject.SetActive(true);
            Assembly = OrynAssembly.Create(this, model, outlineMaterial);
        }
        public void AttachPart(OrynAssembly assembly, UnityEngine.Bounds localBounds, Material outlineMaterial)
        {
            Initialize();
            PartOf = assembly;
            var box = (BoxCollider)Bounds;
            box.center = localBounds.center;
            box.size = Vector3.Max(localBounds.size, Vector3.one * 0.015f);
            surface.enabled = false;
            CreateOutline(outlineMaterial);
        }
        private void CreateOutline(Material outlineMaterial)
        {
            importOutline = new GameObject("Interaction bounds").AddComponent<LineRenderer>();
            importOutline.transform.SetParent(transform, false);
            importOutline.sharedMaterial = outlineMaterial;
            importOutline.useWorldSpace = false; importOutline.widthMultiplier = 0.002f;
            int[] order = { 0, 1, 3, 2, 0, 4, 5, 1, 5, 7, 3, 7, 6, 2, 6, 4 };
            importOutline.positionCount = order.Length;
            for (int i = 0; i < order.Length; i++)
                importOutline.SetPosition(i, ((BoxCollider)Bounds).center + Vector3.Scale(((BoxCollider)Bounds).size * 0.5f,
                    new Vector3((order[i] & 1) == 0 ? -1 : 1, (order[i] & 2) == 0 ? -1 : 1, (order[i] & 4) == 0 ? -1 : 1)));
            importOutline.enabled = false;
        }
        private void Awake() { Initialize(); }
        public void Initialize()
        {
            if (State != null) return;
            State = new OrynTwoHandState(new Pose(transform.position, transform.rotation));
            originalScale = transform.localScale;
            Bounds = GetComponent<Collider>();
            surface = GetComponent<Renderer>();
            colors = new MaterialPropertyBlock();
        }
        public void Apply(bool hovered, bool selected)
        {
            transform.SetPositionAndRotation(State.ObjectPose.position, State.ObjectPose.rotation);
            transform.localScale = originalScale * State.Scale;
            Color color = State.Mode == OrynTwoHandState.Operation.Resize ? new Color(0.8f, 0.4f, 1f) :
                State.Mode == OrynTwoHandState.Operation.Waiting ? new Color(0.25f, 0.85f, 0.85f) :
                State.HoldCount > 0 ? new Color(1f, 0.72f, 0.12f) : hovered ? new Color(0.1f, 1f, 0.75f) :
                selected ? new Color(0.1f, 0.75f, 1f) : new Color(0.08f, 0.4f, 0.8f);
            colors.SetColor("_Color", color);
            surface.SetPropertyBlock(colors);
            if (importOutline != null)
            { importOutline.enabled = hovered || selected || State.HoldCount > 0; importOutline.SetPropertyBlock(colors); }
        }
    }
}
