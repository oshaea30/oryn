import io
import json
from pathlib import Path
import struct
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import Mock

from app import Jobs, Server
from asset_inspection import inspect_glb
from providers import GenerationError, MAX_BYTES, MeshyProvider, validate_glb
from transport import AdbTransport, DeliveryError


def make_glb(change=None, binary=None):
    binary = binary if binary is not None else struct.pack('<9f', 0,0,0, 1,0,0, 0,1,0)
    doc = {'asset':{'version':'2.0'}, 'scene':0, 'scenes':[{'name':'Test scene','nodes':[0]}],
        'nodes':[{'name':'Object_01','mesh':0}], 'meshes':[{'primitives':[{'attributes':{'POSITION':0}}]}],
        'accessors':[{'bufferView':0,'componentType':5126,'count':3,'type':'VEC3'}],
        'bufferViews':[{'buffer':0,'byteLength':len(binary)}], 'buffers':[{'byteLength':len(binary)}]}
    if change: change(doc)
    raw = json.dumps(doc).encode(); raw += b' ' * (-len(raw) % 4)
    binary += bytes(-len(binary) % 4)
    chunks = struct.pack('<II',len(raw),0x4E4F534A)+raw+struct.pack('<II',len(binary),0x004E4942)+binary
    return struct.pack('<III',0x46546C67,2,12+len(chunks))+chunks


GLB = make_glb()


class Opener:
    def __init__(self, replies): self.replies, self.requests = list(replies), []
    def open(self, request, timeout):
        self.requests.append(request)
        value = self.replies.pop(0)
        if isinstance(value, Exception): raise value
        return io.BytesIO(value if isinstance(value, bytes) else json.dumps(value).encode())


class FakeTransport:
    def __init__(self): self.calls = 0
    def deliver(self, path, job, progress):
        validate_glb(Path(path).read_bytes())
        self.calls += 1
        progress('loaded_on_quest', 100)


