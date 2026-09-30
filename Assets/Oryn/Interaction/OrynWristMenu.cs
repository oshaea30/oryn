using System;
using System.Collections.Generic;
using UnityEngine;

namespace Oryn.Interaction
{
    // Palm orientation reveals only the launcher. Opening always needs a separate action.
    public sealed class OrynWristReveal
    {
        public bool Visible { get; private set; }
        public bool Expanded { get; private set; }
        private float dwell;
        public void Reset() { Visible = Expanded = false; dwell = 0; }
        public void Toggle() { if (Visible) Expanded = !Expanded; }
        public bool Sample(OrynPalmSample palm, Vector3 wrist, Pose eye, bool eligible, float seconds)
        {
            Vector3 toEye = eye.position - wrist;
            bool facing = eligible && palm.Valid && palm.Open && toEye.magnitude >= 0.20f && toEye.magnitude <= 0.85f &&
                Vector3.Dot(palm.Normal, toEye.normalized) > (Visible ? 0.25f : 0.60f) &&
                Vector3.Dot(eye.rotation * Vector3.forward, -toEye.normalized) > 0.50f;
            if (!facing || !float.IsFinite(seconds)) { Reset(); return false; }
            dwell += Mathf.Clamp(seconds, 0, 0.05f);
            Visible = dwell >= 0.30f;
            return Visible;
        }
        public void Controller(bool available, bool toggle)
        {
            if (!available) { Reset(); return; }
            Visible = true;
            if (toggle) Toggle();
        }
        public static bool NearObject(Collider bounds, Vector3 point)
        {
            return bounds != null && bounds.enabled && bounds.gameObject.activeInHierarchy &&
                bounds.bounds.SqrDistance(point) <= 0.01f &&
                OrynSurfaceContact.Query(bounds, point, out _, out _, out float distance) && distance <= 0.10f;
        }
        public static Pose Placement(Vector3 wrist, Vector3 fingers, Vector3 normal, Pose eye)
        {
            // Launcher sits just off the wrist; the fan extends 9–19cm toward the other hand.
            Vector3 center = wrist - fingers.normalized * 0.025f + normal.normalized * 0.045f;
            Vector3 forward = (center - eye.position).normalized;
            if (forward.sqrMagnitude < 0.01f) forward = eye.rotation * Vector3.forward;
            Vector3 up = Vector3.ProjectOnPlane(eye.rotation * Vector3.up, forward).normalized;
            if (up.sqrMagnitude < 0.01f) up = Vector3.ProjectOnPlane(eye.rotation * Vector3.right, forward).normalized;
            return new Pose(center, Quaternion.LookRotation(forward, up));
        }
    }

    // Own the small runtime-generated meshes with the scene, including repeated app sessions.
    public sealed class OrynWristVisualResources : MonoBehaviour
    {
        public readonly List<Mesh> Meshes = new List<Mesh>();
        public Material Accent;
        private void OnDestroy()
        {
            foreach (var mesh in Meshes) if (mesh != null) { if (Application.isPlaying) Destroy(mesh); else DestroyImmediate(mesh); }
            if (Accent != null) { if (Application.isPlaying) Destroy(Accent); else DestroyImmediate(Accent); }
        }
    }

