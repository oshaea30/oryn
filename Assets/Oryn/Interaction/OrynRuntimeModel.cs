using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using GLTFast;
using GLTFast.Loading;
using GLTFast.Logging;
using UnityEngine;

namespace Oryn.Interaction
{
    // Owns one imported asset's resources. Geometry is deliberately separate from
    // workspace state/interaction; deleting the workspace object disposes both.
    public sealed class OrynRuntimeModel : MonoBehaviour
    {
        public const long MaximumFileBytes = 16 * 1024 * 1024;
        public Bounds LocalBounds { get; private set; }
        public string SourceHash { get; private set; }
        public string SourcePath { get; private set; }
        private GltfImport importer;
        public static OrynRuntimeModel AuthoredDemonstration(string name, Bounds bounds)
        {
            var model = new GameObject(name).AddComponent<OrynRuntimeModel>();
            model.LocalBounds = bounds;
            // No generated-asset hash: a family demonstration cannot inherit the
            // identity, mappings or research records of a generated model.
            return model;
        }
        public static string ImportPath => Path.Combine(Application.persistentDataPath, "Imports", "model.glb");

        public static async Task<OrynRuntimeModel> Load(string path, CancellationToken cancellation = default)
        {
            cancellation.ThrowIfCancellationRequested();
            var info = new FileInfo(path);
            if (!info.Exists) throw new FileNotFoundException("Copy model.glb into the Imports folder first.");
            if (info.Length < 20 || info.Length > MaximumFileBytes) throw new InvalidDataException("Model must be a GLB smaller than 16 MB.");
            // Header validation is not a glTF parser; the maintained glTFast library
            // handles geometry, buffers, textures and node hierarchy.
            using (var stream = info.OpenRead())
            using (var reader = new BinaryReader(stream))
                if (reader.ReadUInt32() != 0x46546c67 || reader.ReadUInt32() != 2 || reader.ReadUInt32() != info.Length)
                    throw new InvalidDataException("Invalid GLB 2.0 header or incomplete file.");
            var root = new GameObject("External GLB"); root.SetActive(false);
            var model = root.AddComponent<OrynRuntimeModel>();
            try
            {
                model.SourcePath = Path.GetFullPath(path);
                model.SourceHash = OrynKnowledgeStore.HashFile(path);
                model.importer = new GltfImport(downloadProvider: new NoExternalDownloads(),
                    deferAgent: Application.isPlaying ? null : new UninterruptedDeferAgent(), logger: new ConsoleLogger());
                if (!await model.importer.LoadFile(path, cancellationToken: cancellation)) throw new InvalidDataException("GLB import failed; use a self-contained uncompressed model.");
                cancellation.ThrowIfCancellationRequested();
                var instance = new GameObjectInstantiator(model.importer, root.transform, new ConsoleLogger(),
                    new InstantiationSettings { Mask = ComponentType.Mesh });
                if (!await model.importer.InstantiateMainSceneAsync(instance, cancellation)) throw new InvalidDataException("GLB has no usable scene.");
                cancellation.ThrowIfCancellationRequested();
                model.Normalize();
                if (OrynKnowledgeStore.HashFile(path) != model.SourceHash) throw new InvalidDataException("Model changed during import");
                Debug.Log("ORYN_MODEL_PARSED name=" + info.Name + " bytes=" + info.Length);
                return model;
            }
            catch
            {
                model.importer?.Dispose(); model.importer = null;
                if (Application.isPlaying) Destroy(root); else DestroyImmediate(root);
                throw;
            }
        }

        private void Normalize()
        {
            var renderers = GetComponentsInChildren<MeshRenderer>(true);
            if (renderers.Length == 0 || renderers.Length > 128 || GetComponentsInChildren<SkinnedMeshRenderer>(true).Length > 0)
                throw new InvalidDataException("Use a static model with 1-128 mesh renderers.");
            Bounds bounds = new Bounds(); bool first = true; long vertices = 0;
            foreach (var renderer in renderers)
            {
                var filter = renderer.GetComponent<MeshFilter>();
                if (filter == null || filter.sharedMesh == null) continue;
                vertices += filter.sharedMesh.vertexCount;
                Bounds meshBounds = filter.sharedMesh.bounds;
                for (int corner = 0; corner < 8; corner++)
                {
                    Vector3 sign = new Vector3((corner & 1) == 0 ? -1 : 1, (corner & 2) == 0 ? -1 : 1, (corner & 4) == 0 ? -1 : 1);
                    Vector3 p = transform.InverseTransformPoint(renderer.transform.TransformPoint(meshBounds.center + Vector3.Scale(meshBounds.extents, sign)));
                    if (!float.IsFinite(p.x) || !float.IsFinite(p.y) || !float.IsFinite(p.z)) throw new InvalidDataException("Model bounds are not finite.");
                    if (first) { bounds = new Bounds(p, Vector3.zero); first = false; } else bounds.Encapsulate(p);
                }
                foreach (var material in renderer.sharedMaterials)
                    if (material == null || material.shader == null || !material.shader.isSupported) throw new InvalidDataException("Model material/shader is unsupported.");
            }
            float size = Mathf.Max(bounds.size.x, Mathf.Max(bounds.size.y, bounds.size.z));
            if (first || size < 0.00001f || vertices > 200000) throw new InvalidDataException("Model is empty, too small, or exceeds 200,000 vertices.");
            // Parent is subsequently scaled to 35 cm by the normal workspace prefab.
            transform.localScale = Vector3.one / size;
            transform.localPosition = -bounds.center / size;
            LocalBounds = new Bounds(Vector3.zero, bounds.size / size);
        }
        // Unity does not call OnDestroy for every never-activated object. Abandoned
        // hidden imports must explicitly release their resources before destruction.
        public void ReleaseResources() { importer?.Dispose(); importer = null; }
        private void OnDestroy() { ReleaseResources(); }

        // The first milestone is offline/self-contained GLB only. A GLB may still
        // reference URLs; reject those rather than silently downloading anything.
        private sealed class NoExternalDownloads : IDownloadProvider
        {
            public Task<IDownload> Request(Uri url) => throw new InvalidDataException("External GLB buffers are not supported; embed them in the file.");
            public Task<ITextureDownload> RequestTexture(Uri url, bool nonReadable) => throw new InvalidDataException("External GLB textures are not supported; embed them in the file.");
        }
    }
}
