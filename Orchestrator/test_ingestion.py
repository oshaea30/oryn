import copy
from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest

from ingestion import ingest, prepare_asset, validate_manifest, digest
from mesh_islands import decode
from providers import GenerationError
from test_mesh_islands import fixture, exported_triangles
from test_generation import FakeTransport
from app import Jobs


class IngestionTests(unittest.TestCase):
    def test_lossless_preparation_and_stable_source_ids(self):
        data = fixture()
        manifest, prepared = ingest(data, {'job_id': 'a'*32, 'provider':'fixture'})
        self.assertEqual(manifest['capabilities']['geometric_explosion']['status'], 'supported')
        self.assertEqual(manifest['components'], [])
        self.assertEqual(manifest['component_mappings'], [])
        self.assertTrue(all(p['semantic_status']=='unidentified' for p in manifest['geometry_pieces']))
        doc, points, faces = decode(data)
        out, triangles = exported_triangles(prepared)
        self.assertEqual(Counter(tuple(points[v] for v in f) for f in faces), triangles)
        self.assertEqual(doc['nodes'][0]['translation'], out['nodes'][0]['translation'])
        again, output = ingest(data, {'job_id':'b'*32})
        self.assertEqual(manifest['geometry_pieces'], again['geometry_pieces'])
        self.assertEqual(prepared, output)
        self.assertFalse(manifest['runtime']['headset_verified'])

    def test_two_hundred_pieces_preserved_but_not_flattened_for_runtime(self):
        points, faces = [], []
        for i in range(200):
            n=len(points); points.extend([(i*3,0,0),(i*3+1,0,0),(i*3,1,0)]); faces.append((n,n+1,n+2))
        manifest, prepared = ingest(fixture(points=points,faces=faces), {})
        self.assertIsNone(prepared)
        self.assertEqual(len(manifest['geometry_pieces']), 200)
        self.assertEqual(len(manifest['unresolved_mappings']), 200)
        self.assertEqual(len(manifest['assembly_hierarchy']['geometry_ids']), 200)
        self.assertEqual(manifest['runtime']['prepared_targets'], 0)
        self.assertEqual(manifest['capabilities']['geometric_explosion']['status'], 'unsupported')

    def test_existing_multinode_geometry_is_preserved(self):
        _, prepared = ingest(fixture(), {})
        manifest, second = ingest(prepared, {})
        self.assertIsNone(second)
        self.assertEqual(manifest['runtime']['artifact'], 'source')
        self.assertEqual(manifest['capabilities']['geometric_explosion']['status'], 'supported')

    def test_semantic_mapping_requires_provenance_and_evidence(self):
        manifest,_=ingest(fixture(),{})
        manifest['components']=[{'id':'component-1'}]
        base={'geometry_ids':[manifest['geometry_pieces'][0]['id']], 'component_id':'component-1',
              'status':'candidate','derived_by':{'method':'human_hypothesis'},'evidence':[],
              'human_review':{'status':'not_reviewed'}}
        manifest['component_mappings']=[base]
        validate_manifest(manifest,manifest['asset_id'])
        for change in ({'status':'reference-supported'}, {'status':'verified'}, {'status':'certain'},
                       {'confidence':.94}, {'derived_by':{}}, {'geometry_ids':['unknown']}, {'evidence':['unknown']}):
            changed=copy.deepcopy(manifest); changed['component_mappings'][0].update(change)
            with self.subTest(change=change), self.assertRaises(GenerationError): validate_manifest(changed,changed['asset_id'])

    def test_cached_manifest_and_sources_preserved_and_tamper_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root); data=fixture(); (folder/'model.glb').write_bytes(data)
            manifest, chosen=prepare_asset(folder,'geometry',{})
            path=folder/'geometry.ingestion.json'; original=path.read_bytes()
            self.assertEqual((folder/'model.glb').read_bytes(),data)
            prepare_asset(folder,'geometry',{})
            self.assertEqual(path.read_bytes(),original)
            chosen.write_bytes(data)
            with self.assertRaises(GenerationError): prepare_asset(folder,'geometry',{})
            self.assertEqual(path.read_bytes(),original)

    def test_service_automatically_delivers_manifest_bound_assembly(self):
        class Provider:
            def __init__(self,key): pass
            def generate_geometry(self,*args): return fixture()
        class Transport(FakeTransport):
            def deliver(self,path,job,progress):
                self.name=path.name;self.payload=path.read_bytes()
                super().deliver(path,job,progress)
        import time
        with tempfile.TemporaryDirectory() as root:
            transport=Transport(); jobs=Jobs(Path(root)/'jobs',Path(root)/'unused',key='fixture',provider=Provider,transport=transport)
            jobs.request_object({'request_id':'a'*32,'prompt':'two pieces'})
            for _ in range(200):
                if not jobs.busy: break
                time.sleep(.01)
            self.assertFalse(jobs.busy)
            job=jobs.jobs['a'*32]
            self.assertEqual(transport.name,'geometry.assembly.glb')
            self.assertEqual(job['delivery_asset_sha256'],digest(transport.payload))
            self.assertEqual(job['status'],'loaded_on_quest')
            stamp=job['updated']
            restarted=Jobs(Path(root)/'jobs',Path(root)/'unused',transport=transport)
            self.assertEqual(restarted.jobs['a'*32]['updated'],stamp)
            self.assertEqual(transport.calls,1,'Startup backfill must never deliver')


if __name__=='__main__': unittest.main()
