using System.Collections.Generic;
using UnityEngine;

namespace Oryn.Interaction
{
    // Deliberately separate, authored teaching fixtures. Never labels generated
    // islands or pretends a decorative Meshy exterior contains this mechanism.
    public static class OrynMechanicalBenchmarks
    {
        public static OrynMechanicalDefinition Definition(bool engine)
        {
            var links = new List<OrynMechanicalLink>();
            if (!engine)
            {
                links.Add(Link("chassis", OrynMotionKind.Fixed, Vector3.zero, "structure"));
                for (int i = 0; i < 4; i++)
                {
                    var p = new Vector3(i % 2 == 0 ? -0.32f : 0.32f, 0, i < 2 ? -0.32f : 0.32f);
                    var arm = Link("arm_" + i, OrynMotionKind.Fixed, p * 0.5f, "structure"); arm.ParentId = "chassis"; links.Add(arm);
                    var motor = Link("motor_" + i, OrynMotionKind.Fixed, p, "propulsion"); motor.ParentId = arm.Id; links.Add(motor);
                    var rotor = Link("rotor_" + i, OrynMotionKind.Rotation, p + Vector3.up * 0.055f, "propulsion");
                    rotor.ParentId = motor.Id; rotor.Axis = Vector3.up; rotor.Ratio = i == 0 || i == 3 ? 1 : -1; links.Add(rotor);
                    var prop = Link("propeller_" + i, OrynMotionKind.Rotation, p + Vector3.up * 0.08f, "propulsion");
                    prop.ParentId = rotor.Id; prop.DriverId = rotor.Id; prop.Axis = Vector3.up; links.Add(prop);
                }
            }
            else
            {
                var crank = Link("crankshaft", OrynMotionKind.Rotation, Vector3.zero, "rotating_assembly");
                crank.HomeEuler = new Vector3(90, 0, 0); links.Add(crank);
                float[] offsets = { 0, 90, 270, 180 };
                for (int station = 0; station < 4; station++)
                {
                    float z = (station - 1.5f) * 0.18f;
                    var pin = Link("crankpin_" + station, OrynMotionKind.Rotation, new Vector3(0.07f, 0, z), "rotating_assembly");
                    pin.ParentId = "crankshaft"; pin.DriverId = "crankshaft"; pin.PhaseDegrees = offsets[station];
                    pin.Pivot = new Vector3(0, 0, z); pin.HomeEuler = new Vector3(90, 0, 0); links.Add(pin);
                    var web = Link("crankweb_" + station, OrynMotionKind.Rotation, new Vector3(0.035f, 0, z), "rotating_assembly");
                    web.ParentId = "crankshaft"; web.DriverId = "crankshaft"; web.PhaseDegrees = offsets[station];
                    web.Pivot = pin.Pivot; web.HomeEuler = new Vector3(0,0,90); links.Add(web);
                    for (int bank = 0; bank < 2; bank++)
                    {
                        string suffix = station + "_" + bank;
                        Vector3 axis = new Vector3(bank == 0 ? -1 : 1, 1, 0).normalized;
                        foreach (var kind in new[] { OrynMotionKind.SliderCrankRod, OrynMotionKind.SliderCrankPiston })
                        {
                            var link = Link((kind == OrynMotionKind.SliderCrankRod ? "rod_" : "piston_") + suffix, kind, Vector3.zero, "rotating_assembly");
                            link.ParentId = kind == OrynMotionKind.SliderCrankRod ? pin.Id : "rod_" + suffix;
                            link.DriverId = "crankshaft"; link.PhaseDegrees = offsets[station]; link.Axis = axis;
                            link.Pivot = new Vector3(0, 0, z + (bank == 0 ? -0.018f : 0.018f));
                            link.CrankRadius = 0.07f; link.RodLength = 0.22f; links.Add(link);
                        }
                    }
                }
                links.Add(Link("support_left", OrynMotionKind.Fixed, new Vector3(-0.29f, 0.08f, 0), "structure"));
                links.Add(Link("support_right", OrynMotionKind.Fixed, new Vector3(0.29f, 0.08f, 0), "structure"));
            }
            return new OrynMechanicalDefinition {
                Id = engine ? "authored-v8-kinematics" : "authored-drone-propulsion", Revision = "1", Scope = "authored_family_demonstration",
                Title = engine ? "V8 mechanism / authored demo" : "Drone propulsion / authored demo",
                Explanation = engine ? "One shaft drives eight slider-crank linkages. Illustrative dimensions and phasing; not a specific engine, firing order or verified generated-mesh mapping."
                    : "Four authored motor rotors drive propellers 1:1. Illustrative direction and speed; no thrust, flight controller or aerodynamic simulation.",
                CyclesPerSecond = 0.5f, Links = links.ToArray()
            };
        }
        private static OrynMechanicalLink Link(string id, OrynMotionKind kind, Vector3 p, string subsystem)
            => new OrynMechanicalLink { Id = id, GeometryId = id, Kind = kind, HomePosition = p, Pivot = p, Subsystem = subsystem,
                DerivedBy = "oryn_authored_benchmark_v1", EvidenceStatus = "unsupported" };