    public sealed class OrynWristMenu
    {
        public const int PageCount = 4;
        private readonly OrynWorkspace workspace;
        private readonly OrynWristReveal reveal = new OrynWristReveal();
        private readonly OrynWristVisualResources resources;
        private readonly Transform fan, hubRing;
        private readonly LineRenderer tether;
        private readonly OrynWorkspaceButton hub;
        private readonly TextMesh hubText, title, status, details;
        private readonly TextMesh[] captions = new TextMesh[6];
        private readonly OrynWorkspaceButton[] slots = new OrynWorkspaceButton[6];
        private readonly Mesh[] homeMeshes = new Mesh[4], actionMeshes = new Mesh[6];
        private int page = -1, inputMode = -1;
        private string previousStatus, previousDetails;
        public bool Expanded => reveal.Expanded;
        private static readonly string[] Titles = { "INSPECT", "MOTION", "OBJECTS", "DETAILS" };
        private static readonly string[][] Labels = {
            new[] { "Bring\nmodel", "Parts /\nwhole", "Take\napart", "Assemble", "Isolate /\nall", "Reset" },
            new[] { "Play", "Pause", "Stop /\nhome", "Slow", "Normal", "System /\nall" },
            new[] { "Drone\ndemo", "V8\ndemo", "Cube", "Sphere", "Delete", "" },
            new[] { "Previous\nlabel", "Next\nlabel", "Save\nlabel", "", "", "" }
        };
        private static readonly OrynWorkspaceButton.Command[][] Actions = {
            new[] { OrynWorkspaceButton.Command.LoadModel, OrynWorkspaceButton.Command.Parts, OrynWorkspaceButton.Command.Explode,
                OrynWorkspaceButton.Command.Reassemble, OrynWorkspaceButton.Command.Isolate, OrynWorkspaceButton.Command.Reset },
            new[] { OrynWorkspaceButton.Command.MotionPlay, OrynWorkspaceButton.Command.MotionPause, OrynWorkspaceButton.Command.MotionStop,
                OrynWorkspaceButton.Command.MotionSlow, OrynWorkspaceButton.Command.MotionNormal, OrynWorkspaceButton.Command.MotionIsolate },
            new[] { OrynWorkspaceButton.Command.DroneDemo, OrynWorkspaceButton.Command.V8Demo, OrynWorkspaceButton.Command.Cube,
                OrynWorkspaceButton.Command.Sphere, OrynWorkspaceButton.Command.Delete, OrynWorkspaceButton.Command.Delete },
            new[] { OrynWorkspaceButton.Command.PreviousLabel, OrynWorkspaceButton.Command.NextLabel, OrynWorkspaceButton.Command.SaveLabel,
                OrynWorkspaceButton.Command.SaveLabel, OrynWorkspaceButton.Command.SaveLabel, OrynWorkspaceButton.Command.SaveLabel }
        };
        public OrynWristMenu(OrynWorkspace owner)
        {
            workspace = owner;
            Material material = owner.Buttons[0].GetComponent<Renderer>().sharedMaterial;
            foreach (Transform child in owner.Panel) child.gameObject.SetActive(false);
            owner.Panel.name = "ORYN wrist launcher and radial menu"; owner.Panel.localScale = Vector3.one;
            resources = owner.Panel.gameObject.AddComponent<OrynWristVisualResources>();
            resources.Accent = new Material(material); resources.Accent.color = new Color(0.18f,0.85f,0.77f);
            fan = new GameObject("Deliberately opened controls").transform; fan.SetParent(owner.Panel,false);
            owner.Buttons = new OrynWorkspaceButton[7];
            hub = Button(owner.Panel,material,Own(Sector(0,0.028f,0,360,48)));
            hub.Action = OrynWorkspaceButton.Command.MenuHome; owner.Buttons[6] = hub;
            hubText = Label(owner.Panel,"ORYN",new Vector3(0,0,-0.011f),0.0022f);
            // Thin physical connection, plus an open arc instead of a solid backing board.
            hubRing = Visual(owner.Panel,Own(Sector(0.029f,0.030f,0,360,48)),resources.Accent);
            tether = new GameObject("Wrist tether").AddComponent<LineRenderer>();
            tether.transform.SetParent(owner.Panel,false);tether.useWorldSpace=false;tether.positionCount=2;
            tether.startWidth=0.0012f;tether.endWidth=0.0006f;tether.sharedMaterial=resources.Accent;
            Visual(fan,Own(Sector(0.076f,0.0775f,-82,82,40)),resources.Accent);
            title = Label(fan,"ORYN",new Vector3(-0.003f,0.061f,-0.011f),0.0025f);
            status = Label(fan,"",new Vector3(-0.03f,-0.066f,-0.011f),0.0017f);
            details = Label(fan,"",new Vector3(-0.075f,-0.09f,-0.011f),0.00165f);
            details.anchor = TextAnchor.UpperLeft; details.alignment = TextAlignment.Left;
            for (int i=0;i<4;i++) homeMeshes[i] = Own(Sector(0.091f,0.19f,60-i*40-18,60-i*40+18,12));
            for (int i=0;i<6;i++) actionMeshes[i] = Own(Sector(0.091f,0.19f,67.5f-i*27-11.5f,67.5f-i*27+11.5f,10));
            for(int i=0;i<6;i++)
            {
                slots[i] = Button(fan,material,actionMeshes[i]); owner.Buttons[i] = slots[i];
                captions[i] = Label(fan,"",Vector3.zero,0.00245f);
            }
            Layout(); owner.Panel.gameObject.SetActive(false);
        }
        private Mesh Own(Mesh mesh) { resources.Meshes.Add(mesh); return mesh; }
        private static Transform Visual(Transform parent, Mesh mesh, Material material)
        {
            var go = new GameObject("Wrist accent",typeof(MeshFilter),typeof(MeshRenderer));
            go.transform.SetParent(parent,false);go.GetComponent<MeshFilter>().sharedMesh=mesh;go.GetComponent<Renderer>().sharedMaterial=material;return go.transform;
        }
        private static OrynWorkspaceButton Button(Transform parent,Material material,Mesh mesh)
        {
            var go = new GameObject("Radial action",typeof(MeshFilter),typeof(MeshRenderer),typeof(MeshCollider));
            go.transform.SetParent(parent,false);go.GetComponent<MeshFilter>().sharedMesh=mesh;go.GetComponent<Renderer>().sharedMaterial=material;
            var collider=go.GetComponent<MeshCollider>();collider.sharedMesh=mesh;collider.convex=true;
            var button=go.AddComponent<OrynWorkspaceButton>();button.Bounds=collider;button.WristStyle=true;return button;
        }
        private TextMesh Label(Transform parent,string value,Vector3 position,float size)
        {
            var text=new GameObject("Radial caption").AddComponent<TextMesh>();text.transform.SetParent(parent,false);text.transform.localPosition=position;
            text.font=workspace.Status.font;text.fontSize=48;text.characterSize=size;text.anchor=TextAnchor.MiddleCenter;
            text.alignment=TextAlignment.Center;text.richText=false;text.text=value;text.color=new Color(0.86f,0.94f,0.96f);
            text.GetComponent<Renderer>().sharedMaterial=workspace.Status.GetComponent<Renderer>().sharedMaterial;return text;
        }
        public static Vector3 SlotCenter(int index,bool home)
        {
            float radians=(home ? 60-index*40 : 67.5f-index*27)*Mathf.Deg2Rad;
            return new Vector3(Mathf.Cos(radians)*0.143f,Mathf.Sin(radians)*0.143f,-0.011f);
        }
        private void Layout()
        {
            fan.gameObject.SetActive(reveal.Expanded);
            hub.transform.localScale=Vector3.one*(reveal.Expanded ? 1 : 0.60f);
            hubRing.localScale=hub.transform.localScale;
            hubText.transform.localScale=Vector3.one*(reveal.Expanded ? 1 : 0.70f);
            hubText.text=!reveal.Expanded ? "ORYN" : page<0 ? "Close" : "Back";
            title.text=page<0 ? "ORYN" : Titles[page];
            details.gameObject.SetActive(page==3);status.gameObject.SetActive(page!=3);
            previousStatus=previousDetails=null;
            for(int i=0;i<6;i++)
            {
                bool active=page<0 ? i<4 : Labels[page][i].Length>0;
                slots[i].gameObject.SetActive(active);captions[i].gameObject.SetActive(active);
                if(!active)continue;
                Mesh mesh=page<0 ? homeMeshes[i] : actionMeshes[i];
                slots[i].GetComponent<MeshFilter>().sharedMesh=mesh;((MeshCollider)slots[i].Bounds).sharedMesh=mesh;
                slots[i].Action=page<0 ? (OrynWorkspaceButton.Command)((int)OrynWorkspaceButton.Command.MenuObject+i) : Actions[page][i];
                captions[i].text=page<0 ? new[]{"Inspect","Motion","Objects","Details"}[i] : Labels[page][i];
                captions[i].transform.localPosition=SlotCenter(i,page<0);
            }
        }
        public void Navigate(OrynWorkspaceButton.Command action)
        {
            if(action==OrynWorkspaceButton.Command.MenuHome)
            {
                if(!reveal.Expanded) { page=-1;reveal.Toggle(); }
                else if(page>=0) page=-1;
                else reveal.Toggle();
            }
            else if(reveal.Expanded && action>=OrynWorkspaceButton.Command.MenuObject && action<=OrynWorkspaceButton.Command.MenuDetails)
                page=(int)action-(int)OrynWorkspaceButton.Command.MenuObject;
            Layout();
        }
        public void Hide()
        {
            reveal.Reset();page=-1;inputMode=-1;Layout();workspace.Panel.gameObject.SetActive(false);
        }
        public bool Update(OrynTrackedInput input,Pose eye,bool eligible,bool toggleController)
        {
            bool wasVisible=workspace.Panel.gameObject.activeSelf,wasExpanded=reveal.Expanded;
            int mode=input.Valid[2] && input.WristValid[0] ? 2 : input.Valid[0] ? 0 : -1;
            if(mode!=inputMode) { reveal.Reset();inputMode=mode; }
            Pose pose=default;
            if(!eligible || mode<0)reveal.Reset();
            else if(mode==2)
            {
                reveal.Sample(input.Palms[0],input.Wrists[0],eye,true,Time.unscaledDeltaTime);
                pose=OrynWristReveal.Placement(input.Wrists[0],input.Palms[0].Fingers,input.Palms[0].Normal,eye);
            }
            else
            {
                reveal.Controller(true,toggleController);
                pose=OrynWristReveal.Placement(input.Poses[0].position,input.Poses[0].rotation*Vector3.forward,
                    (eye.position-input.Poses[0].position).normalized,eye);
            }
            workspace.Panel.gameObject.SetActive(reveal.Visible);
            if(reveal.Visible)
            {
                // A short following filter removes raw wrist jitter without pinning the panel in space.
                float t=!wasVisible ? 1 : 1-Mathf.Exp(-Mathf.Max(0,Time.unscaledDeltaTime)/0.035f);
                workspace.Panel.SetPositionAndRotation(Vector3.Lerp(workspace.Panel.position,pose.position,t),Quaternion.Slerp(workspace.Panel.rotation,pose.rotation,t));
                Vector3 wrist = mode==2 ? input.Wrists[0] : input.Poses[0].position;
                tether.SetPosition(0,workspace.Panel.InverseTransformPoint(wrist));tether.SetPosition(1,Vector3.zero);
            }
            if(wasExpanded!=reveal.Expanded || wasVisible!=reveal.Visible) { page=-1;Layout(); }
            return wasVisible!=reveal.Visible || wasExpanded!=reveal.Expanded;
        }
        public void Refresh()
        {
            if(!reveal.Expanded)return;
            string value=workspace.MenuConfirmingDelete ? "Pinch Delete again to confirm" : page<0 ? "Choose a tool" : page==1 ? (workspace.CommandAssembly?.Owner.Mechanical?.Status ?? "No bound motion") :
                page==2 ? "Authored demos" : workspace.Status.text;
            if(value!=previousStatus) { status.text=Wrap(value??"",19,3);previousStatus=value; }
            string info=workspace.Inspector?.Details?.text ?? "Select a part.";
            if(page==3 && info!=previousDetails) { details.text=Wrap(info,24,7);previousDetails=info; }
        }
        private static string Wrap(string value,int width,int maxLines)
        {
            var lines=new List<string>();
            foreach(string paragraph in value.Split('\n'))
            {
                string line="";
                foreach(string original in paragraph.Split(new[]{' '},StringSplitOptions.RemoveEmptyEntries))
                {
                    string word=original;
                    if(line.Length>0 && line.Length+1+word.Length>width) { lines.Add(line);line=""; }
                    while(word.Length>width) { lines.Add(word.Substring(0,width));word=word.Substring(width); }
                    if(word.Length>0)line+=(line.Length>0 ? " " : "")+word;
                }
                lines.Add(line);
            }
            if(lines.Count>maxLines) { lines.RemoveRange(maxLines,lines.Count-maxLines);lines[maxLines-1]+="…"; }
            return string.Join("\n",lines);
        }

