using System;
using System.IO;
using System.Linq;
using UnityEngine;

namespace Oryn.Interaction
{
    [Serializable] public sealed class OrynExperienceComponent
    {
        public string id, geometryId, name, subsystem, parentId, driverId, explanation;
        public string provenance, evidence;
        public string[] referenceIds;
    }
    [Serializable] public sealed class OrynExperienceObject
    {
        public string id, revision, instance, title, scope, explanation;
        public string[] actions;
        public OrynExperienceComponent[] components;
    }
    [Serializable] public sealed class OrynExperienceState
    {
        public int schema = 1;
        public string session, contextToken, referenceToken, selected = "";
        public int focusInstance;
        public long utc;
        public bool ready, running, isolated, partsMode;
        public float speed, spread;
        public OrynExperienceObject subject;
    }
    [Serializable] public sealed class OrynExperienceCommand
    {
        public int schema = 1;
        public string id, session, contextToken, action, component = "", subsystem = "";
        public long expires;
    }

    [Serializable] public sealed class OrynExperienceReceipt
    {
        public string id, status, message, referenceToken;
    }

    // Application-owned USB transport. Separate identity/records from generated meshes.
    [DefaultExecutionOrder(1101)]
    public sealed class OrynExperienceBridge : MonoBehaviour
    {
        public OrynWorkspace Workspace;
        private readonly string session = Guid.NewGuid().ToString("N");
        private string lastContext, token, lastReference, referenceToken;
        private float nextPoll;
        private OrynExperienceFeedback feedback;
        private void Start()
        {
            if (Workspace == null || Workspace.Rig == null) return;
            feedback = gameObject.AddComponent<OrynExperienceFeedback>();
            feedback.Initialize(Workspace.Rig.centerEyeAnchor, Workspace.MarkerMaterial);
        }
        private string Root => Path.Combine(Application.persistentDataPath, "ExperienceBridge");
        public static readonly string[] Actions = { "select", "isolate_component", "isolate_subsystem", "demonstrate",
            "play", "pause", "slow", "normal", "explode", "reassemble", "restore" };

