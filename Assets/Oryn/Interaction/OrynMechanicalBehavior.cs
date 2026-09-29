using System;
using System.Collections.Generic;
using UnityEngine;

namespace Oryn.Interaction
{
    // Applied after workspace manipulation. Each binding is a geometry child of an
    // existing interaction wrapper: movement never overwrites grab/explode poses.
    [DefaultExecutionOrder(100)]
    public sealed class OrynMechanicalBehavior : MonoBehaviour
    {
        public OrynMechanicalDefinition Definition { get; private set; }
        public bool Running { get; private set; }
        public float Speed { get; private set; } = 1;
        public double Cycles { get; private set; }
        private OrynMechanicalEvaluator evaluator;
        private Pose[] poses, rest;
        private Transform[] geometry;
        private Vector3[] localHomes;
        private Quaternion[] rotationHomes;
        private OrynWorkspaceObject[] boundParts;
        private Bounds[] meshBounds;
        private OrynAssembly assembly;
        public string Status => "AUTHORED DEMO · NOT VERIFIED\n" + (Running ? "PLAYING" : "PAUSED") + " · " + Speed.ToString("0.##") + "x";

        public void Configure(OrynMechanicalDefinition definition, OrynAssembly owner, Dictionary<string,Transform> bindings)
        {
            if (owner == null || bindings == null) throw new ArgumentException("Assembly and bindings required");
            var checkedEvaluator = new OrynMechanicalEvaluator(definition);
            foreach (var link in checkedEvaluator.Definition.Links)
                if (!bindings.TryGetValue(link.GeometryId, out var target) || target == null ||
                    target.parent == null || target.parent.GetComponent<OrynWorkspaceObject>()?.PartOf != owner ||
                    target.GetComponent<MeshFilter>()?.sharedMesh == null)
                    throw new ArgumentException("Explicit assembly geometry binding required");
            evaluator = checkedEvaluator; Definition = evaluator.Definition; assembly = owner;
            int n = Definition.Links.Length;
            poses = new Pose[n]; rest = new Pose[n]; geometry = new Transform[n]; localHomes = new Vector3[n]; rotationHomes = new Quaternion[n];
            boundParts = new OrynWorkspaceObject[n]; meshBounds = new Bounds[n];
            evaluator.Evaluate(0, rest);
            for (int i = 0; i < n; i++)
            {
                geometry[i] = bindings[Definition.Links[i].GeometryId];
                localHomes[i] = geometry[i].localPosition; rotationHomes[i] = geometry[i].localRotation;
                boundParts[i] = geometry[i].parent.GetComponent<OrynWorkspaceObject>();
                meshBounds[i] = geometry[i].GetComponent<MeshFilter>().sharedMesh.bounds;
            }
            StopHome();
        }
        public string ComponentId(OrynWorkspaceObject part)
        {
            if (boundParts == null) return "";
            int index = Array.IndexOf(boundParts, part);
            return index < 0 ? "" : Definition.Links[index].Id;
        }
        public OrynWorkspaceObject Component(string id)
        {
            for (int i = 0; i < Definition.Links.Length; i++) if (Definition.Links[i].Id == id) return boundParts[i];
            throw new ArgumentException("Unknown component");
        }
        public void Demonstrate(string id)
        {
            if (!string.IsNullOrEmpty(id))
            {
                var ids = new HashSet<string> { id };
                var selectedLink = Array.Find(Definition.Links, link => link.Id == id);
                if (selectedLink == null) throw new ArgumentException("Unknown component");
                // A propeller demonstration includes its driver; a motor includes its moving children.
                if (!string.IsNullOrEmpty(selectedLink.DriverId)) ids.Add(selectedLink.DriverId);
                var parts = new HashSet<OrynWorkspaceObject>();
                for (int i = 0; i < Definition.Links.Length; i++)
                {
                    var link = Definition.Links[i];
                    if (ids.Contains(link.ParentId ?? "") || ids.Contains(link.DriverId ?? "")) ids.Add(link.Id);
                    if (ids.Contains(link.Id)) parts.Add(boundParts[i]);
                }
                assembly.IsolateParts(parts);
            }
            Play();
        }
        public void Play() { if (evaluator != null) Running = true; }
        public void Pause() { Running = false; }
        public void StopHome() { Running = false; Cycles = 0; ApplyPose(); }
        public void SetSpeed(float speed)
        { if (!float.IsFinite(speed) || speed < 0.05f || speed > 2) throw new ArgumentOutOfRangeException(nameof(speed)); Speed = speed; }
        public void Seek(double cycles)
        { if (double.IsNaN(cycles) || double.IsInfinity(cycles) || cycles < 0 || cycles > 1000000) throw new ArgumentOutOfRangeException(nameof(cycles)); Cycles = cycles; ApplyPose(); }
        public void Advance(double seconds)
        {
            if (double.IsNaN(seconds) || double.IsInfinity(seconds) || seconds < 0 || seconds > 1) throw new ArgumentOutOfRangeException(nameof(seconds));
            if (Running && evaluator != null) Cycles += seconds * Speed * Definition.CyclesPerSecond;
            ApplyPose();
        }
        private void LateUpdate() { if (evaluator != null) Advance(Math.Min(Time.deltaTime, 0.1f)); }
        private void OnDisable() { Pause(); }
        private void OnApplicationPause(bool paused) { if (paused) Pause(); }
        private void ApplyPose()
        {
            if (evaluator == null) return;
            evaluator.Evaluate(Cycles, poses);
            for (int i = 0; i < geometry.Length; i++)
            {
                geometry[i].localPosition = localHomes[i] + poses[i].position - rest[i].position;
                geometry[i].localRotation = poses[i].rotation * Quaternion.Inverse(rest[i].rotation) * rotationHomes[i];
                // Keep touch/grab bounds on the visibly moving geometry, not at home.
                var part = boundParts[i]; var b = meshBounds[i];
                var bounds = new Bounds(part.transform.InverseTransformPoint(geometry[i].TransformPoint(b.center)), Vector3.zero);
                for (int c = 0; c < 8; c++)
                    bounds.Encapsulate(part.transform.InverseTransformPoint(geometry[i].TransformPoint(b.center + Vector3.Scale(b.extents,
                        new Vector3((c & 1) == 0 ? -1 : 1, (c & 2) == 0 ? -1 : 1, (c & 4) == 0 ? -1 : 1)))));
                part.UpdateMechanicalBounds(bounds);
            }
        }
        public void IsolateSubsystem(string subsystem)
        {
            var parts = new HashSet<OrynWorkspaceObject>();
            for (int i = 0; i < Definition.Links.Length; i++) if (Definition.Links[i].Subsystem == subsystem) parts.Add(boundParts[i]);
            if (parts.Count == 0) throw new ArgumentException("Unknown subsystem");
            assembly.IsolateParts(parts);
        }
    }
}
