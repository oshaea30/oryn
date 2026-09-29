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
                state.referenceToken = new string('e',32);
                var notice = new OrynExperienceNotice { id = new string('f',32), session = state.session,
                    referenceToken = state.referenceToken, phase = "completed", message = "This motor drives its propeller in the authored model.", sequence = 13, expires = 1030 };
                check(OrynExperienceFeedback.Valid(notice,state,1000), "context-bound answer accepted");
                state.referenceToken = new string('a',32); check(!OrynExperienceFeedback.Valid(notice,state,1000), "answer for old selection rejected");
                notice.referenceToken = state.referenceToken;
                check(!OrynExperienceFeedback.Valid(notice,state,1031), "expired answer rejected");
                notice.message = "<b>unsafe</b>";check(!OrynExperienceFeedback.Valid(notice,state,1000), "markup rejected");notice.message = "Ready";
                notice.phase = "play";check(!OrynExperienceFeedback.Valid(notice,state,1000), "display cannot be an action channel");
                notice.phase = "cancelled";notice.referenceToken = "";check(OrynExperienceFeedback.Valid(notice,state,1000), "cancellation is selection-independent");
                check(OrynExperienceFeedback.Wrap(new string('x',480)).Split('\n').All(line=>line.Length<=52), "long words wrap within panel");
                check(OrynExperienceFeedback.Wrap(string.Join(" ", Enumerable.Repeat(new string('x',27),17))).Split('\n').Length <= 10, "feedback line count is bounded");
                check(OrynExperienceFeedback.Wrap("hello world") == "hello world", "normal text preserved");
                Directory.CreateDirectory("Builds/Mechanical");
                File.WriteAllText("Builds/Mechanical/drone-complete-object.json", JsonUtility.ToJson(subject,true));
                if (SystemInfo.graphicsDeviceType != UnityEngine.Rendering.GraphicsDeviceType.Null)
                {
                    var view = new GameObject("Feedback preview"); view.transform.position = new Vector3(10,10,10);
                    var camera = view.AddComponent<Camera>(); camera.clearFlags = CameraClearFlags.SolidColor;
                    camera.backgroundColor = new Color(0.08f,0.1f,0.12f); camera.fieldOfView = 55; camera.nearClipPlane = 0.01f;
                    var feedback = view.AddComponent<OrynExperienceFeedback>(); feedback.Initialize(view.transform,material);
                    notice.phase = "completed"; notice.referenceToken = state.referenceToken;
                    notice.message = "In this authored model, rotor 0 drives propeller 0; rotor 1 drives propeller 1; rotor 2 drives propeller 2; rotor 3 drives propeller 3. These components belong to the propulsion subsystem. Thrust and flight are not simulated.";
                    check(feedback.Accept(notice,state,1000), "feedback accepted and rendered");
                    check(!feedback.Accept(notice,state,1000), "replayed feedback rejected");
                    var target = new RenderTexture(1050,900,24); camera.targetTexture = target; camera.Render(); RenderTexture.active = target;
                    var image = new Texture2D(1050,900,TextureFormat.RGB24,false); image.ReadPixels(new Rect(0,0,1050,900),0,0); image.Apply();
                    File.WriteAllBytes("Builds/Mechanical/conversation-feedback.png",image.EncodeToPNG());
                    RenderTexture.active = null; camera.targetTexture = null;
                    UnityEngine.Object.DestroyImmediate(image);UnityEngine.Object.DestroyImmediate(target);
                    UnityEngine.Object.DestroyImmediate(view);
                }
                Debug.Log("ORYN_EXPERIENCE_TESTS_OK checks=" + checks);
            }
            finally { UnityEngine.Object.DestroyImmediate(root); UnityEngine.Object.DestroyImmediate(material); }
        }
    }
}
