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
        private static void Check(bool value,string message)
        { if(!value)throw new InvalidOperationException("Wrist menu: "+message);checks++; }
        public static void Run()
        {
            checks=0;
            var eye=new Pose(new Vector3(0,1.6f,0),Quaternion.identity);
            var wrist=new Vector3(-0.1f,1.3f,0.4f);
            var palm=new OrynPalmSample{Valid=true,Open=true,Normal=(eye.position-wrist).normalized,Fingers=Vector3.forward};
            var reveal=new OrynWristReveal();
            Check(!reveal.Sample(palm,wrist,eye,true,0.05f),"passing wrist through view does not instantly reveal launcher");
            for(int i=0;i<240;i++)reveal.Sample(palm,wrist,eye,true,0.05f);
            Check(reveal.Visible && !reveal.Expanded,"even prolonged palm facing cannot open the menu");
            reveal.Toggle();Check(reveal.Expanded,"explicit launcher action opens");
            reveal.Sample(palm,wrist,eye,false,0.02f);
            Check(!reveal.Visible && !reveal.Expanded,"either-hand manipulation suppresses and closes controls");
            for(int i=0;i<10;i++)reveal.Sample(palm,wrist,eye,true,0.05f);
            Check(reveal.Visible && !reveal.Expanded,"releasing a figure never reopens the menu");
            reveal.Toggle();palm.Valid=false;reveal.Sample(palm,wrist,eye,true,0.02f);
            Check(!reveal.Visible && !reveal.Expanded,"tracking loss closes and disarms");
            reveal.Toggle();Check(!reveal.Expanded,"hidden launcher cannot open");
            palm.Valid=true;palm.Open=false;
            for(int i=0;i<20;i++)reveal.Sample(palm,wrist,eye,true,0.05f);
            Check(!reveal.Visible,"closed hand cannot reveal launcher");
            palm.Open=true;palm.Normal=-palm.Normal;
            for(int i=0;i<20;i++)reveal.Sample(palm,wrist,eye,true,0.05f);
            Check(!reveal.Visible,"turned palm hides launcher");palm.Normal=-palm.Normal;
            Check(!reveal.Sample(palm,wrist,eye,true,float.NaN),"invalid timestep cannot reveal");
            reveal.Controller(true,false);Check(reveal.Visible && !reveal.Expanded,"controller tracking does not open menu");
            reveal.Controller(true,true);Check(reveal.Expanded,"controller Y explicitly opens");
            reveal.Controller(false,false);reveal.Controller(true,false);
            Check(!reveal.Expanded,"focus/tracking recovery requires a new toggle");
            var pose=OrynWristReveal.Placement(wrist,palm.Fingers,palm.Normal,eye);
            Check(Vector3.Distance(pose.position,wrist)<0.08f,"launcher stays within 8cm of wrist");
            Check(Vector3.Dot(pose.rotation*Vector3.forward,(pose.position-eye.position).normalized)>0.999f,"fan faces user");
            Vector3 delta=new Vector3(2,1,-3);
            var shifted=OrynWristReveal.Placement(wrist+delta,palm.Fingers,palm.Normal,new Pose(eye.position+delta,eye.rotation));
            Check(Vector3.Distance(shifted.position,pose.position+delta)<0.0001f,"recenter keeps wrist attachment");
            var obj=GameObject.CreatePrimitive(PrimitiveType.Cube);
            try
            {
                obj.transform.localScale=Vector3.one*0.2f;Physics.SyncTransforms();var collider=obj.GetComponent<Collider>();
                Check(OrynWristReveal.NearObject(collider,new Vector3(0.18f,0,0)),"near-surface reach suppresses before touching");
                Check(OrynWristReveal.NearObject(collider,Vector3.zero),"inside geometry also suppresses");
                Check(!OrynWristReveal.NearObject(collider,new Vector3(0.3f,0,0)),"distant objects do not suppress");
                obj.SetActive(false);Check(!OrynWristReveal.NearObject(collider,Vector3.zero),"inactive objects do not suppress");
            }
            finally { UnityEngine.Object.DestroyImmediate(obj); }
            var press=new OrynPressLatch();
            Check(!press.Sample(true,1),"held pinch cannot open launcher");press.Sample(true,0);
            Check(press.Sample(true,1),"fresh pinch opens launcher");press.Clear();
            Check(!press.Sample(true,1),"opening cannot also select a newly exposed tool");
            Debug.Log("ORYN_WRIST_MENU_TESTS_OK checks="+checks);
        }
        public static void RunAndPreview()
        {
            Run();EditorSceneManager.OpenScene(OrynWorkspaceSetup.ScenePath);
            var workspace=UnityEngine.Object.FindAnyObjectByType<OrynWorkspace>();var menu=new OrynWristMenu(workspace);
            var input=new OrynTrackedInput();input.Valid[0]=true;input.Poses[0]=new Pose(new Vector3(-0.1f,1.3f,0.4f),Quaternion.identity);
            var eye=new Pose(new Vector3(0,1.6f,0),Quaternion.identity);
            menu.Update(input,eye,true,false);workspace.Panel.SetPositionAndRotation(Vector3.zero,Quaternion.identity);
            foreach(Transform child in workspace.Panel.GetComponentsInChildren<Transform>(true))child.gameObject.layer=30;
            var go=new GameObject("Radial preview camera");var camera=go.AddComponent<Camera>();
            camera.transform.position=new Vector3(0.055f,0,-0.55f);camera.orthographic=true;camera.orthographicSize=0.205f;
            camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(0.045f,0.063f,0.078f);camera.cullingMask=1<<30;
            var rt=new RenderTexture(1024,1024,24);camera.targetTexture=rt;Directory.CreateDirectory("Builds/WristMenuRadial");
            try
            {
                Check(!menu.Expanded && !workspace.Buttons[0].gameObject.activeInHierarchy,"only launcher is interactive when closed");
                Capture(camera,rt,workspace,"launcher");menu.Navigate(OrynWorkspaceButton.Command.MenuHome);menu.Refresh();Physics.SyncTransforms();
                Check(menu.Expanded,"launcher explicitly opens category fan");
                Capture(camera,rt,workspace,"home");
                for(int page=0;page<OrynWristMenu.PageCount;page++)
                {
                    menu.Navigate((OrynWorkspaceButton.Command)((int)OrynWorkspaceButton.Command.MenuObject+page));menu.Refresh();Physics.SyncTransforms();
                    for(int i=0;i<6;i++)
                    {
                        if(!workspace.Buttons[i].gameObject.activeInHierarchy)continue;
                        Vector3 center=OrynWristMenu.SlotCenter(i,false);
                        Check(OrynMenuPlacement.PointedButton(workspace.Buttons,new Pose(new Vector3(center.x,center.y,-0.4f),Quaternion.identity),out _)==workspace.Buttons[i],"radial slice ray selects correct action");
                        Check(OrynMenuPlacement.NearButton(workspace.Buttons,center)==workspace.Buttons[i],"near pinch selects correct curved slice");
                        Check(OrynMenuPlacement.NearButton(workspace.Buttons,new Vector3(center.x,center.y,0.02f))==null,"rear touch cannot select");
                    }
                    Check(OrynMenuPlacement.PointedButton(workspace.Buttons,new Pose(new Vector3(0.143f,0,-0.4f),Quaternion.identity),out _)==null,"visible angular gaps are not hit targets");
                    Capture(camera,rt,workspace,"page-"+page);menu.Navigate(OrynWorkspaceButton.Command.MenuHome);
                }
                menu.Navigate(OrynWorkspaceButton.Command.MenuHome);
                Check(!menu.Expanded,"home center closes menu");
                menu.Update(input,eye,true,true);Check(menu.Expanded,"controller opens fan");
                menu.Update(input,eye,false,false);Check(!menu.Expanded && !workspace.Panel.gameObject.activeSelf,"manipulation hides entire menu including launcher");
                menu.Update(input,eye,true,false);Check(!menu.Expanded,"post-grab recovery stays closed");
                Debug.Log("ORYN_WRIST_PREVIEW_OK checks="+checks);
            }
            finally { RenderTexture.active=null;camera.targetTexture=null;rt.Release();UnityEngine.Object.DestroyImmediate(rt);UnityEngine.Object.DestroyImmediate(go); }
        }
        private static void Capture(Camera camera,RenderTexture rt,OrynWorkspace workspace,string name)
        {
            foreach(var button in workspace.Buttons)button.ShowState(true,false);
            camera.Render();RenderTexture.active=rt;var texture=new Texture2D(1024,1024,TextureFormat.RGB24,false);
            texture.ReadPixels(new Rect(0,0,1024,1024),0,0);texture.Apply();File.WriteAllBytes("Builds/WristMenuRadial/"+name+".png",texture.EncodeToPNG());UnityEngine.Object.DestroyImmediate(texture);
        }
    }
}