        // Closed extruded annular slice. Individual convex colliders leave real gaps between buttons.
        public static Mesh Sector(float inner,float outer,float start,float end,int steps)
        {
            var vertices=new Vector3[(steps+1)*4];var triangles=new List<int>();
            for(int i=0;i<=steps;i++)
            {
                float a=Mathf.Lerp(start,end,(float)i/steps)*Mathf.Deg2Rad;Vector3 radial=new Vector3(Mathf.Cos(a),Mathf.Sin(a),0);
                vertices[i*4]=radial*inner+Vector3.back*0.006f;vertices[i*4+1]=radial*outer+Vector3.back*0.006f;
                vertices[i*4+2]=radial*inner+Vector3.forward*0.002f;vertices[i*4+3]=radial*outer+Vector3.forward*0.002f;
                if(i==steps)continue;int n=i*4,m=n+4;
                Quad(triangles,n,m,m+1,n+1);Quad(triangles,n+2,n+3,m+3,m+2);
                Quad(triangles,n+1,m+1,m+3,n+3);Quad(triangles,n,n+2,m+2,m);
            }
            Quad(triangles,0,1,3,2);int last=steps*4;Quad(triangles,last,last+2,last+3,last+1);
            var mesh=new Mesh{name="ORYN radial segment"};mesh.vertices=vertices;mesh.triangles=triangles.ToArray();mesh.RecalculateNormals();mesh.RecalculateBounds();return mesh;
        }
        private static void Quad(List<int> indices,int a,int b,int c,int d)
        { indices.Add(a);indices.Add(b);indices.Add(c);indices.Add(a);indices.Add(c);indices.Add(d); }
    }
}
