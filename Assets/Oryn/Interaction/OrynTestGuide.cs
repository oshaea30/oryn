using System;
using System.IO;
using System.Linq;
using UnityEngine;

namespace Oryn.Interaction
{
    [Serializable] public sealed class OrynTestNotice
    {
        public int schema = 1, sequence;
        public string id, session, phase, message;
        public long expires;
    }
    [Serializable] public sealed class OrynTestNoticeReceipt
    {
        public string id, session, phase;
        public int sequence;
    }

    // Development display only. This never selects, moves or executes an object action.
    public sealed class OrynTestGuide : MonoBehaviour
    {
        private Transform panel;
        private TextMesh label;
        private AudioSource speaker;
        private AudioClip tone;
        private Material backing;
        private OrynTestNotice current;
        private bool stalled;

        public static bool Valid(OrynTestNotice value, string session, long now)
        {
            return value != null && value.schema == 1 && OrynCommandBridge.IsId(value.id) &&
                value.session == session && value.sequence > 0 && value.sequence < 100000 &&
                value.expires >= now && value.expires <= now + 30 &&
                new[] { "ready", "testing", "passed", "failed", "blocked" }.Contains(value.phase) &&
                !string.IsNullOrWhiteSpace(value.message) && value.message.Length <= 240 &&
                !value.message.Any(c => c < 32 && c != '\n' || c == '<' || c == '>');
        }
        public static bool Newer(OrynTestNotice value, OrynTestNotice previous) =>
            previous == null || value.id != previous.id || value.sequence > previous.sequence;

        public void Initialize(Transform eye, Material material)
        {
            panel = new GameObject("ORYN Test Guide").transform;
            panel.SetParent(eye, false); panel.localPosition = new Vector3(0, 0.22f, 0.95f);
            var board = GameObject.CreatePrimitive(PrimitiveType.Quad);
            board.name = "Test status backing"; board.transform.SetParent(panel, false);
            board.transform.localPosition = new Vector3(0, 0, 0.006f);
            board.transform.localScale = new Vector3(0.88f, 0.25f, 1);
            Destroy(board.GetComponent<Collider>());
            backing = new Material(material); backing.color = new Color(0.025f, 0.04f, 0.065f, 1);
            board.GetComponent<Renderer>().sharedMaterial = backing;
            label = new GameObject("Test instructions").AddComponent<TextMesh>();
            label.transform.SetParent(panel, false); label.anchor = TextAnchor.MiddleCenter;
            label.alignment = TextAlignment.Center; label.characterSize = 0.009f;
            label.fontSize = 48; label.richText = false;
            label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            label.GetComponent<MeshRenderer>().sharedMaterial = label.font.material;
            speaker = panel.gameObject.AddComponent<AudioSource>();
            speaker.playOnAwake = false; speaker.spatialBlend = 0; speaker.volume = 0.2f;
            const int rate = 24000;
            float[] samples = new float[rate / 3];
            for (int i = 0; i < samples.Length; i++)
                samples[i] = Mathf.Sin(2 * Mathf.PI * 660 * i / rate) * Mathf.Sin(Mathf.PI * i / samples.Length) * 0.35f;
            tone = AudioClip.Create("ORYN test finished", samples.Length, 1, rate, false);
            tone.SetData(samples, 0); speaker.clip = tone;
            panel.gameObject.SetActive(false);
        }
        public void Poll(string root, string session, long now)
        {
            if (panel == null) return;
            string path = Path.Combine(root, "test-status.json");
            try
            {
                if (File.Exists(path) && new FileInfo(path).Length <= 4096)
                {
                    var next = JsonUtility.FromJson<OrynTestNotice>(File.ReadAllText(path));
                    if (Valid(next, session, now) && Newer(next, current))
                    {
                        bool notify = current == null || next.id != current.id || next.phase != current.phase;
                        current = next; stalled = false;
                        Show(next.phase.ToUpperInvariant() + "\n" + next.message,
                            next.phase == "passed" ? Color.green : next.phase == "ready" || next.phase == "testing" ? Color.cyan : new Color(1, 0.65f, 0.2f));
                        if (notify && next.phase != "ready" && next.phase != "testing") speaker.Play();
                        OrynKnowledgeStore.AtomicWrite(Path.Combine(root, "test-status.ack"), JsonUtility.ToJson(
                            new OrynTestNoticeReceipt { id = next.id, session = session, sequence = next.sequence, phase = next.phase }));
                    }
                }
            }
            catch (Exception) { /* A failed display never alters the action bridge. */ }
            if (current != null && !stalled && now > current.expires && (current.phase == "ready" || current.phase == "testing"))
            {
                stalled = true;
                Show("BLOCKED\nTest connection interrupted.\nNo result confirmed. You can remove the headset.", new Color(1, 0.65f, 0.2f));
                speaker.Play();
            }
        }
        private void Show(string text, Color color)
        {
            label.text = text; label.color = color; panel.gameObject.SetActive(true);
        }
        private void OnDestroy()
        {
            if (panel != null) Destroy(panel.gameObject);
            if (tone != null) Destroy(tone);
            if (backing != null) Destroy(backing);
        }
    }
}