        public static OrynExperienceObject Describe(OrynMechanicalBehavior behavior, int number)
        {
            if (behavior == null || behavior.Definition.Id != "authored-drone-propulsion") return null;
            var d = behavior.Definition;
            return new OrynExperienceObject { id = d.Id, revision = d.Revision, instance = number.ToString(),
                title = d.Title, scope = d.Scope, explanation = d.Explanation, actions = Actions,
                components = d.Links.Select(link => new OrynExperienceComponent {
                    id = link.Id, geometryId = link.GeometryId, name = link.Id.Replace('_',' '),
                    subsystem = link.Subsystem, parentId = link.ParentId ?? "", driverId = link.DriverId ?? "",
                    explanation = Explanation(link), provenance = link.DerivedBy, evidence = link.EvidenceStatus,
                    referenceIds = link.ReferenceIds }).ToArray() };
        }
        private static string Explanation(OrynMechanicalLink link)
        {
            string suffix = link.Id.Contains("_") ? link.Id.Substring(link.Id.LastIndexOf('_') + 1) : "";
            if (link.Id == "chassis") return "In this authored model, the chassis supports the four arms.";
            if (link.Id.StartsWith("arm_")) return "In this authored model, this arm supports motor " + suffix + ".";
            if (link.Id.StartsWith("motor_")) return "In this authored model, this motor houses rotor " + suffix + ", which drives propeller " + suffix + ". The motor housing stays fixed.";
            if (link.Id.StartsWith("rotor_")) return "In this authored model, this rotor drives propeller " + suffix + " at the same angular speed.";
            return "In this authored model, this propeller follows rotor " + suffix + ". Thrust and flight are not simulated.";
        }
        public static string Validate(OrynExperienceCommand command, string filename, OrynExperienceState state, long now)
        {
            if (command == null || command.schema != 1 || !OrynCommandBridge.IsId(command.id) || command.id != filename) return "Invalid request";
            if (state == null || !state.ready) return "Release objects and open ORYN before requesting an action";
            if (command.session != state.session || command.contextToken != state.contextToken) return "Selection or workspace changed; ask again";
            if (command.expires < now || command.expires > now + 30) return "Request expired";
            if (command.action == "show_drone")
                return string.IsNullOrEmpty(command.component) && string.IsNullOrEmpty(command.subsystem) ? null : "Unexpected target";
            if (state.subject == null || !state.subject.actions.Contains(command.action)) return "Action unavailable for this object";
            bool part = command.action == "select" || command.action == "isolate_component" || command.action == "demonstrate";
            if (part && !string.IsNullOrEmpty(command.component))
            { if (!state.subject.components.Any(p => p.id == command.component)) return "Component unavailable"; }
            else if (part && command.action != "demonstrate") return "Select a component first";
            else if (!string.IsNullOrEmpty(command.component)) return "Unexpected component";
            if (command.action == "isolate_subsystem")
            { if (!state.subject.components.Any(p => p.subsystem == command.subsystem)) return "Subsystem unavailable"; }
            else if (!string.IsNullOrEmpty(command.subsystem)) return "Unexpected subsystem";
            return null;
        }
        private OrynExperienceState Snapshot()
        {
            var assembly = Workspace.CommandAssembly;
            var behavior = assembly?.Owner.Mechanical;
            var subject = Describe(behavior, assembly == null ? 0 : assembly.Owner.Number);
            var state = new OrynExperienceState { session = session, ready = Workspace.ExperienceReady,
                focusInstance = Workspace.CommandSelection == null ? 0 : Workspace.CommandSelection.Number,
                subject = subject, selected = subject == null ? "" : behavior.ComponentId(Workspace.CommandSelection),
                running = behavior != null && behavior.Running, speed = behavior == null ? 1 : behavior.Speed,
                isolated = assembly != null && assembly.Isolated, partsMode = assembly != null && assembly.PartsMode,
                spread = assembly == null ? 0 : assembly.SpreadAmount };
            string reference = session + ":" + (subject == null ? "" : subject.id + ":" + subject.revision + ":" + subject.instance) + ":" + state.focusInstance + ":" + state.selected;
            if (reference != lastReference) { lastReference = reference; referenceToken = Guid.NewGuid().ToString("N"); }
            state.referenceToken = referenceToken;
            // Pose/animation time is intentionally excluded; selection, mode and capability changes are not.
            string encoded = JsonUtility.ToJson(state);
            if (encoded != lastContext) { lastContext = encoded; token = Guid.NewGuid().ToString("N"); }
            state.contextToken = token; state.utc = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            return state;
        }
        private void LateUpdate()
        {
            if (Workspace == null || Time.unscaledTime < nextPoll) return;
            nextPoll = Time.unscaledTime + 0.1f;
            try
            {
                Directory.CreateDirectory(Root);
                var state = Snapshot();
                foreach (string path in Directory.EnumerateFiles(Root, "*.command").Take(8))
                {
                    string id = Path.GetFileNameWithoutExtension(path), ack = Path.Combine(Root, id + ".ack");
                    if (!OrynCommandBridge.IsId(id)) continue;
                    if (File.Exists(ack)) { File.Delete(path); continue; }
                    OrynExperienceCommand command = null;
                    try { if (new FileInfo(path).Length <= 4096) command = JsonUtility.FromJson<OrynExperienceCommand>(File.ReadAllText(path)); } catch (Exception) { }
                    string error = Validate(command, id, state, DateTimeOffset.UtcNow.ToUnixTimeSeconds());
                    var receipt = new OrynExperienceReceipt { id = id, status = error == null ? "uncertain" : "rejected", message = error ?? "Execution claimed; do not retry" };
                    OrynKnowledgeStore.AtomicWrite(ack, JsonUtility.ToJson(receipt));
                    if (error == null)
                    {
                        try { Workspace.ApplyExperience(command); receipt.status = "executed"; receipt.message = "Applied on Quest: " + command.action; }
                        catch (Exception) { receipt.message = "Execution could not be confirmed. Check the headset."; }
                        state = Snapshot();
                        receipt.referenceToken = state.referenceToken;
                        OrynKnowledgeStore.AtomicWrite(ack, JsonUtility.ToJson(receipt));
                    }
                    File.Delete(path);
                }
                OrynKnowledgeStore.AtomicWrite(Path.Combine(Root, "state.json"), JsonUtility.ToJson(state));
                feedback?.Poll(Root, state, state.utc);
            }
            catch (Exception) { nextPoll = Time.unscaledTime + 3; Debug.LogWarning("ORYN_EXPERIENCE_BRIDGE_UNAVAILABLE"); }
        }
    }
}
