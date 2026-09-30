using System;
using System.IO;
using Oryn.Interaction;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Oryn.Editor
{
    public static class OrynWristMenuTests
    {
        private static int checks;
        private static void Check(bool value, string message)
        { if (!value) throw new InvalidOperationException("Wrist menu: " + message); checks++; }
        public static void Run()
        {
            checks = 0;
            var eye = new Pose(new Vector3(0,1.6f,0), Quaternion.identity);
            var wrist = new Vector3(-0.1f,1.3f,0.4f);
            var palm = new OrynPalmSample { Valid=true, Open=true, Normal=(eye.position-wrist).normalized, Fingers=Vector3.forward };
            var reveal = new OrynWristReveal();
            Check(!reveal.Sample(palm,wrist,eye,true,0.05f), "passing wrist through view cannot open immediately");
            for (int i=0;i<4;i++) reveal.Sample(palm,wrist,eye,true,0.05f);
            Check(reveal.Visible, "deliberate palm reveal opens");
            Check(!reveal.Sample(palm,wrist,eye,false,0.02f), "holding object or focus loss hides immediately");
            for (int i=0;i<5;i++) reveal.Sample(palm,wrist,eye,true,0.05f);
            palm.Valid=false;
            Check(!reveal.Sample(palm,wrist,eye,true,0.02f), "tracking loss hides immediately");
            palm.Valid=true;palm.Open=false;
            for (int i=0;i<20;i++) reveal.Sample(palm,wrist,eye,true,0.05f);
            Check(!reveal.Visible, "closed hand cannot reveal");
            palm.Open=true;palm.Normal=-palm.Normal;
            for (int i=0;i<20;i++) reveal.Sample(palm,wrist,eye,true,0.05f);
            Check(!reveal.Visible, "palm turned away cannot reveal");
            palm.Normal=-palm.Normal;
            for (int i=0;i<20;i++) reveal.Sample(palm,wrist,new Pose(eye.position,Quaternion.Euler(0,180,0)),true,0.05f);
            Check(!reveal.Visible, "wrist outside forward view cannot reveal");
            Check(!reveal.Sample(palm,wrist,eye,true,float.NaN), "invalid timestep cannot reveal");
            var pose=OrynWristReveal.Placement(wrist,palm.Fingers,palm.Normal,eye);
            Check(Vector3.Distance(pose.position,wrist)<0.18f, "panel is anchored near wrist");
            Check(Vector3.Dot(pose.rotation*Vector3.forward,(pose.position-eye.position).normalized)>0.999f, "front faces user");
            Vector3 delta = new Vector3(2,1,-3);
            var shifted=OrynWristReveal.Placement(wrist+delta,palm.Fingers,palm.Normal,new Pose(eye.position+delta,eye.rotation));
            Check(Vector3.Distance(shifted.position,pose.position+delta)<0.0001f, "recenter preserves wrist-relative placement");
            var obj=GameObject.CreatePrimitive(PrimitiveType.Cube);
            try
            {
                obj.transform.localScale=new Vector3(0.13f,0.045f,0.012f);
                var button=obj.AddComponent<OrynWorkspaceButton>();button.Bounds=obj.GetComponent<Collider>();
                var buttons=new[]{button};Physics.SyncTransforms();
                Check(OrynMenuPlacement.NearButton(buttons,new Vector3(0,0,-0.01f))==button,"front proximity selects");
                Check(OrynMenuPlacement.NearButton(buttons,new Vector3(0,0,0.01f))==null,"back proximity cannot select");
                Check(OrynMenuPlacement.NearButton(buttons,new Vector3(0,0,-0.04f))==null,"proximity limited to 18mm");
                button.Bounds.enabled=false;
                Check(OrynMenuPlacement.NearButton(buttons,new Vector3(0,0,-0.01f))==null,"disabled hit target excluded");
                button.Bounds.enabled=true;obj.SetActive(false);
                Check(OrynMenuPlacement.NearButton(buttons,new Vector3(0,0,-0.01f))==null,"hidden page cannot be selected");
            }
            finally { UnityEngine.Object.DestroyImmediate(obj); }
            Debug.Log("ORYN_WRIST_MENU_TESTS_OK checks="+checks);
        }
        public static void RunAndPreview()
        {
            Run();
            EditorSceneManager.OpenScene(OrynWorkspaceSetup.ScenePath);
            var workspace=UnityEngine.Object.FindAnyObjectByType<OrynWorkspace>();
            var menu=new OrynWristMenu(workspace);
            workspace.Panel.SetPositionAndRotation(Vector3.zero,Quaternion.identity);
            workspace.Panel.gameObject.SetActive(true);
            foreach (Transform child in workspace.Panel.GetComponentsInChildren<Transform>(true)) child.gameObject.layer=30;
            var go=new GameObject("Wrist preview camera");var camera=go.AddComponent<Camera>();
            camera.transform.position=new Vector3(0,0,-0.55f);camera.orthographic=true;camera.orthographicSize=0.20f;
            camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(0.06f,0.09f,0.12f);camera.cullingMask=1<<30;
            var rt=new RenderTexture(1024,1024,24);camera.targetTexture=rt;
            Directory.CreateDirectory("Builds/WristMenu");
            try
            {
                for(int page=0;page<OrynWristMenu.PageCount;page++)
                {
                    menu.Refresh();Physics.SyncTransforms();
                    foreach(var button in workspace.Buttons) button.ShowState(true,false);
                    Check(workspace.Buttons[6].Action==OrynWorkspaceButton.Command.MenuPrevious,"previous navigation stable");
                    Check(workspace.Buttons[7].Action==OrynWorkspaceButton.Command.MenuNext,"next navigation stable");
                    camera.Render();RenderTexture.active=rt;
                    var texture=new Texture2D(1024,1024,TextureFormat.RGB24,false);
                    texture.ReadPixels(new Rect(0,0,1024,1024),0,0);texture.Apply();
                    File.WriteAllBytes("Builds/WristMenu/page-"+page+".png",texture.EncodeToPNG());
                    UnityEngine.Object.DestroyImmediate(texture);menu.ChangePage(1);
                }
                Check(workspace.Buttons[0].Action==OrynWorkspaceButton.Command.LoadModel,"page cycle returns to object controls");
                Debug.Log("ORYN_WRIST_PREVIEW_OK checks="+checks);
            }
            finally
            {
                RenderTexture.active=null;camera.targetTexture=null;rt.Release();
                UnityEngine.Object.DestroyImmediate(rt);UnityEngine.Object.DestroyImmediate(go);
            }
        }
    }
}