class FakeProvider:
    calls = 0
    texture_calls = 0
    def __init__(self, key): self.key = key
    def generate_geometry(self, prompt, profile, progress, task_created):
        type(self).calls += 1
        task_created('preview_task_id', 'preview-saved')
        progress('generating_geometry', 50)
        return GLB
    def texture(self, task_id, profile, progress, task_created):
        type(self).texture_calls += 1
        task_created('refine_task_id', 'refine-saved')
        return GLB
    def balance(self): return 1000


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = self.root / 'fixture.glb'; self.fixture.write_bytes(GLB)
        FakeProvider.calls = 0
        FakeProvider.texture_calls = 0
        self.transport = FakeTransport()
        self.jobs = Jobs(self.root / 'jobs', self.fixture, provider=FakeProvider, transport=self.transport)
        self.body = {'request_id': 'a' * 32, 'mode': 'meshy', 'profile':'structure',
            'prompt': 'a quadcopter drone', 'approve_paid': True, 'approved_credits':5}

    def tearDown(self):
        self.wait()
        self.temp.cleanup()

    def wait(self):
        for _ in range(200):
            if not self.jobs.busy: return
            time.sleep(.005)
        self.fail('Worker did not finish')

    def test_missing_key_blocks_paid_job(self):
        with self.assertRaises(ValueError): self.jobs.submit(self.body)
        self.assertEqual(FakeProvider.calls, 0)

    def test_explicit_cost_approval_required(self):
        self.jobs.key = 'secret'
        self.body['approve_paid'] = False
        with self.assertRaises(ValueError): self.jobs.submit(self.body)
        self.assertEqual(FakeProvider.calls, 0)

    def test_demo_is_labeled_and_never_calls_provider(self):
        self.body['mode'] = 'demo'
        self.jobs.submit(self.body); self.wait()
        job = self.jobs.state()['jobs'][0]
        self.assertTrue(job['demo']); self.assertIn('not AI-generated', job['prompt'])
        self.assertEqual(FakeProvider.calls, 0); self.assertEqual(job['status'], 'loaded_on_quest')

    def test_idempotent_submission_and_key_not_saved(self):
        self.jobs.key = 'VERY_SECRET_KEY'
        self.jobs.submit(self.body); self.wait(); self.jobs.submit(self.body); self.wait()
        self.assertEqual(FakeProvider.calls, 1)
        self.assertNotIn(self.jobs.key, json.dumps(self.jobs.state()))
        text = (self.root / 'jobs' / ('a'*32) / 'job.json').read_text()
        self.assertNotIn(self.jobs.key, text); self.assertIn('preview-saved', text)

    def test_saved_model_redelivery_never_regenerates(self):
        self.jobs.key = 'secret'; self.jobs.submit(self.body); self.wait()
        self.jobs.redeliver('a'*32); self.wait()
        self.assertEqual(FakeProvider.calls, 1); self.assertEqual(self.transport.calls, 1)

    def test_delivery_failure_preserves_generated_file(self):
        self.jobs.key = 'secret'
        self.transport.deliver = Mock(side_effect=DeliveryError('No Quest'))
        self.jobs.submit(self.body); self.wait()
        self.jobs.redeliver('a'*32); self.wait()
        self.assertEqual(self.jobs.state()['jobs'][0]['status'], 'delivery_failed')
        self.assertTrue((self.root / 'jobs' / ('a'*32) / 'model.glb').exists())

    def test_restart_does_not_resubmit_billed_task(self):
        self.jobs.key = 'secret'; self.jobs.submit(self.body); self.wait()
        self.jobs.update('a'*32, status='submitting_texture')
        restarted = Jobs(self.root / 'jobs', self.fixture, provider=FakeProvider, transport=self.transport)
        self.assertEqual(restarted.state()['jobs'][0]['status'], 'interrupted')
        self.assertEqual(FakeProvider.calls, 1)

    def test_prompt_and_id_validation(self):
        self.jobs.key = 'secret'
        for change in ({'prompt': ''}, {'prompt': 'x'*801}, {'request_id': '../bad'}, {'mode': 'unknown'}):
            with self.subTest(change=change), self.assertRaises(ValueError): self.jobs.submit(dict(self.body, **change))

    def test_glb_header_and_size_validation(self):
        validate_glb(GLB)
        for value in (b'', b'bad'*10, GLB[:-1], GLB + bytes(MAX_BYTES)):
            with self.assertRaises(GenerationError): validate_glb(value)

    def test_provider_geometry_does_not_refine_and_isolates_key(self):
        opener = Opener([{'result':'preview-1'}, {'status':'PENDING','progress':0},
            {'status':'SUCCEEDED','model_urls':{'glb':'https://assets.meshy.ai/model.glb'}}, GLB])
        progress, ids = [], {}
        data = MeshyProvider('secret', opener=opener, sleep=lambda _: None).generate_geometry('drone', 'structure',
            lambda phase, n: progress.append(phase), lambda name, value: ids.update({name:value}))
        self.assertEqual(data, GLB); self.assertNotIn('refine_task_id', ids)
        posts = [json.loads(r.data) for r in opener.requests if r.data]
        self.assertEqual([p['mode'] for p in posts], ['preview'])
        self.assertEqual(posts[0]['target_polycount'], 10000)
        self.assertEqual(posts[0]['ai_model'], 'meshy-t2')
        self.assertEqual(posts[0]['model_type'], 'smart-topology')
        self.assertNotIn('should_remesh', posts[0])
        self.assertIsNone(opener.requests[-1].get_header('Authorization'))

    def test_paid_post_timeout_never_retries(self):
        opener = Opener([TimeoutError()])
        with self.assertRaises(GenerationError): MeshyProvider('secret', opener=opener).generate_geometry('drone', 'structure', lambda *a: None, lambda *a: None)
        self.assertEqual(len(opener.requests), 1)

    def test_provider_failure_does_not_refine(self):
        opener = Opener([{'result':'preview-1'}, {'status':'FAILED'}])
        with self.assertRaises(GenerationError): MeshyProvider('secret', opener=opener).generate_geometry('drone', 'structure', lambda *a: None, lambda *a: None)
        self.assertEqual(len(opener.requests), 2)

    def test_asset_url_restrictions(self):
        opener = Opener([]); provider = MeshyProvider('secret', opener=opener)
        for url in ('http://assets.meshy.ai/a', 'https://evil.test/a', 'file:///etc/passwd', 'https://secret@assets.meshy.ai/a', 'https://assets.meshy.ai:8443/a'):
            with self.subTest(url=url), self.assertRaises(GenerationError): provider.download(url)
        self.assertEqual(opener.requests, [])

    def test_auth_and_credit_errors_are_redacted(self):
        for status in (401,402,429,500):
            opener = Opener([urllib.error.HTTPError('url',status,'key=secret',{},None)])
            with self.assertRaises(GenerationError) as caught: MeshyProvider('secret', opener=opener).request({})
            self.assertNotIn('key=secret', str(caught.exception))

    def test_transport_publishes_manifest_last_and_waits_for_ack(self):
        commands = []
        def run(args, **kw):
            commands.append(args)
            if args[-1] == 'devices': output='List of devices attached\nquest\tdevice\n'
            elif 'cat' in args:
                delivery = Path(args[-1]).stem
                output=json.dumps({'id':delivery,'status':'loaded'})
            else: output='ok'
            return Mock(returncode=0, stdout=output)
        folder = self.root / 'transport'; folder.mkdir(); model=folder/'model.glb'; model.write_bytes(GLB)
        states=[]
        AdbTransport(run=run,sleep=lambda _:None).deliver(model, {'id':'a'*32,'demo':True}, lambda s,n,**kw:states.append(s))
        moves=[c for c in commands if 'mv' in c]
        self.assertTrue(moves[0][-1].endswith('.glb')); self.assertTrue(moves[1][-1].endswith('.json'))
        self.assertEqual(states[-1], 'loaded_on_quest')

    def test_transport_rejects_missing_or_multiple_devices(self):
        for devices in ('', 'a\tdevice\nb\tdevice\n', 'a\tunauthorized\n'):
            run=Mock(return_value=Mock(returncode=0,stdout='List of devices attached\n'+devices))
            with self.assertRaises(DeliveryError): AdbTransport(run=run).deliver(self.fixture, {'id':'a'*32,'demo':True}, lambda *a:None)

    def test_http_csrf_host_and_key_redaction(self):
        server=Server(0,self.jobs); thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            origin=server.origin
            with urllib.request.urlopen(origin+'/api/state') as response: state=json.load(response)
            for headers in ({}, {'X-Oryn-Token':state['token'],'Origin':'https://evil.test'}):
                req=urllib.request.Request(origin+'/api/key',data=b'{"key":"secret-long-key"}',headers=dict({'Content-Type':'application/json'},**headers))
                with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(req)
                self.assertEqual(caught.exception.code,403)
                caught.exception.close()
            req=urllib.request.Request(origin+'/api/key',data=b'{"key":"secret-long-key"}',headers={'Content-Type':'application/json','X-Oryn-Token':state['token']})
            with urllib.request.urlopen(req) as response: self.assertNotIn('secret',response.read().decode())
            self.assertTrue(self.jobs.state()['configured'])
            req=urllib.request.Request(origin+'/api/state',headers={'Host':'evil.test'})
            with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(req)
            caught.exception.close()
        finally:
            server.shutdown();server.server_close();thread.join()

    def quality_job(self):
        self.jobs.key = 'secret'
        self.jobs.submit(dict(self.body, profile='quality', approved_credits=20)); self.wait()
        return {'id':'a'*32,'request_id':'b'*32,'approve_paid':True,'approved_credits':10}

    def test_paid_geometry_stops_at_inspection(self):
        self.jobs.key = 'secret'; self.jobs.submit(self.body); self.wait()
        job = self.jobs.state()['jobs'][0]
        self.assertEqual(job['status'],'ready'); self.assertEqual(self.transport.calls,0)
        self.assertEqual(FakeProvider.texture_calls,0)
        self.assertEqual(job['variants']['geometry']['preflight'],'PASS')

    def test_profile_credit_approval_must_match(self):
        self.jobs.key = 'secret'
        for changed in ({'profile':'quality'}, {'approved_credits':30}, {'profile':'unknown'}):
            with self.assertRaises(ValueError): self.jobs.submit(dict(self.body, **changed))
        self.assertEqual(FakeProvider.calls,0)

    def test_texture_is_separate_idempotent_and_preserves_geometry(self):
        body = self.quality_job()
        path = self.root / 'jobs' / ('a'*32) / 'model.glb'
        original = path.read_bytes()
        self.jobs.texture(body); self.wait(); self.jobs.texture(body); self.wait()
        job = self.jobs.state()['jobs'][0]
        self.assertEqual(FakeProvider.calls,1); self.assertEqual(FakeProvider.texture_calls,1)
        self.assertEqual(self.transport.calls,0); self.assertEqual(path.read_bytes(),original)
        self.assertEqual(set(job['variants']), {'geometry','textured'})
        self.jobs.redeliver('a'*32,'textured'); self.wait()
        self.assertEqual(self.transport.calls,1)
        restarted = Jobs(self.root/'jobs',self.fixture,key='secret',provider=FakeProvider,transport=self.transport)
        restarted.texture(body)
        self.assertEqual(FakeProvider.texture_calls,1)
        with self.assertRaises(ValueError): restarted.texture(dict(body,request_id='c'*32))

    def test_texture_requires_own_approval(self):
        body = self.quality_job()
        for changed in ({'approve_paid':False}, {'approved_credits':5}, {'request_id':'../bad'}):
            with self.assertRaises(ValueError): self.jobs.texture(dict(body, **changed))
        self.assertEqual(FakeProvider.texture_calls,0)

    def test_structure_texture_blocked_before_paid_call(self):
        self.jobs.key='secret';self.jobs.submit(self.body);self.wait()
        with self.assertRaises(ValueError): self.jobs.texture({'id':'a'*32,'request_id':'b'*32,'approve_paid':True,'approved_credits':10})
        self.assertEqual(FakeProvider.texture_calls,0)
        opener=Opener([])
        with self.assertRaises(GenerationError): MeshyProvider('secret',opener=opener).texture('preview','structure',lambda *a:None,lambda *a:None)
        self.assertEqual(opener.requests,[])

    def test_failed_texture_keeps_geometry_and_blocks_paid_retry(self):
        body = self.quality_job()
        class Failing(FakeProvider):
            def texture(self,*args): raise GenerationError('Texture failed')
        self.jobs.provider=Failing;self.jobs.texture(body);self.wait()
        self.assertEqual(self.jobs.state()['jobs'][0]['status'],'texture_failed')
        self.jobs.redeliver('a'*32);self.wait();self.assertEqual(self.transport.calls,1)
        with self.assertRaises(ValueError): self.jobs.texture(dict(body,request_id='c'*32))

    def test_quality_and_texture_payloads(self):
        result={'status':'SUCCEEDED','model_urls':{'glb':'https://assets.meshy.ai/model.glb'}}
        opener=Opener([{'result':'preview-1'},result,GLB,{'result':'refine-1'},result,GLB])
        provider=MeshyProvider('secret',opener=opener)
        provider.generate_geometry('drone','quality',lambda *a:None,lambda *a:None)
        self.assertEqual(len(opener.requests),3)
        provider.texture('preview-1','quality',lambda *a:None,lambda *a:None)
        posts=[json.loads(r.data) for r in opener.requests if r.data]
        self.assertEqual(posts[0]['ai_model'],'meshy-7.1');self.assertTrue(posts[0]['should_remesh'])
        self.assertEqual(posts[1]['mode'],'refine');self.assertEqual(posts[1]['preview_task_id'],'preview-1')
        self.assertEqual(posts[1]['texture_resolution'],'2k');self.assertFalse(posts[1]['enable_pbr'])
        self.assertIsNone(opener.requests[-1].get_header('Authorization'))

    def test_balance_is_read_only_and_numeric(self):
        opener=Opener([{'balance':1000}]);p=MeshyProvider('secret',opener=opener)
        self.assertEqual(p.balance(),1000)
        self.assertEqual(opener.requests[0].get_method(),'GET')
        self.assertEqual(opener.requests[0].full_url,'https://api.meshy.ai/openapi/v1/balance')
        for value in ('1000',-1,True,float('nan')):
            with self.assertRaises(GenerationError): MeshyProvider('secret',opener=Opener([{'balance':value}])).balance()

    def test_changed_file_is_not_delivered(self):
        self.jobs.key='secret';self.jobs.submit(self.body);self.wait()
        path=self.root/'jobs'/('a'*32)/'model.glb'
        path.write_bytes(make_glb(lambda d:d['nodes'][0].update(name='changed')))
        with self.assertRaises(ValueError): self.jobs.redeliver('a'*32)
        self.assertEqual(self.transport.calls,0)

    def test_failed_preflight_retains_inspection_but_blocks_delivery(self):
        bad=make_glb(lambda d:d['buffers'][0].update(uri='https://example.test/data'))
        self.fixture.write_bytes(bad);self.jobs.submit(dict(self.body,mode='demo'));self.wait()
        job=self.jobs.state()['jobs'][0]
        self.assertEqual(job['variants']['geometry']['preflight'],'FAIL')
        self.assertEqual(job['status'],'delivery_failed');self.assertEqual(self.transport.calls,0)


