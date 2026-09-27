using UnityEngine;

namespace Oryn.Interaction
{
    // Analytic surface queries, including INSIDE points (Collider.ClosestPoint does
    // not return a surface for those). Distances and padding are in world metres.
    public static class OrynSurfaceContact
    {
        public const float TouchDistance = 0.025f;
        public const float ContactMemory = 0.3f;
        public static bool ResizeTarget(Collider collider, Vector3 pinch, out Vector3 surface)
        {
            // Resize is a near-object tool, not a physical grasp. Keep it bounded
            // to the surface but do not require fingers to penetrate/touch it.
            return Query(collider, pinch, out surface, out _, out float distance) && distance >= -0.04f && distance <= 0.15f;
        }
        public static bool Query(Collider collider, Vector3 point, out Vector3 surface, out Vector3 normal, out float distance)
        {
            surface = point; normal = Vector3.up; distance = float.PositiveInfinity;
            if (collider == null || !collider.enabled || !collider.gameObject.activeInHierarchy) return false;
            Transform t = collider.transform;
            Vector3 scale = t.lossyScale;
            scale = new Vector3(Mathf.Abs(scale.x), Mathf.Abs(scale.y), Mathf.Abs(scale.z));
            if (collider is SphereCollider sphere)
            {
                Vector3 delta = point - t.TransformPoint(sphere.center);
                float radius = sphere.radius * Mathf.Max(scale.x, Mathf.Max(scale.y, scale.z));
                normal = delta.sqrMagnitude > 0.0000001f ? delta.normalized : t.up;
                distance = delta.magnitude - radius;
                surface = point - normal * distance;
                return true;
            }
            if (!(collider is BoxCollider box)) return false;
            Vector3 center = t.TransformPoint(box.center);
            Vector3 local = Quaternion.Inverse(t.rotation) * (point - center);
            Vector3 extent = Vector3.Scale(box.size * 0.5f, scale);
            Vector3 closest = new Vector3(Mathf.Clamp(local.x, -extent.x, extent.x), Mathf.Clamp(local.y, -extent.y, extent.y), Mathf.Clamp(local.z, -extent.z, extent.z));
            Vector3 outward = local - closest;
            if (outward.sqrMagnitude > 0.00000001f)
            {
                distance = outward.magnitude;
                normal = t.rotation * outward.normalized;
            }
            else
            {
                Vector3 depth = extent - new Vector3(Mathf.Abs(local.x), Mathf.Abs(local.y), Mathf.Abs(local.z));
                int axis = depth.x <= depth.y && depth.x <= depth.z ? 0 : depth.y <= depth.z ? 1 : 2;
                Vector3 direction = Vector3.zero; direction[axis] = local[axis] < 0 ? -1 : 1;
                closest[axis] = direction[axis] * extent[axis];
                distance = -depth[axis]; normal = t.rotation * direction;
            }
            surface = center + t.rotation * closest;
            return true;
        }

        public static bool Touch(Collider collider, Vector3 point, Vector3 previous, bool hasPrevious, out Vector3 surface)
        {
            if (!Query(collider, point, out surface, out _, out float distance)) return false;
            if (distance >= -0.015f && distance <= TouchDistance) return true;
            // Catch a fast fingertip crossing the surface between frames. Never
            // infer contact from a hand first detected deep inside the object.
            Vector3 travel = point - previous;
            if (!hasPrevious || travel.magnitude > 0.15f || travel.sqrMagnitude < 0.000001f) return false;
            if (!Query(collider, previous, out _, out _, out float before) || before < 0) return false;
            if (!collider.Raycast(new Ray(previous, travel.normalized), out RaycastHit hit, travel.magnitude)) return false;
            surface = hit.point;
            return true;
        }
    }

    // An open-then-pinch can finish just before contact. This grace period applies
    // only to object grabs, never to panel commands or tracking recovery.
    public sealed class OrynContactLatch
    {
        private readonly OrynPressLatch press = new OrynPressLatch();
        private float pendingUntil = -1;
        public void Clear() { press.Clear(); pendingUntil = -1; }
        public bool Sample(bool valid, float strength, bool touching, float now)
        {
            if (!valid || strength <= OrynGrabState.EndThreshold) pendingUntil = -1;
            if (press.Sample(valid, strength)) pendingUntil = now + OrynSurfaceContact.ContactMemory;
            if (!valid || !touching || now > pendingUntil) return false;
            pendingUntil = -1;
            return true;
        }
    }
}
