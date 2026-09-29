using System;
using System.Collections.Generic;
using UnityEngine;

namespace Oryn.Interaction
{
    public enum OrynMotionKind { Fixed, Rotation, Translation, Reciprocation, SliderCrankPiston, SliderCrankRod }

    [Serializable]
    public sealed class OrynMechanicalLink
    {
        public string Id, GeometryId, ParentId, DriverId, Subsystem;
        public OrynMotionKind Kind;
        public Vector3 HomePosition, HomeEuler, Axis = Vector3.forward, Pivot;
        public float Ratio = 1, PhaseDegrees, Travel, CrankRadius, RodLength;
        // The provenance of authoring and strength of evidence are separate axes.
        public string DerivedBy = "human_authored", EvidenceStatus = "unsupported";
        public string[] ReferenceIds = Array.Empty<string>();
        public string VerificationRecordId = "";
    }

    [Serializable]
    public sealed class OrynMechanicalDefinition
    {
        public int SchemaVersion = 1;
        public string Id, Revision, Title, Scope, Explanation;
        public float CyclesPerSecond = 0.5f;
        public OrynMechanicalLink[] Links;

        public void Validate()
        {
            if (SchemaVersion != 1 || string.IsNullOrWhiteSpace(Id) || string.IsNullOrWhiteSpace(Revision) ||
                string.IsNullOrWhiteSpace(Scope) || Links == null || Links.Length < 1 || Links.Length > 64 ||
                !float.IsFinite(CyclesPerSecond) || CyclesPerSecond <= 0 || CyclesPerSecond > 2)
                throw new ArgumentException("Invalid bounded mechanical definition");
            var prior = new Dictionary<string, OrynMechanicalLink>();
            var geometry = new HashSet<string>();
            foreach (var link in Links)
            {
                if (link == null || string.IsNullOrWhiteSpace(link.Id) || string.IsNullOrWhiteSpace(link.GeometryId) ||
                    prior.ContainsKey(link.Id) || !geometry.Add(link.GeometryId) || !Enum.IsDefined(typeof(OrynMotionKind), link.Kind))
                    throw new ArgumentException("Unique mechanical and geometry IDs required");
                // Topological order prevents cycles. Parent is a semantic assembly relationship;
                // Driver supplies timing, never implicitly reparents an interaction transform.
                if ((!string.IsNullOrEmpty(link.ParentId) && !prior.ContainsKey(link.ParentId)) ||
                    (!string.IsNullOrEmpty(link.DriverId) && !prior.ContainsKey(link.DriverId)))
                    throw new ArgumentException("Parent/driver must precede child");
                if (!Finite(link.HomePosition) || !Finite(link.HomeEuler) || !Finite(link.Axis) || !Finite(link.Pivot) ||
                    !float.IsFinite(link.Ratio) || Mathf.Abs(link.Ratio) > 8 || !float.IsFinite(link.PhaseDegrees) ||
                    !float.IsFinite(link.Travel) || Mathf.Abs(link.Travel) > 2 || !float.IsFinite(link.CrankRadius) ||
                    !float.IsFinite(link.RodLength) || link.Axis.sqrMagnitude < 0.99f || link.Axis.sqrMagnitude > 1.01f)
                    throw new ArgumentException("Invalid mechanical dimensions/axis");
                if (link.Kind == OrynMotionKind.SliderCrankPiston || link.Kind == OrynMotionKind.SliderCrankRod)
                {
                    // This version supports planar, zero-offset slider cranks in XY only.
                    if (Mathf.Abs(link.Axis.z) > 0.0001f || link.CrankRadius <= 0 || link.RodLength <= link.CrankRadius ||
                        link.RodLength > 2 || string.IsNullOrEmpty(link.DriverId) || prior[link.DriverId].Kind != OrynMotionKind.Rotation)
                        throw new ArgumentException("Unsupported slider-crank geometry/driver");
                }
                if (string.IsNullOrWhiteSpace(link.DerivedBy) || link.ReferenceIds == null ||
                    (link.EvidenceStatus != "unsupported" && link.EvidenceStatus != "reference-supported" && link.EvidenceStatus != "verified") ||
                    (link.EvidenceStatus != "unsupported" && link.ReferenceIds.Length == 0) ||
                    (link.EvidenceStatus == "verified" && string.IsNullOrWhiteSpace(link.VerificationRecordId)))
                    throw new ArgumentException("Mechanical evidence/provenance required");
                prior.Add(link.Id, link);
            }
        }
        private static bool Finite(Vector3 v) => float.IsFinite(v.x) && float.IsFinite(v.y) && float.IsFinite(v.z);
    }