class InspectionTests(unittest.TestCase):
    def test_single_mesh_report(self):
        report=inspect_glb(GLB)
        self.assertEqual(report['preflight'],'PASS');self.assertEqual(report['triangles'],1)
        self.assertEqual(report['mesh_objects'],1);self.assertEqual(report['vertices_upper_bound'],3)
        self.assertEqual(report['textures'],0);self.assertEqual(report['hierarchy'][0]['name'],'Object_01')

    def test_mesh_instances_are_not_unique_meshes(self):
        def change(d):
            d['nodes']=[{'name':'Drone','children':[1,2]},{'mesh':0},{'mesh':0}]
        r=inspect_glb(make_glb(change))
        self.assertEqual(r['mesh_objects'],2);self.assertEqual(r['unique_meshes'],1)
        self.assertEqual(r['triangles'],2);self.assertEqual(r['vertices_upper_bound'],6)
        self.assertEqual([n['depth'] for n in r['hierarchy']],[0,1,1])
        self.assertEqual([n['parent_index'] for n in r['hierarchy']],[None,0,0])

    def test_unused_meshes_and_other_scenes_not_counted(self):
        def change(d):
            d['meshes'].append(d['meshes'][0]);d['nodes'].append({'mesh':1})
            d['scenes'].append({'nodes':[1]})
        r=inspect_glb(make_glb(change));self.assertEqual(r['mesh_objects'],1);self.assertEqual(r['triangles'],1)

    def test_indexed_triangle_counts(self):
        binary=struct.pack('<9f3H',0,0,0,1,0,0,0,1,0,0,1,2)
        def change(d):
            d['bufferViews']=[{'buffer':0,'byteLength':36},{'buffer':0,'byteOffset':36,'byteLength':6}]
            d['accessors'].append({'bufferView':1,'componentType':5123,'count':3,'type':'SCALAR'})
            d['meshes'][0]['primitives'][0]['indices']=1
        self.assertEqual(inspect_glb(make_glb(change,binary))['triangles'],1)

    def test_invalid_graphs_and_accessors_rejected(self):
        changes=[lambda d:d['nodes'][0].update(children=[0]),
            lambda d:d['scenes'][0].update(nodes=[0,0]),lambda d:d['scenes'][0].update(nodes=[-1]),
            lambda d:d['nodes'][0].update(mesh=5),lambda d:d['accessors'][0].update(count=999999),
            lambda d:d['accessors'][0].update(sparse={}),lambda d:d['accessors'][0].update(count=True)]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(GenerationError):inspect_glb(make_glb(change))

    def test_external_skin_and_extensions_fail_preflight(self):
        changes=[lambda d:d['buffers'][0].update(uri='https://example.test/data'),
            lambda d:d['nodes'][0].update(skin=0),lambda d:d.update(extensionsRequired=['KHR_draco_mesh_compression']),
            lambda d:d['nodes'][0].update(extensions={'EXT_mesh_gpu_instancing':{}})]
        for change in changes:
            with self.subTest(change=change):self.assertEqual(inspect_glb(make_glb(change))['preflight'],'FAIL')

    def test_chunk_corruption_rejected(self):
        damaged=bytearray(GLB);struct.pack_into('<I',damaged,12,3)
        for value in (bytes(damaged),GLB[:-1],struct.pack('<III',0x46546C67,2,20)+b'12345678'):
            with self.assertRaises(GenerationError):inspect_glb(value)

    def test_conservative_renderer_limit(self):
        def change(d):
            d['nodes']=[{'mesh':0} for _ in range(129)];d['scenes'][0]['nodes']=list(range(129))
        r=inspect_glb(make_glb(change));self.assertEqual(r['preflight'],'FAIL')

    def test_no_semantic_identity_inferred(self):
        r=inspect_glb(GLB)
        self.assertNotIn('semantic',r['hierarchy'][0]);self.assertTrue(any('not semantic' in w for w in r['warnings']))


if __name__ == '__main__': unittest.main()
