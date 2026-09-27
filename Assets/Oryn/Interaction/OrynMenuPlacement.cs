using UnityEngine;

namespace Oryn.Interaction
{
    public static class OrynMenuPlacement
    {
        public const float Distance = 0.70f, BelowEyes = 0.23f, LayoutCenter = 0.32f, RayLength = 2.5f;
        public static Pose InFrontOf(Pose eye)
        {
            // Use eye-relative height (standing or seated), never a floor coordinate.
            // Keep the panel upright even when looking down at a piece or straight up.
            Vector3 forward = Vector3.ProjectOnPlane(eye.rotation * Vector3.forward, Vector3.up);
            if (forward.sqrMagnitude < 0.01f)
                forward = Vector3.Cross(eye.rotation * Vector3.right, Vector3.up);
            forward = Vector3.ProjectOnPlane(forward, Vector3.up).normalized;
            if (forward.sqrMagnitude < 0.01f) forward = Vector3.forward;
            Vector3 right = Vector3.Cross(Vector3.up, forward);
            return new Pose(eye.position + forward * Distance - Vector3.up * BelowEyes - right * LayoutCenter,
                Quaternion.LookRotation(forward, Vector3.up));
        }
        public static OrynWorkspaceButton PointedButton(OrynWorkspaceButton[] buttons, Pose pointer, out Vector3 endpoint)
        {
            var ray = new Ray(pointer.position, pointer.rotation * Vector3.forward);
            endpoint = ray.GetPoint(RayLength);
            OrynWorkspaceButton nearest = null;
            float distance = RayLength;
            foreach (var button in buttons)
            {
                if (button == null || !button.gameObject.activeInHierarchy || button.Bounds == null || !button.Bounds.enabled) continue;
                if (Vector3.Dot(ray.origin - button.transform.position, button.transform.forward) >= 0) continue;
                if (button.Bounds.Raycast(ray, out RaycastHit hit, distance))
                { nearest = button; distance = hit.distance; endpoint = hit.point; }
            }
            return nearest;
        }
    }
}
