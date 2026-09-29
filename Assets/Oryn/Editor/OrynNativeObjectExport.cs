using System;
using System.IO;
using System.Linq;
using Oryn.Interaction;
using UnityEditor;
using UnityEngine;

namespace Oryn.Editor
{
    // Research control export only. Exports the actual runtime geometry, never a replacement mesh.
    public static class OrynNativeObjectExport
    {
        [Serializable] public class Point { public float x,y,z; public Point(Vector3 v) { x=v.x;y=v.y;z=v.z; } }
        [Serializable] public class Part { public string id; public Point[] vertices; public int[] triangles; public float[] color; }
        [Serializable] public class Frame { public double cycle; public Part[] parts; }
        [Serializable] public class Export { public string source="authored_runtime_control"; public OrynMechanicalDefinition definition; public Frame[] frames; }
        public static void Run()
        {
            var material=new Material(Shader.Find("Unlit/Color"));
            var root=GameObject.CreatePrimitive(PrimitiveType.Cube);
            try
            {
                var owner=root.AddComponent<OrynWorkspaceObject>();
                var behavior=OrynMechanicalBenchmarks.Attach(owner,false,material,material);
                var result=new Export { definition=behavior.Definition, frames=new Frame[9] };
                for(int f=0;f<9;f++)
                {
                    behavior.Seek(f/8.0);
                    result.frames[f]=new Frame {cycle=f/8.0, parts=behavior.Definition.Links.Select(link=>{
                        var filter=behavior.Component(link.Id).GetComponentsInChildren<MeshFilter>()
                            .Single(m=>m.gameObject.name==link.GeometryId);
                        var block=new MaterialPropertyBlock();filter.GetComponent<Renderer>().GetPropertyBlock(block);
                        Color c=block.GetColor("_Color");
                        return new Part {id=link.Id,vertices=filter.sharedMesh.vertices.Select(v=>new Point(root.transform.InverseTransformPoint(filter.transform.TransformPoint(v)))).ToArray(),
                            triangles=filter.sharedMesh.triangles,color=new[]{c.r,c.g,c.b}};
                    }).ToArray()};
                }
                Directory.CreateDirectory("Builds/NativeObjects");
                File.WriteAllText("Builds/NativeObjects/authored-drone-runtime.json",JsonUtility.ToJson(result));
                Debug.Log("ORYN_NATIVE_EXPORT_OK components="+result.definition.Links.Length);
            }
            finally {UnityEngine.Object.DestroyImmediate(root);UnityEngine.Object.DestroyImmediate(material);}
        }
    }
}
