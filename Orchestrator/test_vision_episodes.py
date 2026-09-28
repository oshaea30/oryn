"""Fixture-only budget/episode/vision tests. Never contact a real provider."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock
from types import SimpleNamespace

from cognition import CommandError
from geometry_evidence import GeometryEvidenceStore
from ingestion import ingest
from investigation import validate_sources
from investigation_episodes import Episodes
from spending import PRICE_REVIEWED, policy
from test_investigation import source, findings
from test_mesh_islands import fixture
from usage_ledger import UsageLedger
from vision_provider import OpenAIMappingProvider, vision_body
from vision_service import VisionService
from workflow import WorkflowStore


class InvestigationBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=PRICE_REVIEWED+7200;self.ledger=UsageLedger(Path(self.tmp.name)/'usage.sqlite3',clock=lambda:self.now)

    def quote(self,op,amount=30_000_000):
        self.ledger.create_quote({'request_id':op,'actor_id':'developer','provider':'openai','profile':'fixture',
            'model':'gpt-6-sol','effort':'medium','operation':'fixture','fingerprint':'fixture',
            'price_version':'fixture','input_tokens':1000,'max_output_tokens':2048,'reserved_nanos':amount,
            'ceiling_nanos':50_000_000,'created':self.now,'expires':self.now+120})

    def test_atomic_object_cap_across_workers(self):
        self.quote('a'*32);self.quote('b'*32)
        def attempt(op):
            try:self.ledger.reserve(op,'developer','fixture',30_000_000,investigation_id='c'*64);return True
            except CommandError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,['a'*32,'b'*32]))
        self.assertEqual(sum(results),1)
        self.assertEqual(self.ledger.investigation_summary('c'*64)['remaining_nanos'],20_000_000)

    def test_old_text_charge_and_uncertainty_survive_day_and_restart(self):
        self.quote('a'*32,10_000_000);self.ledger.reserve('a'*32,'developer','fixture',10_000_000)
        self.ledger.settle('a'*32,100,100,6_000_000,'completed')
        self.ledger.bind_investigation('a'*32,'c'*64)
        self.now+=86400;self.ledger=UsageLedger(self.ledger.path,clock=lambda:self.now)
        self.quote('b'*32,45_000_000)
        with self.assertRaises(CommandError):self.ledger.reserve('b'*32,'developer','fixture',45_000_000,investigation_id='c'*64)
        self.quote('d'*32,30_000_000);self.ledger.reserve('d'*32,'developer','fixture',30_000_000,investigation_id='c'*64)
        self.ledger.uncertain('d'*32);self.now+=86400
        self.assertEqual(self.ledger.investigation_summary('c'*64)['charged_and_reserved_nanos'],36_000_000)
        with self.assertRaises(CommandError):self.ledger.bind_investigation('a'*32,'e'*64)
        self.assertEqual(self.ledger.summary()['charged_and_reserved_nanos'],30_000_000)


class VisionEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);root=Path(self.tmp.name)
        self.store=WorkflowStore(root/'workflow.sqlite3');self.geometry=GeometryEvidenceStore(self.store)
        self.data=fixture();self.manifest,_=ingest(self.data,{})
        path=root/'model.glb';path.write_bytes(self.data)
        self.targets=[p['id'] for p in self.manifest['geometry_pieces']]
        identifier=self.geometry.enqueue(path,self.manifest,self.targets);self.geometry.run_next();self.package=self.geometry.get(identifier)
        self.episodes=Episodes(self.store)
        self.sources=validate_sources([source()])
        self.research={'id':'b'*64,'asset_id':self.manifest['asset_id'],'status':'reference_notes_ready','query':'V8 engine',
            'sources':self.sources,'selected_source_ids':['ref1'],'findings':findings(),
            'stages':{'synthesis':{'operation_id':'c'*32}}}
        self.episode=self.episodes.ensure(self.package,self.research)
        # Deliberately synthetic raster header, only ever given to mocked HTTP.
        png=b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',1000,540)+b'\0'*9
        self.images=[{'png':png,'png_sha256':hashlib.sha256(png).hexdigest(),'geometry_id':v['geometry_id'],
            'view_id':v['view_id'],'renderer':'fixture','width':1000,'height':540} for v in self.package['views']]
        self.now=PRICE_REVIEWED+7200;self.ledger=UsageLedger(root/'usage.sqlite3',clock=lambda:self.now)
        self.counter=Mock(return_value=1000);self.sender=Mock(side_effect=self.response)
        self.provider=OpenAIMappingProvider(self.ledger,'PRIVATE_FIXTURE',self.counter,self.sender,clock=lambda:self.now)

    def output(self):
        return {'mappings':[{'geometry_id':'p1','candidate_name':'Crankshaft candidate','rationale':'Fixture-only hypothesis, not an actual identification.',
            'source_ids':['ref1'],'view_ids':['v1']}],'unknown_geometry_ids':['p2']}

    def response(self,*args):
        return {'id':'response-fixture','status':'completed','model':'gpt-6-sol','service_tier':'default',
            'usage':{'input_tokens':1000,'output_tokens':200},
            'output':[{'type':'reasoning','encrypted_content':'DO_NOT_STORE_REASONING'},
                      {'type':'message','content':[{'type':'output_text','text':json.dumps(self.output())}]}]}

    def event(self,kind,payload):self.episodes.append(self.episode['id'],kind,kind,payload)

    def run_provider(self):
        return self.provider.propose_mappings(self.episode,self.package,self.sources,self.images,self.event)

    def publish(self):
        result,refs,provenance=self.run_provider()
        revision=self.geometry.save_candidates(self.package['id'],result,refs,provenance)
        self.episodes.append(self.episode['id'],'candidates_persisted','candidates_persisted',{'mappings':revision['mappings']})
        self.episodes.finish(self.episode['id'],'completed',candidate_revision_id=revision['id'])
        return revision

    def test_payload_only_object_rasters_and_bounded_evidence(self):
        body,aliases,views,sources=vision_body(policy('openai','vision',self.now),'V8',self.package,self.sources,self.images)
        self.assertFalse(body['store']);self.assertEqual(body['max_output_tokens'],2048)
        self.assertNotIn('tools',body);self.assertNotIn('previous_response_id',body)
        images=[i for i in body['input'][1]['content'] if i['type']=='input_image']
        self.assertEqual(len(images),2);self.assertTrue(all(i['image_url'].startswith('data:image/png;base64,') for i in images))
        self.assertEqual(aliases['p1'],self.targets[0]);self.assertEqual(views['v1'],self.package['views'][0]['view_id'])
        changed=deepcopy(self.images);changed[0]['png_sha256']='bad'
        with self.assertRaises(ValueError):vision_body(policy('openai','vision',self.now),'V8',self.package,self.sources,changed)

    def test_exact_local_rasters_retained_once_without_egress(self):
        self.episodes.retain_observations(self.episode['id'],self.package,self.images)
        self.episodes.retain_observations(self.episode['id'],self.package,self.images)
        self.assertEqual(self.episodes.image(self.episode['id'],0),self.images[0]['png'])
        self.assertEqual(len([e for e in self.episodes.events(self.episode['id']) if e['kind']=='observations_prepared']),1)
        changed=deepcopy(self.images);changed[0]['view_id']='bad'
        with self.assertRaises(ValueError):self.episodes.retain_observations(self.episode['id'],self.package,changed)
        self.sender.assert_not_called();self.counter.assert_not_called()

    def test_local_render_action_reuses_retained_inputs(self):
        renderer=Mock(return_value=self.images)
        first=self.episodes.prepare_local(self.episode['id'],self.geometry,renderer)
        second=self.episodes.prepare_local(self.episode['id'],self.geometry,renderer)
        self.assertFalse(first['reused']);self.assertTrue(second['reused']);renderer.assert_called_once()
        self.sender.assert_not_called();self.counter.assert_not_called()

    def test_local_http_evidence_reads_and_review_auth_boundary(self):
        from app import Jobs, Server
        self.episodes.retain_observations(self.episode['id'],self.package,self.images)
        jobs=Jobs(Path(self.tmp.name)/'jobs',Path(self.tmp.name)/'model.glb')
        jobs.episodes=self.episodes;jobs.geometry_evidence=self.geometry
        server=Server(0,jobs);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=server.origin+'/api/episode?id='+self.episode['id']
            with urllib.request.urlopen(url) as response:record=json.load(response)
            self.assertEqual(record['status'],'waiting_policy')
            with urllib.request.urlopen(server.origin+'/api/episode-image?id='+self.episode['id']+'&piece=0') as response:
                self.assertEqual(response.headers['Content-Type'],'image/png');self.assertEqual(response.read(),self.images[0]['png'])
            request=urllib.request.Request(server.origin+'/api/episode-review',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
            self.assertEqual(error.exception.code,403);error.exception.close()
            for tail in ('&piece=-1','&piece=0&extra=1'):
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(server.origin+'/api/episode-image?id='+self.episode['id']+tail)
                self.assertEqual(error.exception.code,404);error.exception.close()
        finally:server.shutdown();server.server_close();thread.join()
        self.sender.assert_not_called();self.counter.assert_not_called()

    def test_paid_fixture_is_admitted_then_observable_history_retained(self):
        def send(*args):
            self.assertEqual(self.ledger.get(self.episode['operation_id'])['status'],'reserved')
            return self.response()
        self.sender.side_effect=send
        result,refs,provenance=self.run_provider()
        self.assertEqual(result['mappings'][0]['geometry_id'],self.targets[0])
        events=json.dumps(self.episodes.events(self.episode['id']))
        self.assertIn('provider_response',events);self.assertIn('validation_passed',events)
        self.assertNotIn('DO_NOT_STORE_REASONING',events);self.assertNotIn('PRIVATE_FIXTURE',events)
        self.assertNotIn('data:image/png',events)
        self.assertEqual(self.ledger.investigation_summary(self.manifest['asset_id'])['charged_and_reserved_nanos'],4_500_000)
        with self.assertRaises(CommandError):self.run_provider()
        self.sender.assert_called_once();self.counter.assert_called_once()

    def test_invalid_provider_output_is_preserved_but_not_published(self):
        output=self.output();output['mappings'][0]['status']='verified'
        response=self.response();response['output'][1]['content'][0]['text']=json.dumps(output)
        self.sender.side_effect=None;self.sender.return_value=response
        with self.assertRaises(CommandError):self.run_provider()
        events=self.episodes.events(self.episode['id'])
        self.assertIn('provider_response',[e['kind'] for e in events]);self.assertIn('validation_rejected',[e['kind'] for e in events])
        self.assertEqual(self.geometry.report(self.package['id'])['candidate_revisions'],[])
        self.assertEqual(self.ledger.get(self.episode['operation_id'])['outcome'],'invalid_response')

    def test_timeout_reservation_survives_and_no_retry(self):
        self.sender.side_effect=TimeoutError('PRIVATE_FIXTURE')
        with self.assertRaises(CommandError):self.run_provider()
        self.assertEqual(self.ledger.get(self.episode['operation_id'])['status'],'uncertain')
        with self.assertRaises(CommandError):self.run_provider()
        self.sender.assert_called_once()

    def test_cumulative_budget_blocks_second_stage_before_generation(self):
        op='d'*32;amount=40_000_000
        self.ledger.create_quote({'request_id':op,'actor_id':'developer','provider':'openai','profile':'fixture',
            'model':'gpt-6-sol','effort':'medium','operation':'fixture','fingerprint':'fixture','price_version':'fixture',
            'input_tokens':1000,'max_output_tokens':2048,'reserved_nanos':amount,'ceiling_nanos':50_000_000,
            'created':self.now,'expires':self.now+120})
        self.ledger.reserve(op,'developer','fixture',amount,investigation_id=self.manifest['asset_id'])
        with self.assertRaises(CommandError):self.run_provider()
        self.sender.assert_not_called()

    def test_rejections_corrections_and_stale_review_conflicts_are_append_only(self):
        revision=self.publish();before=deepcopy(revision)
        body={'request_id':'a'*32,'revision_id':revision['id'],'geometry_id':self.targets[0],
            'decision':'rejected','reason':'Geometry/reference mismatch.','replacement_name':'','source_ids':['ref1'],'previous_review_id':None}
        first=self.episodes.review(self.episode['id'],body,self.geometry)
        self.assertEqual(first,self.episodes.review(self.episode['id'],body,self.geometry))
        correction={**body,'request_id':'b'*32,'decision':'corrected','replacement_name':'Rocker arm','previous_review_id':first}
        second=self.episodes.review(self.episode['id'],correction,self.geometry)
        self.assertNotEqual(first,second)
        with self.assertRaises(ValueError):self.episodes.review(self.episode['id'],{**correction,'request_id':'c'*32},self.geometry)
        with self.assertRaises(ValueError):self.episodes.review(self.episode['id'],{**body,'decision':'verified'},self.geometry)
        self.assertEqual(self.geometry.report(self.package['id'])['candidate_revisions'][0],before)
        reviews=[e for e in self.episodes.events(self.episode['id']) if e['kind']=='human_review']
        self.assertEqual(len(reviews),2);self.assertEqual(reviews[1]['payload']['replacement_candidate']['status'],'candidate')

    def test_claims_policy_and_recovery_do_not_execute_providers(self):
        self.assertFalse(self.episodes.policy_ready('a'*64))
        with self.assertRaises(ValueError):self.episodes.configure_policy('a'*64,{'object_only_vision':True,'sharing_disabled':False,'accept_budget':True})
        self.episodes.configure_policy('a'*64,{'object_only_vision':True,'sharing_disabled':True,'accept_budget':True})
        self.assertTrue(self.episodes.policy_ready('a'*64));self.assertFalse(self.episodes.policy_ready('b'*64))
        first=self.episodes.claim(self.episode['id']);self.assertEqual(first['status'],'running')
        self.assertIsNone(self.episodes.claim(self.episode['id']))
        self.episodes.recover();self.assertEqual(self.episodes.get(self.episode['id'])['status'],'interrupted')
        self.assertIsNone(self.episodes.claim(self.episode['id']));self.sender.assert_not_called();self.counter.assert_not_called()

    def service(self):
        research=SimpleNamespace(key='PRIVATE_FIXTURE',budget_error='',ledger=self.ledger,lock=threading.Lock())
        jobs=SimpleNamespace(research=research,episodes=self.episodes,geometry_evidence=self.geometry)
        return VisionService(jobs,provider_factory=lambda ledger,key:self.provider)

    def authorize(self,service):
        service.configure_policy({'object_only_vision':True,'sharing_disabled':True,'accept_budget':True})

    def test_service_never_dispatches_without_policy_or_local_observations(self):
        service=self.service()
        with self.assertRaises(ValueError):service.start_episode(self.episode['id'])
        self.authorize(service)
        with self.assertRaises(ValueError):service.start_episode(self.episode['id'])
        self.episodes.retain_observations(self.episode['id'],self.package,self.images)
        service.jobs.research.key='CHANGED_FIXTURE'
        self.assertFalse(service.state()['policy_ready'])
        with self.assertRaises(ValueError):service.start_episode(self.episode['id'])
        self.counter.assert_not_called();self.sender.assert_not_called()

    def test_service_duplicate_dispatch_and_restart_do_not_replay(self):
        service=self.service();self.authorize(service)
        self.episodes.retain_observations(self.episode['id'],self.package,self.images)
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies=list(pool.map(lambda _:service.start_episode(self.episode['id']),range(2)))
        self.assertEqual(sum(r['dispatched'] for r in replies),1)
        service.thread.join(5);self.assertFalse(service.thread.is_alive())
        record=self.episodes.get(self.episode['id'])
        self.assertEqual(record['status'],'completed');self.assertIsNotNone(record['candidate_revision_id'])
        self.assertIn('latency_ms',record)
        restarted=self.service()
        self.assertFalse(restarted.start_episode(record['id'])['dispatched'])
        self.sender.assert_called_once();self.counter.assert_called_once()
        self.assertEqual(self.geometry.get(self.package['id'])['component_mappings'],[])

    def test_service_failure_preserves_uncertainty_and_never_retries(self):
        service=self.service();self.authorize(service)
        self.episodes.retain_observations(self.episode['id'],self.package,self.images)
        self.sender.side_effect=TimeoutError('PRIVATE_FIXTURE')
        service.start_episode(self.episode['id']);service.thread.join(5)
        record=self.episodes.get(self.episode['id'])
        self.assertEqual(record['status'],'failed');self.assertNotIn('PRIVATE_FIXTURE',record['error'])
        self.assertEqual(self.ledger.get(record['operation_id'])['status'],'uncertain')
        self.assertFalse(service.start_episode(record['id'])['dispatched'])
        self.sender.assert_called_once()

    def test_service_preserves_unexamined_targets_as_unknown(self):
        points=[];faces=[]
        for n in range(8):
            i=len(points);points.extend([(n*3,0,0),(n*3+1,0,0),(n*3,1,0)]);faces.append((i,i+1,i+2))
        data=fixture(points=points,faces=faces);manifest,_=ingest(data,{})
        path=Path(self.tmp.name)/'eight.glb';path.write_bytes(data)
        targets=[p['id'] for p in manifest['geometry_pieces']]
        identifier=self.geometry.enqueue(path,manifest,targets);self.geometry.run_next()
        package=self.geometry.get(identifier)
        episode=self.episodes.ensure(package,{**self.research,'asset_id':manifest['asset_id']})
        images=[{**self.images[0],'geometry_id':v['geometry_id'],'view_id':v['view_id']} for v in package['views'][:3]]
        self.episodes.retain_observations(episode['id'],package,images)
        response=self.response()
        output=self.output();output['unknown_geometry_ids']=['p2','p3']
        response['output'][1]['content'][0]['text']=json.dumps(output)
        self.sender.side_effect=None;self.sender.return_value=response
        service=self.service();self.authorize(service)
        service.start_episode(episode['id']);service.thread.join(5)
        self.assertEqual(self.episodes.get(episode['id'])['status'],'completed')
        revision=self.geometry.report(identifier)['candidate_revisions'][0]
        self.assertEqual(set(revision['unknown_geometry_ids']),set(targets[1:]))
        self.assertEqual(len(revision['mappings']),1)
        published=next(e for e in self.episodes.events(episode['id']) if e['kind']=='candidates_persisted')
        self.assertEqual(published['payload']['not_examined_geometry_ids'],targets[3:])

    def test_http_policy_and_dispatch_require_local_auth_and_use_saved_episode(self):
        from app import Jobs, Server
        jobs=Jobs(Path(self.tmp.name)/'http-jobs',Path(self.tmp.name)/'model.glb')
        jobs.episodes=self.episodes;jobs.geometry_evidence=self.geometry;jobs.vision=self.service()
        self.episodes.retain_observations(self.episode['id'],self.package,self.images)
        server=Server(0,jobs);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            confirmation={'object_only_vision':True,'sharing_disabled':True,'accept_budget':True}
            def post(path,body,token='',origin=None):
                return urllib.request.urlopen(urllib.request.Request(server.origin+path,data=json.dumps(body).encode(),
                    headers={'Content-Type':'application/json','Origin':origin or server.origin,'X-Oryn-Token':token},method='POST'))
            for route,body in (('/api/vision-policy',confirmation),('/api/investigate-episode',{'episode_id':self.episode['id']})):
                for token,origin in (('',None),(server.token,'https://untrusted.invalid')):
                    with self.assertRaises(urllib.error.HTTPError) as error:post(route,body,token,origin)
                    self.assertEqual(error.exception.code,403);error.exception.close()
            self.sender.assert_not_called()
            with post('/api/vision-policy',confirmation,server.token) as r:self.assertTrue(json.load(r)['policy_ready'])
            with post('/api/investigate-episode',{'episode_id':self.episode['id']},server.token) as r:
                self.assertEqual(r.status,202);self.assertTrue(json.load(r)['dispatched'])
            jobs.vision.thread.join(5)
            with post('/api/investigate-episode',{'episode_id':self.episode['id']},server.token) as r:self.assertFalse(json.load(r)['dispatched'])
            self.sender.assert_called_once()
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
