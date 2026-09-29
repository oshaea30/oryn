using System;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;

namespace Oryn.Interaction
{
    [Serializable] public sealed class OrynExperienceNotice
    {
        public int schema = 1;
        public long sequence, expires;
        public string id, session, referenceToken, phase, message;
    }

    // Read-only application feedback. No command parsing or object operations.
    public sealed class OrynExperienceFeedback : MonoBehaviour
    {
        private Transform panel, eye, boardTransform;
        private TextMesh label;
        private Material backing;
        private OrynExperienceNotice current;
        private long latestSequence;
        private string lastPayload;

        public static bool Valid(OrynExperienceNotice value, OrynExperienceState state, long now)
        {
            if (value == null || state == null || value.schema != 1 || !OrynCommandBridge.IsId(value.id) ||
                value.session != state.session || value.sequence <= 0 || value.expires < now || value.expires > now + 30 ||
                !new[] { "working", "pending", "completed", "failed", "rejected", "uncertain", "cancelled" }.Contains(value.phase) ||
                string.IsNullOrWhiteSpace(value.message) || value.message.Length > 480 ||
                value.message.Any(c => c < 32 || c == '<' || c == '>')) return false;
            bool contextual = value.phase == "working" || value.phase == "pending" || value.phase == "completed";
            return contextual ? value.referenceToken == state.referenceToken && OrynCommandBridge.IsId(value.referenceToken)
                : string.IsNullOrEmpty(value.referenceToken);
        }
        public static string Wrap(string value)
        {
            const int width = 52;
            var result = new StringBuilder(); int column = 0;
            foreach (string word in value.Split(' '))
            {
                if (word.Length == 0) continue;
                if (column > 0 && column + 1 + word.Length > width) { result.Append('\n'); column = 0; }
                else if (column > 0) { result.Append(' '); column++; }
                foreach (char c in word)
                {
                    if (column == width) { result.Append('\n'); column = 0; }
                    result.Append(c); column++;
                }
            }
            var lines = result.ToString().Split('\n');
            if (lines.Length <= 10) return result.ToString();
            return string.Join("\n", lines.Take(9)) + "\n" + lines[9].Substring(0, Math.Min(lines[9].Length, width - 1)) + "…";
        }
        public void Initialize(Transform anchor, Material material)
        {
            eye = anchor;
            panel = new GameObject("ORYN conversation").transform;
            var board = GameObject.CreatePrimitive(PrimitiveType.Quad);
            boardTransform = board.transform;
            board.transform.SetParent(panel, false); board.transform.localPosition = Vector3.forward * 0.006f;
            board.transform.localScale = new Vector3(0.8f, 0.38f, 1);
            Dispose(board.GetComponent<Collider>());
            backing = new Material(material); backing.color = new Color(0.025f, 0.04f, 0.065f, 1);
            board.GetComponent<Renderer>().sharedMaterial = backing;
            label = new GameObject("ORYN answer").AddComponent<TextMesh>();
            label.transform.SetParent(panel, false); label.transform.localPosition = new Vector3(-0.36f, 0.155f, 0);
            label.anchor = TextAnchor.UpperLeft; label.alignment = TextAlignment.Left;
            label.characterSize = 0.006f; label.fontSize = 48; label.richText = false;
            label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label.GetComponent<MeshRenderer>().sharedMaterial = label.font.material;
            panel.gameObject.SetActive(false);
        }
        public bool Accept(OrynExperienceNotice next, OrynExperienceState state, long now)
        {
            if (panel == null || !Valid(next, state, now) || next.sequence <= latestSequence) return false;
            latestSequence = next.sequence; current = next;
            string heading = next.phase == "working" ? "ORYN · THINKING" : next.phase == "pending" ? "ORYN · WORKING" :
                next.phase == "completed" ? "ORYN" : next.phase == "cancelled" ? "ORYN · CANCELLED" : "ORYN · CHECK REQUEST";
            string body = Wrap(next.message);
            float height = Mathf.Max(0.24f, (body.Split('\n').Length + 2) * 0.035f + 0.07f);
            boardTransform.localScale = new Vector3(0.8f, height, 1);
            label.transform.localPosition = new Vector3(-0.36f, height * 0.5f - 0.035f, 0);
            label.text = heading + "\n\n" + body;
            label.color = next.phase == "failed" || next.phase == "rejected" || next.phase == "uncertain"
                ? new Color(1, 0.75f, 0.5f) : new Color(0.75f, 1, 0.9f);
            Vector3 forward = Vector3.ProjectOnPlane(eye.forward, Vector3.up).normalized;
            if (forward.sqrMagnitude < 0.01f) forward = Vector3.forward;
            panel.SetPositionAndRotation(eye.position + forward * 0.95f + Vector3.down * 0.18f, Quaternion.LookRotation(forward));
            panel.gameObject.SetActive(true);
            return true;
        }
        public void Poll(string root, OrynExperienceState state, long now)
        {
            if (panel == null) return;
            string path = Path.Combine(root, "feedback.json");
            try
            {
                if (File.Exists(path) && new FileInfo(path).Length <= 8192)
                {
                    string raw = File.ReadAllText(path);
                    if (raw != lastPayload)
                    {
                        lastPayload = raw;
                        var next = JsonUtility.FromJson<OrynExperienceNotice>(raw);
                        if (Accept(next, state, now))
                            OrynKnowledgeStore.AtomicWrite(Path.Combine(root, "feedback.ack"), JsonUtility.ToJson(next));
                    }
                }
            }
            catch (Exception) { /* A display failure never changes object behavior. */ }
            if (current != null && (now > current.expires ||
                (!string.IsNullOrEmpty(current.referenceToken) && current.referenceToken != state.referenceToken)))
                panel.gameObject.SetActive(false);
        }
        private static void Dispose(UnityEngine.Object value)
        {
            if (Application.isPlaying) Destroy(value); else DestroyImmediate(value);
        }
        private void OnDisable() { if (panel != null) panel.gameObject.SetActive(false); }
        private void OnDestroy()
        {
            if (panel != null) Dispose(panel.gameObject);
            if (backing != null) Dispose(backing);
        }
    }
}
