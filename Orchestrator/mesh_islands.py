"""Offline, lossless topology separation for the first position-only drone GLB.

Deliberately narrow: one static mesh node, one uncompressed indexed TRIANGLES
primitive, POSITION only. Refuse other layouts rather than silently losing UVs,
normals, skinning, materials or scene transforms. No provider/network dependencies.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import struct

from asset_inspection import inspect_glb
from providers import GenerationError, MAX_BYTES


def decode(data):
    report = inspect_glb(data)
    if report['preflight'] != 'PASS':
        raise GenerationError('Source must pass static preflight before separation.')
    length = struct.unpack_from('<I', data, 12)[0]
    doc = json.loads(data[20:20 + length])
    binary = data[28 + length:]
    if (len(doc['nodes']) != 1 or len(doc['meshes']) != 1 or
            len(doc['scenes']) != 1 or doc['scenes'][0]['nodes'] != [0] or
            doc['nodes'][0].get('mesh') != 0 or doc['nodes'][0].get('children') or
            doc.get('animations') or doc.get('skins') or doc.get('extensionsRequired') or
            doc.get('extensionsUsed') or doc.get('extensions') or doc['meshes'][0].get('weights')):
        raise GenerationError('Separator supports one static, standalone mesh node only.')
    node = doc['nodes'][0]
    if set(node) - {'mesh', 'name', 'matrix', 'translation', 'rotation', 'scale', 'extras'}:
        raise GenerationError('Unsupported node properties; original left untouched.')
    primitives = doc['meshes'][0]['primitives']
    if len(primitives) != 1:
        raise GenerationError('Separator currently requires one primitive.')
    primitive = primitives[0]
    if (primitive.get('mode', 4) != 4 or set(primitive['attributes']) != {'POSITION'} or
            'indices' not in primitive or primitive.get('targets') or primitive.get('extensions')):
        raise GenerationError('Separator requires indexed triangles with POSITION only; attributes will not be discarded.')

    def read(index, fmt):
        accessor = doc['accessors'][index]
        view = doc['bufferViews'][accessor['bufferView']]
        if view.get('extensions') or accessor.get('extensions') or accessor.get('normalized'):
            raise GenerationError('Unsupported accessor or buffer-view encoding.')
        size = struct.calcsize(fmt)
        start = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
        stride = view.get('byteStride', size)
        return [struct.unpack_from(fmt, binary, start + i * stride) for i in range(accessor['count'])]

    positions = read(primitive['attributes']['POSITION'], '<3f')
    ia = doc['accessors'][primitive['indices']]
    index_format = {5121:'<B', 5123:'<H', 5125:'<I'}[ia['componentType']]
    indices = [x[0] for x in read(primitive['indices'], index_format)]
    if any(not math.isfinite(x) for p in positions for x in p):
        raise GenerationError('Non-finite vertex position.')
    if any(i >= len(positions) for i in indices):
        raise GenerationError('Triangle index outside vertex array.')
    faces = [tuple(indices[i:i+3]) for i in range(0, len(indices), 3)]
    if len(faces) > 200000:
        raise GenerationError('Triangle limit exceeded for offline separation.')
    return doc, positions, faces


def components(positions, faces, weld_exact=False):
    parent = list(range(len(positions)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def join(a, b):
        a, b = root(a), root(b)
        if a != b:
            parent[b] = a
    if weld_exact:
        seen = {}
        for i, p in enumerate(positions):
            if p in seen:
                join(i, seen[p])
            else:
                seen[p] = i
    for a, b, c in faces:
        join(a, b)
        join(a, c)
    groups = defaultdict(list)
    for i, face in enumerate(faces):
        groups[root(face[0])].append(i)
    # Stable identifiers for a given source checksum, never semantic names.
    return sorted(groups.values(), key=lambda group: (-len(group), group[0]))


def bounds(points):
    low = [min(p[a] for p in points) for a in range(3)]
    high = [max(p[a] for p in points) for a in range(3)]
    return {'min':low, 'max':high, 'center':[(a+b)/2 for a,b in zip(low,high)],
        'size':[b-a for a,b in zip(low,high)]}


def separate(data, *, root_name='Drone / original transform'):
    doc, positions, faces = decode(data)
    islands = components(positions, faces)
    welded = components(positions, faces, weld_exact=True)
    if not 1 <= len(islands) <= 128:
        raise GenerationError('Island count exceeds the Quest renderer budget; no export created.')
    source_hash = hashlib.sha256(data).hexdigest()
    report = {'schema_version':1, 'source_sha256':source_hash, 'source_triangles':len(faces),
        'source_vertices':len(positions), 'index_islands':len(islands), 'exact_position_islands':len(welded),
        'connectivity':'Triangles sharing a vertex index; no tolerance welding or geometric cuts.',
        'semantic_status':'Unassigned. Disconnected surface islands are not proven mechanical components.',
        'bounds_local':bounds(positions), 'islands':[]}
    out = deepcopy(doc)
    out['asset']['generator'] = 'ORYN offline island separator v1'
    original_node = deepcopy(doc['nodes'][0])
    original_node.pop('mesh')
    original_node['name'] = root_name
    original_node['children'] = list(range(1, len(islands) + 1))
    out['nodes'] = [original_node]
    out['meshes'], out['accessors'], out['bufferViews'] = [], [], []
    binary = bytearray()
    original_primitive = doc['meshes'][0]['primitives'][0]

    def add_accessor(raw, count, kind, component_type, target, **extra):
        binary.extend(bytes(-len(binary) % 4))
        view = len(out['bufferViews'])
        out['bufferViews'].append({'buffer':0,'byteOffset':len(binary),'byteLength':len(raw),'target':target})
        binary.extend(raw)
        index = len(out['accessors'])
        out['accessors'].append(dict(bufferView=view, count=count, type=kind, componentType=component_type, **extra))
        return index

    for number, face_ids in enumerate(islands, 1):
        used = sorted({v for i in face_ids for v in faces[i]})
        local = {old:new for new,old in enumerate(used)}
        points = [positions[i] for i in used]
        local_faces = [tuple(local[v] for v in faces[i]) for i in face_ids]
        box = bounds(points)
        name = f'island_{number:03}'
        position_data = b''.join(struct.pack('<3f', *p) for p in points)
        index_data = b''.join(struct.pack('<3I', *f) for f in local_faces)
        pos = add_accessor(position_data, len(points), 'VEC3', 5126, 34962, min=box['min'], max=box['max'])
        idx = add_accessor(index_data, 3*len(local_faces), 'SCALAR', 5125, 34963)
        primitive = deepcopy(original_primitive)
        primitive.update(attributes={'POSITION':pos}, indices=idx)
        out['meshes'].append({'name':name,'primitives':[primitive]})
        out['nodes'].append({'name':name, 'mesh':number-1,
            'extras':{'oryn':{'source_sha256':source_hash,'island_id':name,'semantic_status':'unassigned'}}})
        report['islands'].append({'id':name, 'triangles':len(face_ids), 'vertices':len(used),
            'bounds_local':box, 'source_face_indices':face_ids, 'semantic_label':None})

    # Keep only geometry-only inputs for this first exporter. Material/image buffers
    # cannot safely be rebuilt by a position-only separator.
    if doc.get('materials') or doc.get('images') or doc.get('textures'):
        raise GenerationError('Export of material/texture resources is not supported yet; original left untouched.')
    out['buffers'] = [{'byteLength':len(binary)}]
    binary.extend(bytes(-len(binary) % 4))
    raw = json.dumps(out, separators=(',',':'), allow_nan=False).encode()
    raw += b' ' * (-len(raw) % 4)
    body = struct.pack('<II', len(raw), 0x4E4F534A) + raw + struct.pack('<II',len(binary),0x004E4942) + binary
    glb = struct.pack('<III',0x46546C67,2,12+len(body)) + body
    if len(glb) > MAX_BYTES:
        raise GenerationError('Separated asset exceeds the file-size budget.')
    check = inspect_glb(glb)
    if check['preflight'] != 'PASS' or check['triangles'] != len(faces) or check['mesh_objects'] != len(islands):
        raise GenerationError('Separated asset failed export validation.')
    report['export_sha256'] = check['sha256']
    report['export_preflight'] = check
    preview = {'positions':positions, 'faces':faces, 'islands':report['islands'],
        'source_sha256':source_hash, 'bounds':report['bounds_local']}
    return glb, report, preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path, help='New directory only; existing output is never overwritten')
    args = parser.parse_args()
    if args.source.stat().st_size > MAX_BYTES:
        raise GenerationError('Source exceeds file-size budget.')
    data = args.source.read_bytes()
    glb, report, preview = separate(data)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    (args.output/'drone-islands.glb').write_bytes(glb)
    (args.output/'islands.json').write_text(json.dumps(report, indent=2))
    template = (Path(__file__).parent/'island_preview.html').read_text()
    # Numeric data plus generated identifiers only; no untrusted mesh names/HTML.
    (args.output/'index.html').write_text(template.replace('/*__ISLAND_DATA__*/null', json.dumps(preview, separators=(',',':'))))
    assert hashlib.sha256(args.source.read_bytes()).hexdigest() == report['source_sha256']
    print(json.dumps({k:report[k] for k in ('source_triangles','index_islands','exact_position_islands','source_sha256','export_sha256')}, indent=2))


if __name__ == '__main__':
    main()
