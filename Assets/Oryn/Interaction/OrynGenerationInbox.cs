using System;
using System.IO;
using System.Security.Cryptography;
using UnityEngine;

namespace Oryn.Interaction
{
    // The USB transport publishes a small manifest LAST, after the GLB is complete.
    // No API credentials, provider URLs or generation code are present on Quest.
    public sealed class OrynGenerationInbox : MonoBehaviour
    {
        public OrynWorkspace Workspace;
        [Serializable] public sealed class Delivery { public string id; public string job_id; public string sha256; public bool demo; }
        [Serializable] public sealed class Receipt { public string id; public string status; public string error; }
        private string folder;
        private float nextCheck;
        private bool reading;
        private void Start()
        {
            folder = Path.Combine(Application.persistentDataPath, "GenerationInbox");
            Directory.CreateDirectory(folder);
            Debug.Log("ORYN_GENERATION_INBOX_READY transport=usb");
        }
        public static bool ValidDelivery(Delivery delivery, string fileStem)
        {
            return delivery != null && Guid.TryParseExact(delivery.id, "N", out _) && delivery.id == fileStem &&
                Guid.TryParseExact(delivery.job_id, "N", out _) && IsHash(delivery.sha256);
        }
        private static bool IsHash(string value)
        {
            if (value == null || value.Length != 64) return false;
            foreach (char c in value) if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
            return true;
        }
        private async void Update()
        {
            if (reading || folder == null || Workspace == null || Time.unscaledTime < nextCheck) return;
            nextCheck = Time.unscaledTime + 2;
            reading = true;
            string stem = null;
            try
            {
                var manifests = Directory.GetFiles(folder, "*.json");
                Array.Sort(manifests, StringComparer.Ordinal);
                foreach (string path in manifests)
                {
                    stem = Path.GetFileNameWithoutExtension(path);
                    if (!Guid.TryParseExact(stem, "N", out _) || File.Exists(Path.Combine(folder, stem + ".ack"))) continue;
                    if (new FileInfo(path).Length > 4096) throw new InvalidDataException("Delivery manifest too large");
                    var delivery = JsonUtility.FromJson<Delivery>(File.ReadAllText(path));
                    if (!ValidDelivery(delivery, stem)) throw new InvalidDataException("Invalid delivery manifest");
                    string model = Path.Combine(folder, stem + ".glb");
                    var info = new FileInfo(model);
                    if (!info.Exists || info.Length < 20 || info.Length > OrynRuntimeModel.MaximumFileBytes) throw new InvalidDataException("Missing or oversized delivered GLB");
                    string hash;
                    using (var stream = File.OpenRead(model))
                    using (var sha = SHA256.Create()) hash = BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
                    if (hash != delivery.sha256) throw new InvalidDataException("GLB checksum mismatch");
                    if (await Workspace.ImportModel(model, delivery.demo ? "demo_usb" : "generated_usb"))
                    {
                        Acknowledge(stem, "loaded", "");
                        Debug.Log("ORYN_GENERATION_DELIVERED id=" + stem + " demo=" + delivery.demo);
                    }
                    break; // One import at a time. No space/focus: retry after next check.
                }
            }
            catch (OperationCanceledException) { }
            catch (Exception error)
            {
                Debug.LogWarning("ORYN_GENERATION_IMPORT_FAILED " + error.Message);
                if (stem != null && Guid.TryParseExact(stem, "N", out _))
                {
                    try { Acknowledge(stem, "failed", "Import rejected. Check device log and GLB compatibility."); }
                    catch (IOException) { Debug.LogWarning("ORYN_GENERATION_RECEIPT_FAILED"); }
                }
            }
            finally { reading = false; }
        }
        private void Acknowledge(string id, string status, string error)
        {
            string target = Path.Combine(folder, id + ".ack");
            string temp = target + ".partial";
            File.WriteAllText(temp, JsonUtility.ToJson(new Receipt { id = id, status = status, error = error }));
            File.Move(temp, target);
        }
    }
}