        public static OrynMechanicalBehavior Attach(OrynWorkspaceObject owner, bool engine, Material material, Material outline)
        {
            var definition = Definition(engine);
            var evaluator = new OrynMechanicalEvaluator(definition);
            var poses = new Pose[definition.Links.Length]; evaluator.Evaluate(0, poses);
            var model = OrynRuntimeModel.AuthoredDemonstration(definition.Title, new Bounds(new Vector3(0, 0.09f, 0), new Vector3(1.1f, 0.75f, 1.1f)));
            var bindings = new Dictionary<string,Transform>();
            for (int i = 0; i < definition.Links.Length; i++)
            {
                var link = definition.Links[i]; string id = link.Id;
                bool cylinder = engine ? !id.StartsWith("support") && !id.StartsWith("crankweb") : id.StartsWith("motor") || id.StartsWith("rotor");
                var part = GameObject.CreatePrimitive(cylinder ? PrimitiveType.Cylinder : PrimitiveType.Cube);
                part.name = id; part.transform.SetParent(model.transform, false);
                var collider = part.GetComponent<Collider>(); collider.enabled = false;
                if (Application.isPlaying) Object.Destroy(collider); else Object.DestroyImmediate(collider);
                Vector3 scale;
                if (engine)
                    scale = id == "crankshaft" ? new Vector3(0.035f, 0.39f, 0.035f) : id.StartsWith("crankweb") ? new Vector3(0.027f, 0.07f, 0.027f) : id.StartsWith("crankpin") ? new Vector3(0.045f, 0.045f, 0.045f) :
                        id.StartsWith("rod") ? new Vector3(0.017f, 0.11f, 0.017f) : id.StartsWith("piston") ? new Vector3(0.09f, 0.035f, 0.09f) : new Vector3(0.025f, 0.28f, 0.75f);
                else
                    scale = id == "chassis" ? new Vector3(0.28f, 0.09f, 0.28f) : id.StartsWith("arm") ? new Vector3(0.04f, 0.04f, 0.45f) :
                        id.StartsWith("propeller") ? new Vector3(0.29f, 0.022f, 0.045f) : new Vector3(0.075f, 0.025f, 0.075f);
                part.transform.localPosition = poses[i].position; part.transform.localRotation = poses[i].rotation; part.transform.localScale = scale;
                if (id.StartsWith("arm")) part.transform.localRotation = Quaternion.LookRotation(link.HomePosition.normalized);
                var renderer = part.GetComponent<MeshRenderer>(); renderer.sharedMaterial = material;
                var color = new MaterialPropertyBlock();
                color.SetColor("_Color", link.Subsystem == "structure" ? new Color(0.18f,0.23f,0.29f) :
                    id.StartsWith("piston") || id.StartsWith("propeller") ? new Color(0.15f,0.8f,0.8f) : new Color(0.95f,0.6f,0.2f));
                renderer.SetPropertyBlock(color); bindings.Add(id, part.transform);
            }
            owner.AttachModel(model, outline); owner.ShapeName = definition.Title;
            var behavior = owner.gameObject.AddComponent<OrynMechanicalBehavior>(); behavior.Configure(definition, owner.Assembly, bindings);
            return behavior;
        }
    }
}
