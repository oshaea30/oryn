using System.Collections.Generic;
using UnityEngine;

namespace Oryn.Interaction
{
    // Geometry ownership stays with the runtime importer. Parts are interaction
    // wrappers, not separately owned meshes or inferred semantic components.
    public sealed class OrynAssembly : MonoBehaviour
    {
        public const int MaximumParts = 64;
        public OrynWorkspaceObject Owner { get; private set; }
        public string AssetHash { get; private set; }
        public string SourcePath { get; private set; }
        public IReadOnlyList<OrynWorkspaceObject> Parts => parts;
        public bool PartsMode { get; private set; }
        public bool Isolated { get; private set; }
        public float SpreadAmount { get; private set; }
        private readonly List<OrynWorkspaceObject> parts = new List<OrynWorkspaceObject>();
        private readonly List<Vector3> homePositions = new List<Vector3>();
        private readonly List<Quaternion> homeRotations = new List<Quaternion>();
        private readonly List<Vector3> homeScales = new List<Vector3>();

        public static OrynAssembly Create(OrynWorkspaceObject owner, OrynRuntimeModel model, Material outline)
        {
            var renderers = model.GetComponentsInChildren<MeshRenderer>(true);
            if (renderers.Length < 2 || renderers.Length > MaximumParts) return null;
            // Validate the complete set before changing the hierarchy.
            foreach (var renderer in renderers)
                if (renderer.GetComponent<MeshFilter>()?.sharedMesh == null) return null;
            var assembly = owner.gameObject.AddComponent<OrynAssembly>();
            assembly.Owner = owner;
            assembly.AssetHash = model.SourceHash; assembly.SourcePath = model.SourcePath;
            var addresses = new Dictionary<MeshRenderer, string>();
            foreach (var renderer in renderers) addresses.Add(renderer, OrynKnowledgeStore.GeometryPath(renderer.transform, model.transform));
            foreach (var renderer in renderers)
            {
                var geometry = renderer.transform;
                var meshBounds = renderer.GetComponent<MeshFilter>().sharedMesh.bounds;
                Vector3 center = geometry.TransformPoint(meshBounds.center);
                var wrapper = new GameObject("Part " + geometry.name, typeof(BoxCollider), typeof(MeshRenderer));
                wrapper.transform.SetParent(owner.transform, false);
                wrapper.transform.SetPositionAndRotation(center, owner.transform.rotation);
                var localBounds = new Bounds(Vector3.zero, Vector3.zero);
                for (int corner = 0; corner < 8; corner++)
                {
                    var sign = new Vector3((corner & 1) == 0 ? -1 : 1, (corner & 2) == 0 ? -1 : 1, (corner & 4) == 0 ? -1 : 1);
                    localBounds.Encapsulate(wrapper.transform.InverseTransformPoint(geometry.TransformPoint(meshBounds.center + Vector3.Scale(meshBounds.extents, sign))));
                }
                // Reparent with world pose preserved. The importer component remains
                // under the assembly owner and disposes resources only with that owner.
                geometry.SetParent(wrapper.transform, true);
                var part = wrapper.AddComponent<OrynWorkspaceObject>();
                part.GeometryPath = addresses[renderer]; part.GeometryName = geometry.name;
                part.AttachPart(assembly, localBounds, outline);
                part.ShapeName = "Part " + geometry.name;
                part.Number = assembly.parts.Count + 1;
                assembly.parts.Add(part);
                assembly.homePositions.Add(wrapper.transform.localPosition);
                assembly.homeRotations.Add(wrapper.transform.localRotation);
                assembly.homeScales.Add(wrapper.transform.localScale);
                part.Bounds.enabled = false;
            }
            return assembly;
        }

        public void SetPartsMode(bool enabled)
        {
            if (!enabled) { Reassemble(); return; }
            Owner.State.ReleaseAll();
            Owner.Apply(false, false);
            Owner.Bounds.enabled = false;
            PartsMode = true;
            for (int i = 0; i < parts.Count; i++)
            {
                var part = parts[i];
                part.State.ReleaseAll();
                part.State.Reset(new Pose(part.transform.position, part.transform.rotation));
                part.Bounds.enabled = part.gameObject.activeSelf;
            }
        }

        public void Explode()
        {
            BeginSpread();
            SetSpread(1f);
        }
        public void BeginSpread()
        {
            RestoreHomes();
            SetPartsMode(true);
            SpreadAmount = 0;
        }
        public void SetSpread(float amount)
        {
            if (!PartsMode || !float.IsFinite(amount)) return;
            SpreadAmount = Mathf.Clamp01(amount);
            for (int i = 0; i < parts.Count; i++)
            {
                // Home positions are centered in the owner's normalized coordinates.
                parts[i].transform.localPosition = homePositions[i] * Mathf.Lerp(1f, 2.1f, SpreadAmount);
                SyncState(parts[i]);
            }
        }

        public void ToggleIsolate(OrynWorkspaceObject chosen)
        {
            if (!PartsMode || chosen == null || chosen.PartOf != this) return;
            bool hideOthers = !Isolated;
            foreach (var part in parts)
            {
                part.State.ReleaseAll();
                part.gameObject.SetActive(!hideOthers || part == chosen);
                part.Bounds.enabled = part.gameObject.activeSelf;
            }
            Isolated = hideOthers;
        }

        public void ResetPart(OrynWorkspaceObject part)
        {
            int index = parts.IndexOf(part);
            if (index < 0) return;
            RestoreHome(index);
            part.Bounds.enabled = PartsMode && part.gameObject.activeSelf;
        }

        public void Reassemble()
        {
            SpreadAmount = 0;
            RestoreHomes();
            PartsMode = false;
            Owner.Bounds.enabled = true;
            foreach (var part in parts) part.Bounds.enabled = false;
        }

        private void RestoreHomes()
        {
            Owner.State.ReleaseAll();
            Isolated = false;
            for (int i = 0; i < parts.Count; i++)
            {
                parts[i].gameObject.SetActive(true);
                RestoreHome(i);
            }
        }
        private void RestoreHome(int index)
        {
            var part = parts[index];
            part.transform.localPosition = homePositions[index];
            part.transform.localRotation = homeRotations[index];
            part.transform.localScale = homeScales[index];
            SyncState(part);
            part.Apply(false, false);
        }
        private static void SyncState(OrynWorkspaceObject part)
        { part.State.Reset(new Pose(part.transform.position, part.transform.rotation)); }
    }
}
