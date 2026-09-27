using System.Collections.Generic;
using UnityEngine;

namespace Oryn.Interaction
{
    public static class OrynObjectPlacement
    {
        public static Pose WithinReach(Pose eye)
        {
            var upright = OrynMenuPlacement.InFrontOf(eye).rotation;
            return new Pose(eye.position + upright * Vector3.forward * 0.45f - Vector3.up * 0.08f, Quaternion.identity);
        }
        public static OrynWorkspaceObject RecoveryTarget(IReadOnlyList<OrynWorkspaceObject> objects, OrynWorkspaceObject selected)
        {
            var root = selected != null && selected.PartOf != null ? selected.PartOf.Owner : selected;
            if (root != null && root.Assembly != null) return root;
            // A cube or legacy single-mesh demo must not prevent assembly recovery.
            for (int i = objects.Count - 1; i >= 0; i--)
                if (objects[i] != null && objects[i].Assembly != null) return objects[i];
            if (root != null && root.IsImported) return root;
            for (int i = objects.Count - 1; i >= 0; i--)
                if (objects[i] != null && objects[i].IsImported) return objects[i];
            return null;
        }
        public static void Recover(OrynWorkspaceObject root, Pose eye)
        {
            if (root == null) return;
            if (root.Assembly != null) root.Assembly.Reassemble();
            root.State.ReleaseAll();
            root.State.Reset(WithinReach(eye));
            root.Apply(false, true);
        }
    }
}