    // Pure evaluator: all poses are assembly-local, no physics, network or inference.
    public sealed class OrynMechanicalEvaluator
    {
        public readonly OrynMechanicalDefinition Definition;
        private readonly double[] phases;
        private readonly int[] drivers;
        public OrynMechanicalEvaluator(OrynMechanicalDefinition definition)
        {
            definition.Validate();
            // Freeze the validated description against subsequent caller mutation.
            Definition = JsonUtility.FromJson<OrynMechanicalDefinition>(JsonUtility.ToJson(definition));
            phases = new double[Definition.Links.Length]; drivers = new int[phases.Length];
            var indices = new Dictionary<string,int>();
            for (int i = 0; i < drivers.Length; i++)
            {
                var link = Definition.Links[i]; drivers[i] = string.IsNullOrEmpty(link.DriverId) ? -1 : indices[link.DriverId];
                indices.Add(link.Id, i);
            }
        }
        public void Evaluate(double cycles, Pose[] poses)
        {
            if (double.IsNaN(cycles) || double.IsInfinity(cycles) || poses == null || poses.Length != phases.Length)
                throw new ArgumentException("Finite phase and exact pose buffer required");
            for (int i = 0; i < phases.Length; i++)
            {
                var link = Definition.Links[i];
                double phase = (drivers[i] < 0 ? cycles : phases[drivers[i]]) * link.Ratio + link.PhaseDegrees / 360.0;
                phases[i] = phase;
                float degrees = (float)((phase % 1.0) * 360.0);
                float sine = (float)Math.Sin(phase * Math.PI * 2);
                var pose = new Pose(link.HomePosition, Quaternion.Euler(link.HomeEuler));
                switch (link.Kind)
                {
                    case OrynMotionKind.Rotation:
                        var spin = Quaternion.AngleAxis(degrees, link.Axis);
                        pose.position = link.Pivot + spin * (link.HomePosition - link.Pivot);
                        pose.rotation = spin * pose.rotation;
                        break;
                    case OrynMotionKind.Translation:
                        // Repeating constant-speed out-and-back travel, no accumulating drift.
                        float triangle = 1f - Mathf.Abs(2f * Mathf.Repeat((float)(phase % 1), 1) - 1f);
                        pose.position += link.Axis * link.Travel * triangle;
                        break;
                    case OrynMotionKind.Reciprocation:
                        pose.position += link.Axis * link.Travel * sine;
                        break;
                    case OrynMotionKind.SliderCrankPiston:
                    case OrynMotionKind.SliderCrankRod:
                        Vector3 pin = new Vector3((float)Math.Cos(phase * Math.PI * 2), sine, 0) * link.CrankRadius;
                        float along = Vector3.Dot(pin, link.Axis);
                        float lateralSquared = (pin - along * link.Axis).sqrMagnitude;
                        Vector3 piston = link.Axis * (along + Mathf.Sqrt(Mathf.Max(0, link.RodLength * link.RodLength - lateralSquared)));
                        pose = link.Kind == OrynMotionKind.SliderCrankPiston
                            ? new Pose(link.Pivot + piston, Quaternion.FromToRotation(Vector3.up, link.Axis))
                            : new Pose(link.Pivot + (pin + piston) * 0.5f, Quaternion.FromToRotation(Vector3.up, piston - pin));
                        break;
                }
                poses[i] = pose;
            }
        }
    }
}
