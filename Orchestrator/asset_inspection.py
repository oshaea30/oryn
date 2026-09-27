"""Bounded, read-only GLB preflight; not a replacement for glTFast validation.

Counts the default scene, preserving node identity and mesh instances. A mesh
node is a candidate part, not proof of semantic identity or independent control.
"""
import hashlib
import json
import struct

from providers import GenerationError, validate_glb


def inspect_glb(data):
    try:
        return _inspect(data)
    except GenerationError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, struct.error, RecursionError, UnicodeError):
        raise GenerationError("GLB inspection failed: malformed scene, accessor, or chunk data.") from None


def _inspect(data):
    validate_glb(data)
    offset, chunks = 12, []
    while offset < len(data):
        size, kind = struct.unpack_from("<II", data, offset)
        if size % 4 or offset + 8 + size > len(data):
            raise GenerationError("Invalid GLB chunk length or alignment.")
        chunks.append((kind, data[offset + 8:offset + 8 + size]))
        offset += 8 + size
    if not chunks or chunks[0][0] != 0x4E4F534A or len(chunks[0][1]) > 4 * 1024 * 1024:
        raise GenerationError("GLB requires a JSON chunk of at most 4 MB.")
    if len(chunks) > 2 or (len(chunks) == 2 and chunks[1][0] != 0x004E4942):
        raise GenerationError("Use a GLB with one JSON and at most one BIN chunk.")
    doc = json.loads(chunks[0][1], parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    if doc["asset"]["version"] != "2.0":
        raise GenerationError("Only glTF 2.0 is supported.")

    def array(name):
        value = doc.get(name, [])
        if not isinstance(value, list) or len(value) > 4096 or any(not isinstance(x, dict) for x in value):
            raise GenerationError("Invalid or oversized GLB resource table.")
        return value

    def integer(value, minimum=0):
        if type(value) is not int or value < minimum:
            raise ValueError()
        return value

    def at(items, index):
        return items[integer(index)]

    nodes, meshes, scenes = array("nodes"), array("meshes"), array("scenes")
    accessors, views, buffers = array("accessors"), array("bufferViews"), array("buffers")
    images, textures, materials = array("images"), array("textures"), array("materials")
    issues, warnings = [], []
    binary_size = len(chunks[1][1]) if len(chunks) == 2 else 0
    if any("uri" in x for x in buffers + images):
        issues.append("External or URI-based resources are not supported; embed buffers and images in GLB.")
    if len(buffers) != 1 or integer(buffers[0]["byteLength"]) > binary_size or binary_size - buffers[0]["byteLength"] > 3:
        issues.append("Missing, multiple, or incomplete embedded binary buffers.")
    for view in views:
        if view.get("buffer") != 0 or integer(view.get("byteOffset", 0)) + integer(view["byteLength"]) > binary_size:
            raise GenerationError("Buffer view lies outside embedded binary data.")
    for image in images:
        if "bufferView" in image:
            at(views, image["bufferView"])
        if image.get("mimeType") not in ("image/png", "image/jpeg"):
            issues.append("Only embedded PNG/JPEG textures are preflight-supported.")
    required = doc.get("extensionsRequired", [])
    if not isinstance(required, list) or any(not isinstance(x, str) for x in required):
        raise ValueError()
    if set(required) - {"KHR_materials_unlit", "KHR_texture_transform"}:
        issues.append("Required extensions need manual runtime verification (compression/quantization is not preflight-supported).")
    if doc.get("animations"):
        warnings.append("Animations are not enabled in the current static-object runtime.")
    if textures:
        warnings.append("Texture decode/GPU memory and shader support require a headset import test.")

    def accessor(index, position=False):
        a = at(accessors, index)
        count = integer(a["count"], 1)
        if "sparse" in a or "bufferView" not in a:
            raise GenerationError("Sparse or compressed-only accessors require manual inspection; delivery blocked.")
        v = at(views, a["bufferView"])
        components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
        width = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}[a["componentType"]]
        element = components * width
        stride = integer(v.get("byteStride", element), element)
        end = integer(a.get("byteOffset", 0)) + (count - 1) * stride + element
        if end > v["byteLength"]:
            raise GenerationError("Accessor exceeds its buffer view.")
        if position and (a["type"] != "VEC3" or a["componentType"] != 5126):
            raise GenerationError("Positions must use uncompressed float VEC3 accessors.")
        if not position and (a["type"] != "SCALAR" or a["componentType"] not in (5121, 5123, 5125)):
            raise GenerationError("Invalid triangle index accessor.")
        return count

    scene_id = integer(doc.get("scene", 0))
    scene = at(scenes, scene_id)
    hierarchy, seen, used_meshes = [], set(), set()
    triangles = vertices = primitive_count = mesh_nodes = 0
    stack = [(i, 0, None) for i in reversed(scene.get("nodes", []))]
    while stack:
        index, depth, parent = stack.pop()
        node = at(nodes, index)
        if index in seen or depth > 64:
            raise GenerationError("Scene has a cycle, duplicate parent, or excessive nesting.")
        seen.add(index)
        entry = {"node_index": index, "parent_index": parent, "depth": depth,
            "name": str(node.get("name", "Node_" + str(index)))[:160], "mesh_index": node.get("mesh")}
        hierarchy.append(entry)
        if "skin" in node or "weights" in node:
            issues.append("Skinned/morphing objects are not supported by the static runtime.")
        if node.get("extensions"):
            issues.append("Node extensions require manual review; instance counts may differ at runtime.")
        if "mesh" in node:
            mesh = at(meshes, node["mesh"])
            used_meshes.add(node["mesh"])
            mesh_nodes += 1
            primitives = mesh["primitives"]
            if not isinstance(primitives, list) or not 1 <= len(primitives) <= 128:
                raise ValueError()
            for primitive in primitives:
                primitive_count += 1
                vertices_here = accessor(primitive["attributes"]["POSITION"], position=True)
                vertices += vertices_here  # Conservative: shared attributes counted per primitive.
                count = accessor(primitive["indices"]) if "indices" in primitive else vertices_here
                mode = primitive.get("mode", 4)
                if mode == 4 and count % 3 == 0:
                    triangles += count // 3
                elif mode in (5, 6) and count >= 3:
                    triangles += count - 2
                else:
                    issues.append("Only valid triangle primitives are supported in preflight.")
                if "material" in primitive:
                    at(materials, primitive["material"])
                if primitive.get("extensions") or primitive.get("targets"):
                    issues.append("Mesh compression, primitive extensions, or morph targets require manual review.")
        children = node.get("children", [])
        if not isinstance(children, list) or len(children) > len(nodes):
            raise ValueError()
        stack.extend((i, depth + 1, index) for i in reversed(children))
    if not 1 <= mesh_nodes <= 128 or primitive_count > 128:
        issues.append("Use 1–128 mesh objects and at most 128 primitives for this conservative preflight.")
    if vertices > 200000:
        issues.append("Conservative instantiated vertex count exceeds 200,000.")
    warnings.append("Separate mesh nodes are candidate parts, not semantic labels or independently grabbable parts yet.")
    return {"schema_version": 1, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
        "scene": str(scene.get("name", "Scene_" + str(scene_id)))[:160], "scene_index": scene_id,
        "mesh_objects": mesh_nodes, "unique_meshes": len(used_meshes), "primitives": primitive_count,
        "triangles": triangles, "vertices_upper_bound": vertices, "materials": len(materials),
        "textures": len(textures), "images": len(images), "hierarchy": hierarchy,
        "preflight": "FAIL" if issues else "PASS", "issues": list(dict.fromkeys(issues)),
        "warnings": warnings, "scope": "Static metadata preflight only; Unity import, bounds, visuals and manipulation still need headset verification."}
