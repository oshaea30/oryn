using System;
using UnityEngine;

namespace Oryn.Interaction
{
    public sealed class OrynPartInspector : MonoBehaviour
    {
        public TextMesh Details;
        // Candidate labels are user choices, NEVER predictions about a mesh.
        public static readonly string[] Labels = { "", "Chassis", "Battery", "Arm", "Motor", "Propeller", "Flight controller", "Housing", "Fastener", "Other" };
        private OrynKnowledgeStore store;
        private OrynWorkspaceObject target;
        private OrynPartRecord record;
        private int draft;
        private string notice = "";
        public bool CanEdit => target != null && record != null;
        public bool CanSave => CanEdit && Labels[draft] != record.Label;
        private OrynKnowledgeStore Store => store ?? (store = new OrynKnowledgeStore(OrynKnowledgeStore.DefaultRoot));
        public void Bind(OrynWorkspaceObject selected)
        {
            if (selected == target) return;
            target = selected; record = null; draft = 0; notice = "";
            if (target != null && target.PartOf != null && OrynKnowledgeStore.IsHash(target.PartOf.AssetHash))
            {
                try
                {
                    record = Store.Ensure(target.PartOf.AssetHash, target.GeometryPath, target.GeometryName);
                    draft = Math.Max(0, Array.IndexOf(Labels, record.Label));
                }
                catch (Exception error) { notice = "Record unavailable; not overwritten"; Debug.LogWarning("ORYN_RECORD_READ_FAILED " + error.GetType().Name); }
            }
            Render();
        }
        public void Cycle(int direction)
        {
            if (!CanEdit) return;
            draft = (draft + direction + Labels.Length) % Labels.Length;
            notice = "Draft only - SAVE to apply"; Render();
        }
        public void Save()
        {
            if (!CanSave) return;
            try
            {
                // Cache first; never claim restart readiness if the model could not be saved.
                Store.RememberModel(target.PartOf.SourcePath, target.PartOf.AssetHash);
                record = Store.Annotate(record, Labels[draft]);
                notice = "Saved locally; not verified";
                Debug.Log("ORYN_RECORD_SAVED part=" + record.partId + " revision=" + record.Revision);
            }
            catch (Exception error) { notice = "Save failed; reselect to retry"; Debug.LogWarning("ORYN_RECORD_SAVE_FAILED " + error.GetType().Name); }
            Render();
        }
        private void Render()
        {
            if (Details == null) return;
            if (!CanEdit)
            {
                var behavior = target == null ? null : (target.PartOf != null ? target.PartOf.Owner.Mechanical : target.Mechanical);
                if (behavior != null)
                {
                    Details.text = "AUTHORED MECHANISM\n\n" + (target.PartOf != null ? target.GeometryName : behavior.Definition.Title) +
                        "\n\nDemonstration only.\nDimensions / ratios authored.\nNo reference verification.\nNot mapped to generated pieces.";
                    return;
                }
                Details.text = "PART KNOWLEDGE\n\nExplode, then grab a piece.\nNo identities are inferred.\n\nLabels are user annotations.\n" + notice;
                return;
            }
            string label = record.Label.Length == 0 ? "Unidentified" : record.Label;
            Details.text = "PART " + target.Number + " / KNOWLEDGE\n" +
                "ID: " + record.partId.Substring(0, 10) + "  Rev " + record.Revision + "\n" +
                "Saved: " + label + "\n" +
                "Status: " + (record.Label.Length == 0 ? "UNIDENTIFIED" : "USER ANNOTATION") + "\n" +
                "Source: " + (record.Revision == 0 ? "none" : "local user / unverified") + "\n" +
                "Evidence / connections: unknown\n\n" +
                "Draft: " + (Labels[draft].Length == 0 ? "Unidentified (clear)" : Labels[draft]) + "\n" + notice;
        }
    }
}
