from collections import Counter
import hashlib
import json
import struct
import unittest

from asset_inspection import inspect_glb
from mesh_islands import components, decode, separate
from providers import GenerationError


def fixture(points=None, faces=None, change=None):
    points = points or [(0,0,0),(1,0,0),(0,1,0),(3,0,0),(4,0,0),(3,1,0)]
    faces = faces or [(0,1,2),(3,4,5)]
    pos = b''.join(struct.pack('<3f', *p) for p in points)
    ind = b''.join(struct.pack('<3I', *f) for f in faces)
    doc = {'asset':{'version':'2.0'},'buffers':[{'byteLength':len(pos+ind)}],
        'bufferViews':[{'buffer':0,'byteLength':len(pos)},{'buffer':0,'byteOffset':len(pos),'byteLength':len(ind)}],
        'accessors':[{'bufferView':0,'componentType':5126,'count':len(points),'type':'VEC3'},
            {'bufferView':1,'componentType':5125,'count':len(faces)*3,'type':'SCALAR'}],
        'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1}]}],
        'nodes':[{'name':'Original','mesh':0,'translation':[1,2,3]}], 'scene':0,'scenes':[{'nodes':[0]}]}
    if change:change(doc)
    raw=json.dumps(doc).encode();raw+=b' '*(-len(raw)%4)
    body=struct.pack('<II',len(raw),0x4E4F534A)+raw+struct.pack('<II',len(pos+ind),0x004E4942)+pos+ind
    return struct.pack('<III',0x46546C67,2,len(body)+12)+body


def exported_triangles(data):
    n=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+n]);binary=data[28+n:]
    def values(index,fmt):
        a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
        return [struct.unpack_from(fmt,binary,v.get('byteOffset',0)+i*struct.calcsize(fmt)) for i in range(a['count'])]
    triangles=[]
    for mesh in doc['meshes']:
        p=mesh['primitives'][0];pts=values(p['attributes']['POSITION'],'<3f');ind=values(p['indices'],'<I')
        triangles.extend(tuple(pts[ind[k+j][0]] for j in range(3)) for k in range(0,len(ind),3))
    return doc,Counter(triangles)


class IslandTests(unittest.TestCase):
    def test_roundtrip_preserves_triangles_winding_and_transform(self):
        original=fixture();before=hashlib.sha256(original).hexdigest()
        out,report,_=separate(original)
        _,pts,faces=decode(original);doc,triangles=exported_triangles(out)
        self.assertEqual(triangles,Counter(tuple(pts[i] for i in f) for f in faces))
        self.assertEqual(report['index_islands'],2)
        self.assertEqual(report['exact_position_islands'],2)
        self.assertEqual(doc['nodes'][0]['translation'],[1,2,3])
        self.assertEqual(report['source_sha256'],before)
        self.assertEqual(hashlib.sha256(original).hexdigest(),before)
        self.assertEqual(inspect_glb(out)['mesh_objects'],2)
        self.assertTrue(all(p['semantic_label'] is None for p in report['islands']))

    def test_vertex_seams_reported_without_welding_export(self):
        points=[(0,0,0),(1,0,0),(0,1,0),(0,0,0),(-1,0,0),(0,-1,0)]
        _,report,_=separate(fixture(points=points))
        self.assertEqual(report['index_islands'],2);self.assertEqual(report['exact_position_islands'],1)

    def test_nearby_positions_not_silently_welded(self):
        points=[(0,0,0),(1,0,0),(0,1,0),(.00001,0,0),(-1,0,0),(0,-1,0)]
        _,report,_=separate(fixture(points=points))
        self.assertEqual(report['exact_position_islands'],2)

    def test_shared_index_connects_faces(self):
        _,report,_=separate(fixture(faces=[(0,1,2),(2,3,4)]))
        self.assertEqual(report['index_islands'],1)

    def test_deterministic_ids_and_face_coverage(self):
        one,r1,_=separate(fixture());two,r2,_=separate(fixture())
        self.assertEqual(one,two);self.assertEqual(r1,r2)
        ids=[i for p in r1['islands'] for i in p['source_face_indices']]
        self.assertEqual(sorted(ids),[0,1]);self.assertEqual(len(set(ids)),2)

    def test_refuses_to_drop_normals_uvs_or_materials(self):
        changes=[lambda d:d['meshes'][0]['primitives'][0]['attributes'].update(NORMAL=0),
            lambda d:d['meshes'][0]['primitives'][0]['attributes'].update(TEXCOORD_0=0),
            lambda d:d.update(materials=[{}])]
        for change in changes:
            with self.assertRaises(GenerationError):separate(fixture(change=change))

    def test_out_of_range_indices_and_nonfinite_positions(self):
        with self.assertRaises(GenerationError):separate(fixture(faces=[(0,1,999)]))
        with self.assertRaises(GenerationError):separate(fixture(points=[(float('nan'),0,0)]*6))

    def test_refuses_instanced_or_multi_node_sources(self):
        def change(d):d['nodes'].append({'mesh':0});d['scenes'][0]['nodes'].append(1)
        with self.assertRaises(GenerationError):separate(fixture(change=change))

    def test_duplicate_and_degenerate_faces_preserved(self):
        original=fixture(faces=[(0,1,2),(0,1,2),(0,0,0),(3,4,5)])
        out,r,_=separate(original);_,pts,faces=decode(original)
        self.assertEqual(exported_triangles(out)[1],Counter(tuple(pts[i] for i in f) for f in faces))
        self.assertEqual(r['source_triangles'],4)

    def test_unsigned_short_indices_and_interleaved_offsets(self):
        # Exercise accessor/view byte offsets and strides using a minimal direct GLB.
        data=fixture();n=struct.unpack_from('<I',data,12)[0];doc=json.loads(data[20:20+n]);binary=data[28+n:]
        points=[struct.unpack_from('<3f',binary,i*12) for i in range(6)]
        packed=b'xxxx'+b''.join(struct.pack('<3fI',*p,0) for p in points)+struct.pack('<6H',0,1,2,3,4,5)
        doc['bufferViews']=[{'buffer':0,'byteOffset':4,'byteLength':96,'byteStride':16},{'buffer':0,'byteOffset':100,'byteLength':12}]
        doc['accessors'][1]['componentType']=5123;doc['buffers'][0]['byteLength']=len(packed)
        raw=json.dumps(doc).encode();raw+=b' '*(-len(raw)%4)
        body=struct.pack('<II',len(raw),0x4E4F534A)+raw+struct.pack('<II',len(packed),0x004E4942)+packed
        out,r,_=separate(struct.pack('<III',0x46546C67,2,len(body)+12)+body)
        self.assertEqual(r['index_islands'],2);self.assertEqual(inspect_glb(out)['triangles'],2)


if __name__=='__main__':unittest.main()
