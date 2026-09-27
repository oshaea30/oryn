using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace Oryn.Preview
{
    // Desktop-only navigation. The preview scene is excluded from the Quest build.
    [RequireComponent(typeof(Camera))]
    public sealed class OrynDesktopCamera : MonoBehaviour
    {
        private Vector3 initialPosition;
        private Quaternion initialRotation;
        private float yaw;
        private float pitch;
        private GUIStyle titleStyle;
        private GUIStyle textStyle;

        private void Awake()
        {
            initialPosition = transform.position;
            initialRotation = transform.rotation;
            ResetView();
            Debug.Log("ORYN_DESKTOP_READY: synthetic room; no headset or passthrough camera required.");
        }

        private void Start()
        {
            // The sample enables this world-space console globally. Hide its UI only
            // for this desktop scene, without changing the Quest debugging settings.
            FindAnyObjectByType<Meta.XR.ImmersiveDebugger.UserInterface.DebugInterface>()?.Hide();
        }

        private void Update()
        {
            if (!Application.isFocused) return;
            Vector3 movement = Vector3.zero;
            Vector2 look = Vector2.zero;
            bool looking = false;
            bool fast = false;
#if ENABLE_INPUT_SYSTEM
            Keyboard keyboard = Keyboard.current;
            Mouse mouse = Mouse.current;
            if (keyboard != null)
            {
                movement.x = (keyboard.dKey.isPressed ? 1 : 0) - (keyboard.aKey.isPressed ? 1 : 0);
                movement.z = (keyboard.wKey.isPressed ? 1 : 0) - (keyboard.sKey.isPressed ? 1 : 0);
                movement.y = (keyboard.eKey.isPressed ? 1 : 0) - (keyboard.qKey.isPressed ? 1 : 0);
                fast = keyboard.leftShiftKey.isPressed || keyboard.rightShiftKey.isPressed;
                if (keyboard.rKey.wasPressedThisFrame) ResetView();
            }
            if (mouse != null)
            {
                looking = mouse.rightButton.isPressed;
                look = mouse.delta.ReadValue() * 0.12f;
            }
#elif ENABLE_LEGACY_INPUT_MANAGER
            movement = new Vector3(Input.GetAxisRaw("Horizontal"),
                (Input.GetKey(KeyCode.E) ? 1 : 0) - (Input.GetKey(KeyCode.Q) ? 1 : 0),
                Input.GetAxisRaw("Vertical"));
            looking = Input.GetMouseButton(1);
            look = new Vector2(Input.GetAxisRaw("Mouse X"), Input.GetAxisRaw("Mouse Y")) * 2f;
            fast = Input.GetKey(KeyCode.LeftShift);
            if (Input.GetKeyDown(KeyCode.R)) ResetView();
#endif
            Navigate(movement, looking ? look : Vector2.zero, fast, Time.unscaledDeltaTime);
        }

        public void Navigate(Vector3 movement, Vector2 lookDegrees, bool fast, float seconds)
        {
            yaw += lookDegrees.x;
            pitch = Mathf.Clamp(pitch - lookDegrees.y, -80f, 80f);
            transform.rotation = Quaternion.Euler(pitch, yaw, 0f);
            Vector3 forward = Quaternion.Euler(0f, yaw, 0f) * Vector3.forward;
            Vector3 right = Quaternion.Euler(0f, yaw, 0f) * Vector3.right;
            Vector3 direction = right * movement.x + Vector3.up * movement.y + forward * movement.z;
            transform.position += Vector3.ClampMagnitude(direction, 1f) * (fast ? 3f : 1.2f) * seconds;
            Vector3 position = transform.position;
            position.x = Mathf.Clamp(position.x, -2.7f, 2.7f);
            position.y = Mathf.Clamp(position.y, 0.3f, 2.7f);
            position.z = Mathf.Clamp(position.z, -1.7f, 4.7f);
            transform.position = position;
        }

        public void ResetView()
        {
            transform.SetPositionAndRotation(initialPosition, initialRotation);
            yaw = initialRotation.eulerAngles.y;
            pitch = Mathf.DeltaAngle(0f, initialRotation.eulerAngles.x);
        }

        private void OnGUI()
        {
            if (titleStyle == null)
            {
                titleStyle = new GUIStyle(GUI.skin.label) { fontSize = 23, fontStyle = FontStyle.Bold };
                textStyle = new GUIStyle(GUI.skin.label) { fontSize = 13, wordWrap = true };
                titleStyle.normal.textColor = Color.white;
                textStyle.normal.textColor = new Color(0.82f, 0.87f, 0.91f);
            }
            GUILayout.BeginArea(new Rect(20, 20, Mathf.Min(390, Screen.width - 40), 205), GUI.skin.box);
            GUILayout.Label("ORYN / LOCAL PREVIEW", titleStyle);
            GUILayout.Label("One virtual object. A room to explore.", textStyle);
            GUILayout.Space(10);
            GUILayout.Label("WASD  Move     Q / E  Down / Up\nHold right mouse  Look     Shift  Faster\nR  Reset view", textStyle);
            GUILayout.Space(8);
            if (GUILayout.Button("Reset view", GUILayout.Height(28))) ResetView();
            GUILayout.Label("Synthetic room — headset validation pending", textStyle);
            GUILayout.EndArea();
        }
    }
}
