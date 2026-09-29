using System;
using System.IO;
using System.Linq;
using Oryn.Interaction;
using UnityEngine;

namespace Oryn.Editor
{
    public static class OrynExperienceTests
    {
        public static void Run()
        {
            int checks = 0;
            Action<bool,string> check = (ok,name) => { if (!ok) throw new Exception("Experience: " + name); checks++; };
            var material = new Material(Shader.Find("Unlit/Color"));
            var root = GameObject.CreatePrimitive(PrimitiveType.Cube);
            var owner = root.AddComponent<OrynWorkspaceObject>();
            try
            {
                var behavior = OrynMechanicalBenchmarks.Attach(owner, false, material, material);
                var subject = OrynExperienceBridge.Describe(behavior, 1);
                check(subject.components.Length == 17, "complete drone declares 17 components");
                check(subject.components.All(c => c.evidence == "unsupported"), "authored does not imply verified");
                check(!OrynKnowledgeStore.IsHash(owner.Assembly.AssetHash), "no generated identity fabricated");
                foreach (var component in subject.components)
                    check(behavior.ComponentId(behavior.Component(component.id)) == component.id, "stable explicit binding");
                check(behavior.ComponentId(owner) == "", "whole object is not a component");
                behavior.Demonstrate("motor_0");
                var visible = owner.Assembly.Parts.Where(p => p.gameObject.activeSelf).Select(behavior.ComponentId).OrderBy(x => x).ToArray();
                check(visible.SequenceEqual(new[] { "motor_0", "propeller_0", "rotor_0" }), "motor demonstration reveals only its drive group");
                check(behavior.Running, "demonstration starts playback");
                owner.Assembly.Reassemble();
                check(behavior.Running && owner.Assembly.Parts.All(p => p.gameObject.activeSelf), "reassembly preserves playback and visibility");
                behavior.Demonstrate("propeller_1");
                check(owner.Assembly.Parts.Count(p => p.gameObject.activeSelf) == 2, "propeller demonstration includes its driver");
                var state = new OrynExperienceState { session = new string('a',32), contextToken = new string('b',32), ready = true, subject = subject };
                var command = new OrynExperienceCommand { id = new string('c',32), session = state.session, contextToken = state.contextToken, expires = 1030, action = "play" };
                Func<string> validate = () => OrynExperienceBridge.Validate(command, command.id, state, 1000);
                check(validate() == null, "declared mechanical action accepted");
                command.action = "isolate_component"; command.component = "motor_0"; check(validate() == null, "component accepted");
                command.component = "invented"; check(validate() != null, "undeclared component denied");
                command.component = ""; command.action = "isolate_subsystem"; command.subsystem = "propulsion"; check(validate() == null, "declared subsystem accepted");
                command.subsystem = "battery"; check(validate() != null, "undeclared subsystem denied");
                command.subsystem = ""; command.action = "play";
                command.contextToken = new string('d',32); check(validate() != null, "stale selection denied");command.contextToken = state.contextToken;
                command.session = new string('d',32); check(validate() != null, "other session denied");command.session = state.session;
                state.ready = false;check(validate() != null, "held or unfocused action denied");state.ready = true;
                command.expires = 999;check(validate() != null, "expired action denied");command.expires = 1031;check(validate() != null, "unbounded expiry denied");command.expires = 1030;
                command.action = "delete";check(validate() != null, "arbitrary action denied");
                state.subject = null;command.action = "show_drone";check(validate() == null, "acquisition works without existing object");
                command.action = "play";check(validate() != null, "motion needs complete object");
                Directory.CreateDirectory("Builds/Mechanical");
                File.WriteAllText("Builds/Mechanical/drone-complete-object.json", JsonUtility.ToJson(subject,true));
                Debug.Log("ORYN_EXPERIENCE_TESTS_OK checks=" + checks);
            }
            finally { UnityEngine.Object.DestroyImmediate(root); UnityEngine.Object.DestroyImmediate(material); }
        }
    }
}
