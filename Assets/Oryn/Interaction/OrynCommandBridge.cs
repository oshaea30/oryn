using System;
using System.IO;
using System.Linq;
using UnityEngine;

namespace Oryn.Interaction
{
    [Serializable] public sealed class OrynCommandPart
    {
        public string partId, label, status, error;
        public int number, revision;
    }
    [Serializable] public sealed class OrynCommandContext
    {
        public bool ready, partsMode, isolated;
        public int owner;
        public string assetSha256 = "", selectedPartId = "";
        public OrynCommandPart[] parts = Array.Empty<OrynCommandPart>();
    }
    [Serializable] public sealed class OrynCommandSnapshot
    {
        public int schema = 1;
        public string session, contextToken;
        public long utc;
        public bool testGuideAvailable;
        public OrynCommandContext context;
    }
    [Serializable] public sealed class OrynRuntimeCommand
    {
        public int schema;
        public string id, session, contextToken, action, partId;
        public long expires;
    }
    [Serializable] public sealed class OrynCommandReceipt
    {
        public string id, status, message;
    }

    // USB-only local IPC. No network listener, credentials, model execution or arbitrary tools.
    [DefaultExecutionOrder(1100)]
    public sealed class OrynCommandBridge : MonoBehaviour
    {
        public OrynWorkspace Workspace;
        private readonly string session = Guid.NewGuid().ToString("N");
        private string lastContext, token;
        private float nextPoll;
        private OrynTestGuide testGuide;
        private void Start()
        {
#if UNITY_EDITOR || DEVELOPMENT_BUILD
            if (Workspace != null && Workspace.Rig != null)
            {
                testGuide = gameObject.AddComponent<OrynTestGuide>();
                testGuide.Initialize(Workspace.Rig.centerEyeAnchor, Workspace.MarkerMaterial);
            }
#endif
        }
        private string Root => Path.Combine(Application.persistentDataPath, "CommandBridge");
        public static bool IsId(string value) => value != null && value.Length == 32 && value.All(c => c >= '0' && c <= '9' || c >= 'a' && c <= 'f');
        public static string Validate(OrynRuntimeCommand command, string filename, OrynCommandSnapshot state, long now)
        {
            if (command == null || command.schema != 1 || !IsId(command.id) || command.id != filename) return "Invalid command";
            if (state == null || state.context == null || !state.context.ready) return "Headset not ready; release objects and open ORYN";
            if (command.session != state.session || command.contextToken != state.contextToken) return "Selection or workspace changed; ask again";
            if (command.expires < now || command.expires > now + 120) return "Command expired or invalid expiry";
            bool partAction = command.action == "select" || command.action == "isolate";
            if (!partAction && command.action != "explode" && command.action != "reassemble") return "Unsupported action";
            if (partAction && (!OrynKnowledgeStore.IsHash(command.partId) ||
                !state.context.parts.Any(p => p.partId == command.partId && string.IsNullOrEmpty(p.error)))) return "Part unavailable";
            if (!partAction && !string.IsNullOrEmpty(command.partId)) return "Unexpected part target";
            return null;
        }
        private OrynCommandSnapshot Snapshot()
        {
            var context = new OrynCommandContext { ready = Workspace.CommandsReady };
            var assembly = Workspace.CommandAssembly;
            if (assembly != null)
            {
                context.owner = assembly.Owner.Number;
                context.assetSha256 = assembly.AssetHash;
                context.partsMode = assembly.PartsMode; context.isolated = assembly.Isolated;
                var store = new OrynKnowledgeStore(OrynKnowledgeStore.DefaultRoot);
                context.parts = assembly.Parts.Select(part =>
                {
                    var result = new OrynCommandPart { number = part.Number, partId = OrynKnowledgeStore.PartId(assembly.AssetHash, part.GeometryPath),
                        label = "", status = "unidentified", error = "" };
                    try
                    {
                        var record = store.Read(assembly.AssetHash, part.GeometryPath, part.GeometryName);
                        result.label = record.Label; result.status = record.Status; result.revision = record.Revision;
                    }
                    catch (Exception) { result.error = "Saved record unavailable"; result.status = "unavailable"; }
                    if (part == Workspace.CommandSelection) context.selectedPartId = result.partId;
                    return result;
                }).ToArray();
            }
            string encoded = JsonUtility.ToJson(context);
            if (encoded != lastContext) { lastContext = encoded; token = Guid.NewGuid().ToString("N"); }
            return new OrynCommandSnapshot { session = session, contextToken = token,
                utc = DateTimeOffset.UtcNow.ToUnixTimeSeconds(), context = context, testGuideAvailable = testGuide != null };
        }
        private void LateUpdate()
        {
            if (Workspace == null || Time.unscaledTime < nextPoll) return;
            nextPoll = Time.unscaledTime + 0.5f;
            try
            {
                Directory.CreateDirectory(Root);
                testGuide?.Poll(Root, session, DateTimeOffset.UtcNow.ToUnixTimeSeconds());
                var state = Snapshot();
                // Receipts remain durable across process restarts: never replay a claimed command.
                foreach (string path in Directory.EnumerateFiles(Root, "*.command").Take(8))
                {
                    string id = Path.GetFileNameWithoutExtension(path), ack = Path.Combine(Root, id + ".ack");
                    if (!IsId(id)) continue;
                    if (File.Exists(ack)) { File.Delete(path); continue; }
                    OrynRuntimeCommand command = null;
                    try { if (new FileInfo(path).Length <= 4096) command = JsonUtility.FromJson<OrynRuntimeCommand>(File.ReadAllText(path)); }
                    catch (Exception) { }
                    string error = Validate(command, id, state, DateTimeOffset.UtcNow.ToUnixTimeSeconds());
                    var receipt = new OrynCommandReceipt { id = id, status = error == null ? "uncertain" : "rejected", message = error ?? "Claimed; execution not yet confirmed. Do not retry automatically." };
                    OrynKnowledgeStore.AtomicWrite(ack, JsonUtility.ToJson(receipt));
                    if (error == null)
                    {
                        try
                        {
                            var assembly = Workspace.CommandAssembly;
                            var target = assembly.Parts.FirstOrDefault(p => OrynKnowledgeStore.PartId(assembly.AssetHash, p.GeometryPath) == command.partId);
                            Workspace.ApplyCommand(command.action, target);
                            receipt.status = "executed"; receipt.message = "Applied on Quest: " + command.action;
                        }
                        catch (Exception) { receipt.message = "Execution could not be confirmed. Check the headset before another request."; }
                        OrynKnowledgeStore.AtomicWrite(ack, JsonUtility.ToJson(receipt));
                        state = Snapshot();
                    }
                    File.Delete(path);
                }
                OrynKnowledgeStore.AtomicWrite(Path.Combine(Root, "state.json"), JsonUtility.ToJson(state));
            }
            catch (Exception) { nextPoll = Time.unscaledTime + 3f; Debug.LogWarning("ORYN_COMMAND_BRIDGE_IO_UNAVAILABLE"); }
        }
    }
}
