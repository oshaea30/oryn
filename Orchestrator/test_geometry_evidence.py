"""Local geometry evidence and untrusted candidate contracts; no paid calls."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import xml.etree.ElementTree as ET

from app import Jobs, Server
from geometry_evidence import GeometryEvidenceStore, build_evidence, gap, validate_candidates
from ingestion import ingest
from test_mesh_islands import fixture
from test_generation import FakeTransport
from workflow import WorkflowStore


class GeometryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.data=fixture()
        self.source=self.root/'model.glb'; self.source.write_bytes(self.data)
        self.manifest,_=ingest(self.data,{})
        self.targets=[p['id'] for p in self.manifest['geometry_pieces']]
        self.store=GeometryEvidenceStore(WorkflowStore(self.root/'workflow.sqlite3'))

    def queued(self):
        return self.store.enqueue(self.source,self.manifest,self.targets)

    def ready(self):
        identifier=self.queued(); self.store.run_next(); return self.store.get(identifier)

    def test_views_and_measurements_bound_to_source_without_mutation(self):
        original=deepcopy(self.manifest)
        result=build_evidence(self.data,self.manifest,self.targets)
        self.assertEqual(result['component_mappings'],[])
        self.assertFalse(result['outbound_images']);self.assertFalse(result['runtime_changed'])
        self.assertEqual(len(result['measurements']),2)
        self.assertEqual(result['source_node_transform']['translation'],[1,2,3])
        for view in result['views']:
            root=ET.fromstring(view['svg'])
            self.assertEqual(len(root.findall('{http://www.w3.org/2000/svg}text')),16)
            self.assertNotIn('<script',view['svg'])
        self.assertEqual(original,self.manifest)
        self.assertEqual(result,build_evidence(self.data,self.manifest,self.targets))

    def test_all_200_measured_only_eight_get_views(self):
        points=[];faces=[]
        for n in range(200):
            i=len(points);points.extend([(n*3,0,0),(n*3+1,0,0),(n*3,1,0)]);faces.append((i,i+1,i+2))
        data=fixture(points=points,faces=faces);manifest,_=ingest(data,{})
        targets=[p['id'] for p in manifest['geometry_pieces'][:8]]
        result=build_evidence(data,manifest,targets)
        self.assertEqual(len(result['measurements']),200);self.assertEqual(len(result['views']),8)
        self.assertEqual(manifest['runtime']['prepared_targets'],0)

    def test_bad_binding_targets_layout_or_budget_rejected(self):
        for targets in ([],self.targets*5,[self.targets[0]]*2,['unknown']):
            with self.subTest(targets=targets),self.assertRaises(ValueError):
                build_evidence(self.data,self.manifest,targets)
        changed=deepcopy(self.manifest);changed['geometry_pieces'][0]['triangle_indices']=[]
        with self.assertRaises(ValueError):build_evidence(self.data,changed,self.targets)
        with patch('geometry_evidence.MAX_FACES',1),self.assertRaises(ValueError):
            build_evidence(self.data,self.manifest,self.targets)
        self.source.write_bytes(b'changed')
        identifier=self.queued();self.store.run_next()
        self.assertEqual(self.store.get(identifier)['status'],'unavailable')
        self.assertIsNone(self.store.run_next())

    def test_bound_gap_is_not_adjacency(self):
        a={'min':[0,0,0],'max':[1,1,1]};b={'min':[2,3,1],'max':[3,4,2]}
        self.assertAlmostEqual(gap(a,b),5**.5)
        self.assertEqual(gap(a,a),0)

    def test_restart_reuse_and_no_duplicate_work_across_workers(self):
        identifier=self.queued()
        manifest=deepcopy(self.manifest);manifest['provenance']['job_id']='different'
        self.assertEqual(identifier,self.store.enqueue(self.source,manifest,self.targets))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.store.run_next(),range(2)))
        self.assertEqual(sum(r is not None for r in results),1)
        restarted=GeometryEvidenceStore(WorkflowStore(self.root/'workflow.sqlite3'))
        self.assertIsNone(restarted.run_next())
        report=restarted.report(identifier)
        self.assertEqual(report['status'],'ready');self.assertNotIn('source_path',report)
        self.assertNotIn('svg',json.dumps(report));self.assertIn('<svg',restarted.view(identifier,0))
        with self.assertRaises(ValueError):restarted.view(identifier,-1)
        with restarted.workflows.connect() as db:
            db.execute('UPDATE geometry_evidence_views SET svg=? WHERE evidence_id=?',('corrupt',identifier))
        with self.assertRaises(ValueError):restarted.view(identifier,0)

    def test_interrupted_never_replayed(self):
        identifier=self.queued()
        with self.store.workflows.connect() as db:
            db.execute("UPDATE geometry_evidence SET status='running' WHERE id=?",(identifier,))
        self.store.recover_interrupted()
        self.assertEqual(self.store.get(identifier)['status'],'interrupted')
        self.assertIsNone(self.store.run_next())

    def test_storage_budget_stops_without_eviction(self):
        identifier=self.queued()
        with patch('geometry_evidence.MAX_STORED_VIEW_BYTES',1):self.store.run_next()
        self.assertEqual(self.store.get(identifier)['status'],'unavailable')
        self.assertEqual(self.source.read_bytes(),self.data)
        with self.store.workflows.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM geometry_evidence_views').fetchone()[0],0)

    def test_legacy_view_compression_preserves_identity(self):
        package=self.ready();identifier=package['id'];svg=self.store.view(identifier,0)
        with self.store.workflows.connect() as db:
            db.execute('UPDATE geometry_evidence_views SET svg=? WHERE evidence_id=? AND ordinal=0',(svg,identifier))
        restarted=GeometryEvidenceStore(self.store.workflows)
        self.assertEqual(restarted.view(identifier,0),svg)
        self.assertEqual(restarted.get(identifier)['views'],package['views'])

    def test_application_queues_evidence_without_delaying_delivery(self):
        class Provider:
            def __init__(self,key):pass
            def generate_geometry(self,*args):return fixture()
        transport=FakeTransport()
        jobs=Jobs(self.root/'jobs',self.source,key='fixture',provider=Provider,transport=transport)
        jobs.request_object({'request_id':'a'*32,'prompt':'two pieces'})
        for _ in range(200):
            if not jobs.busy:break
            time.sleep(.01)
        self.assertFalse(jobs.busy)
        job=jobs.state()['jobs'][0];stamp=job['updated']
        self.assertEqual(job['status'],'loaded_on_quest');self.assertEqual(job['geometry_evidence']['status'],'queued')
        jobs.geometry_evidence.run_next()
        self.assertEqual(jobs.state()['jobs'][0]['geometry_evidence']['status'],'ready')
        self.assertEqual(jobs.jobs['a'*32]['updated'],stamp)
        self.assertEqual(transport.calls,1)
        restarted=Jobs(jobs.root,self.source,transport=transport)
        self.assertIsNone(restarted.geometry_evidence.run_next())
        self.assertEqual(transport.calls,1)

    def candidate(self, package):
        return {'mappings':[{'geometry_id':self.targets[0],'candidate_name':'Example fixture family',
                'rationale':'Fixture only, not a real identification.','source_ids':['r1'],
                'view_ids':[package['views'][0]['view_id']]}], 'unknown_geometry_ids':self.targets[1:]}

    def test_candidate_revisions_require_real_bindings_and_preserve_unknown(self):
        package=self.ready();identifier=package['id'];result=self.candidate(package)
        sources=[{'id':'r1','content_sha256':'a'*64,'url':'https://example.org/reference'}]
        provenance={'method':'multimodal_model','provider':'fixture','model':'fixture','operation_id':'fixture'}
        record=self.store.save_candidates(identifier,result,sources,provenance)
        self.assertEqual(record['status'],'candidate');self.assertFalse(record['capabilities_promoted'])
        self.assertEqual(record['human_review']['status'],'not_reviewed')
        self.store.save_candidates(identifier,result,sources,provenance)
        self.assertEqual(len(self.store.report(identifier)['candidate_revisions']),1)
        for change in ('confidence','verified','bad_view','bad_source','missing_unknown','extra_geometry','duplicate'):
            invalid=deepcopy(result)
            if change=='confidence':invalid['mappings'][0]['confidence']=.99
            elif change=='verified':invalid['mappings'][0]['status']='verified'
            elif change=='bad_view':invalid['mappings'][0]['view_ids']=[package['views'][1]['view_id']]
            elif change=='bad_source':invalid['mappings'][0]['source_ids']=['unknown']
            elif change=='missing_unknown':invalid['unknown_geometry_ids']=[]
            elif change=='extra_geometry':invalid['unknown_geometry_ids'].append('unknown')
            else:invalid['mappings'].append(deepcopy(invalid['mappings'][0]))
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_candidates(invalid,package,sources,provenance)
        self.assertEqual(self.store.get(identifier)['component_mappings'],[])
        self.assertEqual(self.source.read_bytes(),self.data)

    def test_local_get_routes_do_not_execute_work_or_expose_paths(self):
        jobs=Jobs(self.root/'jobs',self.source)
        identifier=jobs.geometry_evidence.enqueue(self.source,self.manifest,self.targets)
        jobs.geometry_evidence.run_next()
        server=Server(0,jobs);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=server.origin
            response=urllib.request.urlopen(base+'/api/geometry-evidence?id='+identifier)
            record=json.load(response);self.assertNotIn('source_path',record)
            response=urllib.request.urlopen(base+'/api/geometry-view?id='+identifier+'&piece=0')
            self.assertEqual(response.headers['Content-Type'],'image/svg+xml')
            self.assertIn(b'<svg',response.read())
            for query in ('id=../../private','id='+identifier+'&piece=-1','id='+identifier+'&piece=0&extra=1'):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(base+'/api/geometry-view?'+query)
                self.assertEqual(error.exception.code,404)
                error.exception.close()
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
