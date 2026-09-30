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
            // Both hands, several hand sizes, all fingers curled with a lateral straight thumb.
            foreach(float side in new[]{-1f,1f})foreach(float scale in new[]{0.65f,1f,1.35f})
            {
                var bases=new[]{new Vector3(.035f*side,0,.075f),new Vector3(0,0,.08f),new Vector3(-.015f*side,0,.075f),new Vector3(-.035f*side,0,.065f)};
                var joints=new Vector3[4];var tips=new Vector3[4];var confidence=new[]{true,true,true,true};
                for(int i=0;i<4;i++) { bases[i]*=scale;joints[i]=bases[i]+new Vector3(0,-.025f,.015f)*scale;tips[i]=bases[i]+new Vector3(0,-.025f,-.01f)*scale; }
                Vector3 thumbBase=new Vector3(.045f*side,0,.035f)*scale,thumbJoint=new Vector3(.065f*side,0,.045f)*scale,thumbTip=new Vector3(.095f*side,0,.055f)*scale;
                Check(OrynWristPose.Matches(true,Vector3.zero,thumbBase,thumbJoint,thumbTip,bases,joints,tips,confidence),"thumb-out fist recognized on either hand and at different sizes");
                Check(!OrynWristPose.Matches(false,Vector3.zero,thumbBase,thumbJoint,thumbTip,bases,joints,tips,confidence),"untracked pose rejected");
                Check(!OrynWristPose.Matches(true,Vector3.zero,thumbBase,thumbJoint,thumbBase,bases,joints,tips,confidence),"tucked thumb rejected");
                for(int i=0;i<4;i++)
                {
                    Vector3 save=tips[i];tips[i]=joints[i]+(joints[i]-bases[i]);
                    Check(!OrynWristPose.Matches(true,Vector3.zero,thumbBase,thumbJoint,thumbTip,bases,joints,tips,confidence),"each of four fingers must curl");tips[i]=save;
                    confidence[i]=false;Check(!OrynWristPose.Matches(true,Vector3.zero,thumbBase,thumbJoint,thumbTip,bases,joints,tips,confidence),"low confidence rejected");confidence[i]=true;
                }
            }
            var eye=new Pose(new Vector3(0,1.6f,0),Quaternion.identity);var wrist=new Vector3(-.1f,1.3f,.4f);
            var palm=new OrynPalmSample{Valid=true,Open=false,Normal=Vector3.up,Fingers=Vector3.forward};
            var reveal=new OrynWristReveal();
            Check(!reveal.Sample(palm,wrist,eye,true,true,.04f),"single noisy pose frame does not open");
            Check(reveal.Sample(palm,wrist,eye,true,true,.04f),"80ms pose opens directly");
            Check(reveal.Sample(palm,wrist,eye,false,true,.016f),"relaxing fingers preserves menu");
            reveal.Toggle();for(int i=0;i<30;i++)reveal.Sample(palm,wrist,eye,true,true,.02f);
            Check(!reveal.Expanded,"close cannot reopen from a held pose");
            reveal.Sample(palm,wrist,eye,false,true,.02f);for(int i=0;i<5;i++)reveal.Sample(palm,wrist,eye,true,true,.02f);
            Check(reveal.Expanded,"fresh pose opens again");
            reveal.Sample(palm,wrist,eye,true,false,.02f);Check(!reveal.Expanded,"manipulation closes immediately");
            for(int i=0;i<10;i++)reveal.Sample(palm,wrist,eye,true,true,.02f);
            Check(!reveal.Expanded,"post-grab held pose cannot reopen automatically");
            palm.Normal=Vector3.down;reveal.Sample(palm,wrist,eye,false,true,.02f);
            Check(!reveal.Sample(palm,wrist,eye,true,true,.05f),"palm down cannot open");
            palm.Normal=Vector3.up;reveal.Sample(palm,wrist,eye,false,true,.02f);
            for(int i=0;i<20;i++)reveal.Sample(palm,wrist,eye,false,true,.05f);
            Check(!reveal.Expanded,"open palm alone does not reveal a menu or launcher");
            reveal.Controller(true,true);Check(reveal.Expanded,"controller toggle still opens");reveal.Controller(false,false);
            Check(!reveal.Expanded,"controller tracking loss closes");
            var obj=GameObject.CreatePrimitive(PrimitiveType.Cube);
            try
            {
                obj.transform.localScale=Vector3.one*.2f;Physics.SyncTransforms();var bounds=obj.GetComponent<Collider>();
                Check(OrynWristReveal.NearObject(bounds,new Vector3(.18f,0,0)),"reach suppression retained");
                Check(!OrynWristReveal.NearObject(bounds,new Vector3(.3f,0,0)),"distant object does not suppress");
            }
            finally { UnityEngine.Object.DestroyImmediate(obj); }
            Debug.Log("ORYN_WRIST_MENU_TESTS_OK checks="+checks);
        }
        public static void BuildAndPreview() { RunAndPreview(); OrynWorkspaceSetup.BuildAndroid(); }
        public static void RunAndPreview()
        {
            Run();EditorSceneManager.OpenScene(OrynWorkspaceSetup.ScenePath);
            var workspace=UnityEngine.Object.FindAnyObjectByType<OrynWorkspace>();var menu=new OrynWristMenu(workspace);
            var input=new OrynTrackedInput();input.Valid[0]=input.Valid[1]=true;
            input.Poses[0]=new Pose(new Vector3(-.2f,1.3f,.4f),Quaternion.identity);input.Poses[1]=new Pose(new Vector3(.2f,1.3f,.4f),Quaternion.identity);
            var eye=new Pose(new Vector3(0,1.6f,0),Quaternion.identity);
            var go=new GameObject("Two-wrist preview camera");var camera=go.AddComponent<Camera>();
            camera.orthographic=true;camera.orthographicSize=.205f;camera.clearFlags=CameraClearFlags.SolidColor;
            camera.backgroundColor=new Color(.045f,.063f,.078f);camera.cullingMask=1<<30;
            var rt=new RenderTexture(1024,1024,24);camera.targetTexture=rt;Directory.CreateDirectory("Builds/TwoWristMenu");
            try
            {
                menu.Update(input,eye,true,false,false);Check(!menu.Expanded,"no automatic panel on tracking acquisition");
                for(int hand=0;hand<2;hand++)
                {
                    menu.Hide();menu.Update(input,eye,true,hand==0,hand==1);
                    Check(menu.HostHand==hand && menu.Expanded,"correct wrist owns its menu");
                    Check(workspace.Buttons[0].Action==(hand==0 ? OrynWorkspaceButton.Command.LoadModel : OrynWorkspaceButton.Command.MotionPlay),"left opens object controls; right opens motion directly");
                    Check(menu.AllowsSource(1-hand) && menu.AllowsSource(3-hand),"opposite hand/controller can select");
                    Check(!menu.AllowsSource(hand) && !menu.AllowsSource(hand+2),"host hand cannot select itself");
                    workspace.Panel.SetPositionAndRotation(Vector3.zero,Quaternion.identity);menu.Refresh();Physics.SyncTransforms();
                    foreach(Transform child in workspace.Panel.GetComponentsInChildren<Transform>(true))child.gameObject.layer=30;
                    for(int i=0;i<6;i++)
                    {
                        Vector3 center=OrynWristMenu.SlotCenter(i,false,hand);
                        Check(OrynMenuPlacement.PointedButton(workspace.Buttons,new Pose(new Vector3(center.x,center.y,-.4f),Quaternion.identity),out _)==workspace.Buttons[i],"mirrored slice ray selects correct action");
                        Check(OrynMenuPlacement.NearButton(workspace.Buttons,center)==workspace.Buttons[i],"mirrored near pinch selects correct action");
                        Check(OrynMenuPlacement.NearButton(workspace.Buttons,new Vector3(center.x,center.y,.02f))==null,"rear touch rejected");
                    }
                    camera.transform.position=new Vector3(hand==0 ? .055f : -.055f,0,-.55f);
                    foreach(var button in workspace.Buttons)button.ShowState(true,false);
                    camera.Render();RenderTexture.active=rt;var texture=new Texture2D(1024,1024,TextureFormat.RGB24,false);
                    texture.ReadPixels(new Rect(0,0,1024,1024),0,0);texture.Apply();File.WriteAllBytes("Builds/TwoWristMenu/"+(hand==0 ? "left" : "right")+".png",texture.EncodeToPNG());UnityEngine.Object.DestroyImmediate(texture);
                }
                menu.Update(input,eye,true,true,false);Check(menu.HostHand==0 && menu.Expanded,"fresh left toggle takes over an open right menu");
                menu.Update(input,eye,true,false,true);Check(menu.HostHand==1 && menu.Expanded,"fresh right toggle takes over an open left menu");
                menu.Update(input,eye,false,false,false);Check(!menu.Expanded && !workspace.Panel.gameObject.activeSelf,"busy hides either menu");
                menu.Update(input,eye,true,false,false);Check(!menu.Expanded,"release stays closed");
                Debug.Log("ORYN_WRIST_PREVIEW_OK checks="+checks);
            }
            finally { RenderTexture.active=null;camera.targetTexture=null;rt.Release();UnityEngine.Object.DestroyImmediate(rt);UnityEngine.Object.DestroyImmediate(go); }
        }
    }
}
