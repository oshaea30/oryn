using System;
using System.IO;
using System.Linq;
using Oryn.Interaction;
using Oryn.Preview;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace Oryn.Editor
{
    public static class OrynMechanicalTests
    {
        private static int checks;
        [MenuItem("Oryn/Mechanics/Run deterministic tests")]
        public static void Run()
        {
            checks = 0;
            foreach (bool engine in new[] { false, true })
            {
                var definition = OrynMechanicalBenchmarks.Definition(engine);
                definition.Validate();
                Check(definition.Links.All(l => l.EvidenceStatus == "unsupported" && l.ReferenceIds.Length == 0), "authoring never implies verification");
                Check(definition.Links.Length <= OrynAssembly.MaximumParts, "Quest part budget");
                var evaluator = new OrynMechanicalEvaluator(definition);
                var poses = new Pose[definition.Links.Length]; var again = new Pose[poses.Length];
                evaluator.Evaluate(0.37, poses); evaluator.Evaluate(0.37, again);
                for (int i = 0; i < poses.Length; i++) Near(poses[i].position, again[i].position, "pure repeatable evaluation");
                for (int tick = 0; tick <= 72; tick++)
                {
                    evaluator.Evaluate(tick / 72.0, poses);
                    foreach (var rod in definition.Links.Where(l => l.Kind == OrynMotionKind.SliderCrankRod))
                    {
                        int r = Array.IndexOf(definition.Links, rod);
                        int p = Array.FindIndex(definition.Links, l => l.Id == rod.Id.Replace("rod_","piston_"));
                        Vector3 top = poses[r].position + poses[r].rotation * Vector3.up * rod.RodLength * 0.5f;
                        Near(top, poses[p].position, "rod endpoint meets wrist pin throughout cycle");
                        Vector3 bottom = poses[r].position - poses[r].rotation * Vector3.up * rod.RodLength * 0.5f;
                        Check(Mathf.Abs((bottom - rod.Pivot).magnitude - rod.CrankRadius) < 0.0001f, "crank radius preserved");
                        Check(Vector3.Cross(poses[p].position - rod.Pivot, rod.Axis).magnitude < 0.0001f, "piston stays on cylinder axis");
                    }
                }
                Integration(engine);
            }
            var invalid = OrynMechanicalBenchmarks.Definition(true); invalid.Links[1].DriverId = invalid.Links[1].Id;
            Reject(() => invalid.Validate(), "cyclic timing rejected");
            invalid = OrynMechanicalBenchmarks.Definition(true); invalid.Links[0].EvidenceStatus = "verified";
            Reject(() => invalid.Validate(), "unproven verified claim rejected");
            invalid = OrynMechanicalBenchmarks.Definition(true); invalid.Links.First(l=>l.Kind==OrynMotionKind.SliderCrankRod).RodLength = 0.01f;
            Reject(() => invalid.Validate(), "impossible rod rejected");
            var linear = new OrynMechanicalDefinition {Id="linear-test", Revision="1", Scope="test", Links = new[] {
                new OrynMechanicalLink {Id="driver",GeometryId="a",Kind=OrynMotionKind.Rotation},
                new OrynMechanicalLink {Id="slider",GeometryId="b",Kind=OrynMotionKind.Translation,DriverId="driver",Ratio=2,Travel=0.5f,Axis=Vector3.right},
                new OrynMechanicalLink {Id="reciprocal",GeometryId="c",Kind=OrynMotionKind.Reciprocation,Travel=0.2f,Axis=Vector3.up} }};
            var e = new OrynMechanicalEvaluator(linear); var result = new Pose[3]; e.Evaluate(0.25,result);
            Near(result[1].position,Vector3.right*0.5f,"linked ratio drives translation");
            Near(result[2].position,Vector3.up*0.2f,"sinusoidal reciprocation");
            Reject(()=>e.Evaluate(double.NaN,result),"invalid clock rejected");
            Debug.Log("ORYN_MECHANICAL_TESTS_OK checks=" + checks);
        }
        private static void Integration(bool engine)
        {
            var material = new Material(Shader.Find("Unlit/Color"));
            var root = GameObject.CreatePrimitive(PrimitiveType.Cube);
            root.transform.SetPositionAndRotation(new Vector3(1,1,2),Quaternion.Euler(10,35,5)); root.transform.localScale = Vector3.one*0.35f;
            var owner = root.AddComponent<OrynWorkspaceObject>();
            try
            {
                var b = OrynMechanicalBenchmarks.Attach(owner,engine,material,material); var assembly = owner.Assembly;
                Check(assembly != null && !OrynKnowledgeStore.IsHash(assembly.AssetHash), "demo cannot impersonate generated asset");
                var homes = assembly.Parts.Select(p=>p.transform.localPosition).ToArray();
                b.Play(); b.Advance(0.5); Check(Math.Abs(b.Cycles-0.25)<0.000001,"known elapsed time");
                b.Pause(); b.Advance(0.2); Check(Math.Abs(b.Cycles-0.25)<0.000001,"pause retains phase");
                b.SetSpeed(0.15f); b.Play(); b.Advance(1); Check(Math.Abs(b.Cycles-0.325)<0.000001,"slow motion");
                Reject(()=>b.SetSpeed(float.NaN),"invalid speed rejected");
                assembly.Explode(); b.Advance(0.1);
                for(int i=0;i<homes.Length;i++) Near(assembly.Parts[i].transform.localPosition,homes[i]*2.1f,"motion does not overwrite spread");
                b.IsolateSubsystem(engine?"rotating_assembly":"propulsion"); double phase=b.Cycles; b.Advance(0.2);
                Check(b.Cycles>phase && assembly.Isolated && assembly.Parts.Any(p=>!p.gameObject.activeSelf),"subsystem isolation keeps shared clock");
                var part=assembly.Parts.First(p=>p.gameObject.activeSelf);
                var newPose = new Pose(part.transform.position+Vector3.up*0.2f,Quaternion.Euler(10,20,30));
                part.State.Reset(newPose);part.Apply(false,true);b.Advance(0.1);
                Near(part.transform.position,newPose.position,"animation preserves user translation");
                Check(Quaternion.Angle(part.transform.rotation,newPose.rotation)<0.01f,"animation preserves user rotation");
                assembly.Reassemble(); b.StopHome();
                Check(!b.Running && b.Cycles==0 && assembly.Parts.All(p=>p.gameObject.activeSelf),"home and reassembly restore state");
                for(int i=0;i<homes.Length;i++) Near(assembly.Parts[i].transform.localPosition,homes[i],"reassembled home");
                b.Play(); for(int i=0;i<100;i++)b.Advance(0.01);double partitioned=b.Cycles;
                b.StopHome();b.Play();b.Advance(1);Check(Math.Abs(b.Cycles-partitioned)<1e-9,"clock partition independence");
            }
            finally {UnityEngine.Object.DestroyImmediate(root);UnityEngine.Object.DestroyImmediate(material);}
        }
        [MenuItem("Oryn/Mechanics/Open desktop demo")]
        public static void OpenPreview()
        {
            if(EditorApplication.isPlayingOrWillChangePlaymode || !EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())return;
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
            var camera = MakeCamera();
            var preview = camera.gameObject.AddComponent<OrynMechanicalPreview>(); preview.Surface = new Material(Shader.Find("Unlit/Color"));
            EditorApplication.isPlaying=true;
        }
        private static Camera MakeCamera()
        {
            var camera = new GameObject("Mechanical demo camera",typeof(Camera)).GetComponent<Camera>();
            camera.transform.SetPositionAndRotation(new Vector3(0.9f,0.65f,-1.3f),Quaternion.LookRotation(new Vector3(0,0.1f,0)-new Vector3(0.9f,0.65f,-1.3f)));
            camera.clearFlags=CameraClearFlags.SolidColor;camera.backgroundColor=new Color(0.035f,0.05f,0.065f);camera.fieldOfView=48;camera.nearClipPlane=0.01f;
            return camera;
        }
        public static async void RunBatch()
        {
            try
            {
                Run();OrynWorkspaceTests.Run();OrynMenuTests.Run();OrynCommandTests.Run();await OrynAssemblyTests.Run();
                Directory.CreateDirectory("Builds/Mechanical");
                foreach(bool engine in new[]{false,true})
                {
                    string name=engine?"v8":"drone";
                    File.WriteAllText("Builds/Mechanical/"+name+".json",JsonUtility.ToJson(OrynMechanicalBenchmarks.Definition(engine),true));
                    if(SystemInfo.graphicsDeviceType==UnityEngine.Rendering.GraphicsDeviceType.Null)continue;
                    EditorSceneManager.NewScene(NewSceneSetup.EmptyScene,NewSceneMode.Single);
                    var camera=MakeCamera();var material=new Material(Shader.Find("Unlit/Color"));
                    var root=GameObject.CreatePrimitive(PrimitiveType.Cube);var owner=root.AddComponent<OrynWorkspaceObject>();
                    var behavior=OrynMechanicalBenchmarks.Attach(owner,engine,material,material);behavior.Seek(0.15);
                    var rt=new RenderTexture(1200,900,24);camera.targetTexture=rt;camera.Render();RenderTexture.active=rt;
                    var image=new Texture2D(1200,900,TextureFormat.RGB24,false);image.ReadPixels(new Rect(0,0,1200,900),0,0);image.Apply();
                    File.WriteAllBytes("Builds/Mechanical/"+name+".png",image.EncodeToPNG());
                    RenderTexture.active=null;camera.targetTexture=null;UnityEngine.Object.DestroyImmediate(image);UnityEngine.Object.DestroyImmediate(rt);
                    UnityEngine.Object.DestroyImmediate(root);UnityEngine.Object.DestroyImmediate(material);
                }
                Debug.Log("ORYN_MECHANICAL_BATCH_OK");EditorApplication.Exit(0);
            }
            catch(Exception error){Debug.LogException(error);EditorApplication.Exit(1);}
        }
        private static void Check(bool condition,string name){if(!condition)throw new InvalidOperationException("Mechanical: "+name);checks++;}
        private static void Near(Vector3 a,Vector3 b,string name)=>Check(Vector3.Distance(a,b)<0.0001f,name);
        private static void Reject(Action action,string name){bool failed=false;try{action();}catch(ArgumentException){failed=true;}Check(failed,name);}
    }
}
