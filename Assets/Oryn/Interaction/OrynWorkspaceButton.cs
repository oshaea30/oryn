using UnityEngine;

namespace Oryn.Interaction
{
    public sealed class OrynWorkspaceButton : MonoBehaviour
    {
        public enum Command { Cube, Sphere, Delete, Reset, LoadModel, Parts, Explode, Isolate, Reassemble, PreviousLabel, NextLabel, SaveLabel,
            DroneDemo, V8Demo, MotionPlay, MotionPause, MotionStop, MotionSlow, MotionNormal, MotionIsolate, MenuPrevious, MenuNext, MenuHome, MenuObject, MenuMotion, MenuLibrary, MenuDetails }
        public Command Action;
        public Collider Bounds;
        public bool WristStyle;
        private Renderer surface;
        private MaterialPropertyBlock colors;
        public void ShowState(bool enabled, bool hovered)
        {
            if (surface == null) { surface = GetComponent<Renderer>(); colors = new MaterialPropertyBlock(); }
            colors.SetColor("_Color", WristStyle ? (!enabled ? new Color(0.055f,0.075f,0.09f) : hovered ? new Color(0.09f,0.47f,0.43f) : new Color(0.065f,0.13f,0.16f)) : !enabled ? new Color(0.13f, 0.16f, 0.19f) :
                hovered ? new Color(0.12f, 0.65f, 0.48f) : new Color(0.10f, 0.30f, 0.40f));
            surface.SetPropertyBlock(colors);
        }
    }
}
