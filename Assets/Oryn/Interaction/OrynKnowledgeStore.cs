using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

namespace Oryn.Interaction
{
    [Serializable] public sealed class OrynPartRecord
    {
        public int schema = 1;
        public string assetSha256, partId, geometryPath, geometryName;
        public OrynAnnotation[] history = Array.Empty<OrynAnnotation>();
        public string Label => history.Length == 0 ? "" : history[history.Length - 1].label;
        public string Status => Label.Length == 0 ? "unidentified" : "user_annotation";
        public int Revision => history.Length;
    }
    [Serializable] public sealed class OrynAnnotation
    {
        public int revision;
        public string label, source, verification, utc;
    }

    // Exact facts live in application records, not model conversation memory.
    // v1 intentionally cannot author verified identities or inferred relationships.
    public sealed class OrynKnowledgeStore
    {
        public const string MappingVersion = "renderer-path-v1";
        private readonly string root;
        public OrynKnowledgeStore(string folder) { root = folder; }
        public static string DefaultRoot => Path.Combine(Application.persistentDataPath, "Knowledge");
        public static string HashFile(string path)
        {
            using (var file = File.OpenRead(path))
            using (var sha = SHA256.Create()) return Hex(sha.ComputeHash(file));
        }
        private static string Hex(byte[] bytes) => BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant();
        public static bool IsHash(string value) => value != null && value.Length == 64 && value.All(c => (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'));
        public static string PartId(string asset, string geometryPath)
        {
            if (!IsHash(asset) || string.IsNullOrEmpty(geometryPath)) throw new InvalidDataException("Invalid geometry identity");
            using (var sha = SHA256.Create()) return Hex(sha.ComputeHash(Encoding.UTF8.GetBytes(asset + "/" + MappingVersion + "/" + geometryPath)));
        }
        // Capture ALL addresses before wrappers reparent any imported geometry.
        public static string GeometryPath(Transform geometry, Transform model)
        {
            string path = "";
            for (var node = geometry; node != model; node = node.parent)
            {
                if (node == null) throw new InvalidDataException("Geometry outside model");
                path = "/" + node.GetSiblingIndex() + path;
            }
            return MappingVersion + (path.Length == 0 ? "/root" : path);
        }
        private string RecordPath(string asset, string id)
        {
            if (!IsHash(asset) || !IsHash(id)) throw new InvalidDataException("Invalid record identity");
            return Path.Combine(root, "Records", asset, id + ".json");
        }
        public OrynPartRecord Read(string asset, string geometryPath, string geometryName)
        {
            string id = PartId(asset, geometryPath), path = RecordPath(asset, id);
            if (!File.Exists(path)) return new OrynPartRecord { assetSha256 = asset, partId = id, geometryPath = geometryPath, geometryName = geometryName };
            if (new FileInfo(path).Length > 1024 * 1024) throw new InvalidDataException("Record exceeds limit");
            var record = JsonUtility.FromJson<OrynPartRecord>(File.ReadAllText(path));
            if (record == null || record.schema != 1 || record.assetSha256 != asset || record.partId != id ||
                record.geometryPath != geometryPath || record.geometryName != geometryName || record.history == null || record.history.Length > 1000)
                throw new InvalidDataException("Record binding/schema mismatch");
            for (int i = 0; i < record.history.Length; i++)
            {
                var note = record.history[i];
                if (note == null || note.revision != i + 1 || !ValidLabel(note.label) || note.source != "local_user" ||
                    note.verification != "unverified" || !DateTimeOffset.TryParse(note.utc, out _))
                    throw new InvalidDataException("Invalid annotation history");
            }
            return record;
        }
        public OrynPartRecord Ensure(string asset, string geometryPath, string geometryName)
        {
            var record = Read(asset, geometryPath, geometryName);
            string path = RecordPath(asset, record.partId);
            if (!File.Exists(path)) AtomicWrite(path, JsonUtility.ToJson(record, true));
            return record;
        }
        public static bool ValidLabel(string label) => label != null && label.Length <= 60 && label == label.Trim() &&
            !label.Any(c => char.IsControl(c) || c == '<' || c == '>');
        public OrynPartRecord Annotate(OrynPartRecord expected, string label)
        {
            if (expected == null || !ValidLabel(label)) throw new InvalidDataException("Invalid label");
            var current = Read(expected.assetSha256, expected.geometryPath, expected.geometryName);
            if (current.Revision != expected.Revision) throw new InvalidOperationException("Record changed; select the part again");
            if (current.Label == label) return current;
            if (current.Revision >= 1000) throw new InvalidDataException("Annotation history limit reached");
            var notes = current.history.ToList();
            notes.Add(new OrynAnnotation { revision = current.Revision + 1, label = label, source = "local_user", verification = "unverified", utc = DateTime.UtcNow.ToString("o") });
            current.history = notes.ToArray();
            AtomicWrite(RecordPath(current.assetSha256, current.partId), JsonUtility.ToJson(current, true));
            return current;
        }
        // Atomic publish, with the previous complete record retained for recovery.
        public static void AtomicWrite(string path, string text)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            string temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                using (var file = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    var bytes = Encoding.UTF8.GetBytes(text);
                    file.Write(bytes, 0, bytes.Length); file.Flush(true);
                }
                if (File.Exists(path)) File.Replace(temp, path, path + ".bak"); else File.Move(temp, path);
            }
            finally { if (File.Exists(temp)) File.Delete(temp); }
        }
        public void RememberModel(string source, string hash)
        {
            if (!IsHash(hash) || HashFile(source) != hash) throw new InvalidDataException("Model changed; cannot remember it");
            string target = Path.Combine(root, "Models", hash + ".glb");
            Directory.CreateDirectory(Path.GetDirectoryName(target));
            if (!File.Exists(target))
            {
                string temp = target + "." + Guid.NewGuid().ToString("N") + ".tmp";
                try
                {
                    File.Copy(source, temp);
                    if (HashFile(temp) != hash) throw new InvalidDataException("Model cache checksum mismatch");
                    File.Move(temp, target);
                }
                finally { if (File.Exists(temp)) File.Delete(temp); }
            }
            if (HashFile(target) != hash) throw new InvalidDataException("Saved model checksum mismatch");
            AtomicWrite(Path.Combine(root, "last-model.txt"), hash);
        }
        public string ResumeModel()
        {
            string pointer = Path.Combine(root, "last-model.txt");
            if (!File.Exists(pointer)) return null;
            if (new FileInfo(pointer).Length != 64) throw new InvalidDataException("Invalid saved model pointer");
            string hash = File.ReadAllText(pointer);
            if (!IsHash(hash)) throw new InvalidDataException("Invalid saved model identity");
            string path = Path.Combine(root, "Models", hash + ".glb");
            if (!File.Exists(path) || new FileInfo(path).Length > OrynRuntimeModel.MaximumFileBytes || HashFile(path) != hash)
                throw new InvalidDataException("Saved model missing or changed");
            return path;
        }
    }
}
