using UnityEngine;

namespace Oryn.Interaction
{
    public sealed class OrynWorkspaceButton : MonoBehaviour
    {
        public enum Command { Cube, Sphere, Delete, Reset, LoadModel, Parts, Explode, Isolate, Reassemble, PreviousLabel, NextLabel, SaveLabel,
            DroneDemo, V8Demo, MotionPlay, MotionPause, MotionStop, MotionSlow, MotionNormal, MotionIsolate }
        public Command Action;
        public Collider Bounds;
        private Renderer surface;
        private MaterialPropertyBlock colors;
        public void ShowState(bool enabled, bool hovered)
        {
            if (surface == null) { surface = GetComponent<Renderer>(); colors = new MaterialPropertyBlock(); }
            colors.SetColor("_Color", !enabled ? new Color(0.13f, 0.16f, 0.19f) :
                hovered ? new Color(0.12f, 0.65f, 0.48f) : new Color(0.10f, 0.30f, 0.40f));
            surface.SetPropertyBlock(colors);
        }
    }
}
