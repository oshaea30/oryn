using System;
using System.Collections.Generic;
using UnityEngine;

namespace Oryn.Interaction
{
    // Quick deliberate pose opens directly. Relaxing the fingers does not close an open menu.
    public sealed class OrynWristReveal
    {
        public bool Visible => Expanded;
        public bool Expanded { get; private set; }
        private float dwell;
        private bool armed = true;
        public void Reset() { Expanded = false; dwell = 0; armed = false; }
        public void Toggle() { if (Expanded) Reset(); else { Expanded = true; armed = false; } }
        public bool Sample(OrynPalmSample palm, Vector3 wrist, Pose eye, bool pose, bool eligible, float seconds)
        {
            Vector3 toEye = eye.position - wrist;
            bool available = eligible && palm.Valid && toEye.magnitude >= 0.18f && toEye.magnitude <= 0.9f &&
                Vector3.Dot(palm.Normal, Vector3.up) > (Expanded ? 0.15f : 0.5f) &&
                Vector3.Dot(eye.rotation * Vector3.forward, -toEye.normalized) > 0.25f;
            if (!available || !float.IsFinite(seconds)) { Reset(); return false; }
            if (!pose) { armed = true; dwell = 0; }
            else if (armed && !Expanded)
            {
                dwell += Mathf.Clamp(seconds, 0, 0.05f);
                if (dwell >= 0.08f) { Expanded = true; armed = false; }
            }
            return Expanded;
        }
        public void Controller(bool available, bool toggle)
        {
            if (!available) { Reset(); return; }
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
        private readonly OrynWristReveal[] reveals = { new OrynWristReveal(), new OrynWristReveal() };
        private OrynWristReveal reveal => reveals[HostHand];
        public int HostHand { get; private set; }
        public bool AllowsSource(int source) => Expanded && source >= 0 && source < 4 && source % 2 != HostHand;
        private readonly OrynWristVisualResources resources;
        private readonly Transform fan, hubRing;
        private readonly LineRenderer tether;
        private readonly OrynWorkspaceButton hub;
        private readonly TextMesh hubText, title, status, details;
        private readonly TextMesh[] captions = new TextMesh[6];
        private readonly OrynWorkspaceButton[] slots = new OrynWorkspaceButton[6];
        private readonly Mesh[] homeMeshes = new Mesh[4], actionMeshes = new Mesh[6];
        private readonly Mesh[] mirroredHome = new Mesh[4], mirroredActions = new Mesh[6];
        private readonly Transform fanAccent;
        private readonly int[] inputModes = { -1, -1 };
        private int page = 0;
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
            fanAccent = Visual(fan,Own(Sector(0.076f,0.0775f,-82,82,40)),resources.Accent);
            title = Label(fan,"ORYN",new Vector3(-0.003f,0.061f,-0.011f),0.0025f);
            status = Label(fan,"",new Vector3(-0.03f,-0.066f,-0.011f),0.0017f);
            details = Label(fan,"",new Vector3(-0.075f,-0.09f,-0.011f),0.00165f);
            details.anchor = TextAnchor.UpperLeft; details.alignment = TextAlignment.Left;
            for (int i=0;i<4;i++) homeMeshes[i] = Own(Sector(0.091f,0.19f,60-i*40-18,60-i*40+18,12));
            for (int i=0;i<6;i++) actionMeshes[i] = Own(Sector(0.091f,0.19f,67.5f-i*27-11.5f,67.5f-i*27+11.5f,10));
            for(int i=0;i<4;i++) mirroredHome[i]=Own(Mirror(homeMeshes[i]));
            for(int i=0;i<6;i++) mirroredActions[i]=Own(Mirror(actionMeshes[i]));
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
        public static Vector3 SlotCenter(int index,bool home,int hand=0)
        {
            float radians=(home ? 60-index*40 : 67.5f-index*27)*Mathf.Deg2Rad;
            return new Vector3(Mathf.Cos(radians)*0.143f*(hand==0 ? 1 : -1),Mathf.Sin(radians)*0.143f,-0.011f);
        }
        private void Layout()
        {
            fan.gameObject.SetActive(reveal.Expanded);
            int direction = HostHand==0 ? 1 : -1;
            fanAccent.localScale = new Vector3(direction,1,1);
            status.transform.localPosition = new Vector3(-0.03f*direction,-0.066f,-0.011f);
            details.transform.localPosition = new Vector3(HostHand==0 ? -0.075f : -0.02f,-0.09f,-0.011f);
            hub.transform.localScale=Vector3.one*(reveal.Expanded ? 1 : 0.60f);
            hubRing.localScale=hub.transform.localScale;
            hubText.transform.localScale=Vector3.one*(reveal.Expanded ? 1 : 0.70f);
            hubText.text=HostHand==1 || page<0 ? "Close" : "Tools";
            title.text=page<0 ? "LEFT / TOOLS" : (HostHand==0 ? "L / " : "R / ")+Titles[page];
            details.gameObject.SetActive(page==3);status.gameObject.SetActive(page!=3);
            previousStatus=previousDetails=null;
            for(int i=0;i<6;i++)
            {
                bool active=page<0 ? i<4 && i!=1 : Labels[page][i].Length>0;
                slots[i].gameObject.SetActive(active);captions[i].gameObject.SetActive(active);
                if(!active)continue;
                Mesh mesh=HostHand==0 ? (page<0 ? homeMeshes[i] : actionMeshes[i]) : (page<0 ? mirroredHome[i] : mirroredActions[i]);
                slots[i].GetComponent<MeshFilter>().sharedMesh=mesh;((MeshCollider)slots[i].Bounds).sharedMesh=mesh;
                slots[i].Action=page<0 ? (OrynWorkspaceButton.Command)((int)OrynWorkspaceButton.Command.MenuObject+i) : Actions[page][i];
                captions[i].text=page<0 ? new[]{"Inspect","Motion","Objects","Details"}[i] : Labels[page][i];
                captions[i].transform.localPosition=SlotCenter(i,page<0,HostHand);
            }
        }
        public void Navigate(OrynWorkspaceButton.Command action)
        {
            if (!reveal.Expanded) return;
            if(action==OrynWorkspaceButton.Command.MenuHome)
            {
                if(HostHand==1 || page<0) reveal.Reset(); else page=-1;
            }
            else if(HostHand==0 && action>=OrynWorkspaceButton.Command.MenuObject && action<=OrynWorkspaceButton.Command.MenuDetails && action!=OrynWorkspaceButton.Command.MenuMotion)
                page=(int)action-(int)OrynWorkspaceButton.Command.MenuObject;
            workspace.Panel.gameObject.SetActive(reveal.Visible);
            Layout();
        }
        public void Hide()
        {
            foreach(var state in reveals) state.Reset();
            page=HostHand==0 ? 0 : 1;Layout();workspace.Panel.gameObject.SetActive(false);
        }
        public bool Update(OrynTrackedInput input,Pose eye,bool eligible,bool toggleLeft,bool toggleRight=false)
        {
            bool wasVisible=workspace.Panel.gameObject.activeSelf;int previousHand=HostHand, requestedHand=-1;
            for(int hand=0;hand<2;hand++)
            {
                bool wasOpen=reveals[hand].Expanded;
                int mode=input.Valid[hand+2] && input.WristValid[hand] ? 2 : input.Valid[hand] ? 0 : -1;
                if(mode!=inputModes[hand] && inputModes[hand]>=0) reveals[hand].Reset();
                inputModes[hand]=mode;
                if(!eligible || mode<0) reveals[hand].Reset();
                else if(mode==2) reveals[hand].Sample(input.Palms[hand],input.Wrists[hand],eye,input.WristMenuPose[hand],true,Time.unscaledDeltaTime);
                else reveals[hand].Controller(true,hand==0 ? toggleLeft : toggleRight);
                if(!wasOpen && reveals[hand].Expanded)requestedHand=hand;
            }
            if(requestedHand>=0)HostHand=requestedHand;
            if(!reveals[HostHand].Expanded && reveals[1-HostHand].Expanded)HostHand=1-HostHand;
            // A fresh pose switches wrists directly; a held pose on the old wrist cannot steal focus back.
            if(reveal.Expanded && reveals[1-HostHand].Expanded)reveals[1-HostHand].Reset();
            bool visible=reveal.Visible;
            workspace.Panel.gameObject.SetActive(visible);
            if(visible)
            {
                int hand=HostHand;bool trackedHand=inputModes[hand]==2;
                Vector3 wrist=trackedHand ? input.Wrists[hand] : input.Poses[hand].position;
                Vector3 fingers=trackedHand ? input.Palms[hand].Fingers : input.Poses[hand].rotation*Vector3.forward;
                Vector3 normal=trackedHand ? input.Palms[hand].Normal : (eye.position-wrist).normalized;
                Pose pose=OrynWristReveal.Placement(wrist,fingers,normal,eye);
                float t=!wasVisible || previousHand!=HostHand ? 1 : 1-Mathf.Exp(-Mathf.Max(0,Time.unscaledDeltaTime)/0.015f);
                workspace.Panel.SetPositionAndRotation(Vector3.Lerp(workspace.Panel.position,pose.position,t),Quaternion.Slerp(workspace.Panel.rotation,pose.rotation,t));
                tether.SetPosition(0,workspace.Panel.InverseTransformPoint(wrist));tether.SetPosition(1,Vector3.zero);
            }
            bool changed=wasVisible!=visible || previousHand!=HostHand;
            if(changed) { page=HostHand==0 ? 0 : 1;Layout(); }
            return changed;
        }
        public void Refresh()
        {
            if(!reveal.Expanded)return;
            string value=workspace.MenuConfirmingDelete ? "Pinch Delete again to confirm" : page<0 ? "Choose a tool" : page==1 ? (workspace.CommandAssembly?.Owner.Mechanical?.Status ?? "Motion unavailable") :
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
        private static Mesh Mirror(Mesh source)
        {
            var mesh=UnityEngine.Object.Instantiate(source);var vertices=mesh.vertices;var triangles=mesh.triangles;
            for(int i=0;i<vertices.Length;i++)vertices[i].x=-vertices[i].x;
            for(int i=0;i<triangles.Length;i+=3) { int swap=triangles[i];triangles[i]=triangles[i+2];triangles[i+2]=swap; }
            mesh.vertices=vertices;mesh.triangles=triangles;mesh.RecalculateNormals();mesh.RecalculateBounds();return mesh;
        }
        private static void Quad(List<int> indices,int a,int b,int c,int d)
        { indices.Add(a);indices.Add(b);indices.Add(c);indices.Add(a);indices.Add(c);indices.Add(d); }
    }
}
