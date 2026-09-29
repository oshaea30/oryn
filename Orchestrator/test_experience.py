"""No live providers or USB devices: user requests authorize bounded generation."""
import json
import threading
import urllib.request
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

from app import Jobs, Server, ExperienceError, object_prompt
from providers import GenerationError
from transport import DeliveryError
import test_generation as fixtures
from test_generation import FakeProvider


class ExperienceTests(unittest.TestCase):
    setUp = fixtures.GenerationTests.setUp
    tearDown = fixtures.GenerationTests.tearDown
    wait = fixtures.GenerationTests.wait

    def request(self, identifier='a', prompt='Show me a desk lamp'):
        return self.jobs.request_object({'request_id': identifier * 32, 'prompt': prompt})

    def test_request_generates_and_loads_without_approval_fields(self):
        self.jobs.key = 'PRIVATE_KEY'
        job = self.request(); self.wait()
        result = self.jobs.jobs[job['id']]
        self.assertEqual(result['status'], 'loaded_on_quest')
        self.assertEqual(result['prompt'], 'a desk lamp')
        self.assertEqual(result['approved_geometry_credits'], 5)
        self.assertTrue(result['experience'])
        self.assertEqual(FakeProvider.calls, 1)
        self.assertEqual(FakeProvider.texture_calls, 0)
        self.assertEqual(self.transport.calls, 1)
        self.assertNotIn('PRIVATE_KEY', json.dumps(self.jobs.state()))

    def test_client_cannot_escalate_profile_or_texture(self):
        self.jobs.key = 'secret'
        job = self.jobs.request_object({'request_id':'a'*32, 'prompt':'lamp',
            'profile':'quality', 'approved_credits':1000, 'texture':True})
        self.wait()
        self.assertEqual(job['profile'], 'structure')
        self.assertEqual(FakeProvider.texture_calls, 0)

    def test_same_id_is_idempotent_across_restart(self):
        self.jobs.key = 'secret'; self.request(); self.wait()
        self.request(); self.wait()
        self.jobs = Jobs(self.jobs.root, self.fixture, provider=FakeProvider, transport=self.transport)
        self.request(); self.wait()
        self.assertEqual(FakeProvider.calls, 1)
        self.assertEqual(self.transport.calls, 1)

    def test_id_cannot_be_rebound_to_a_different_request(self):
        self.jobs.key = 'secret'; self.request(); self.wait()
        with self.assertRaises(ExperienceError): self.request(prompt='a chair')
        self.assertEqual(FakeProvider.calls, 1)

    def test_exact_saved_match_reuses_without_key_or_credits(self):
        self.jobs.key = 'secret'; self.request(); self.wait()
        self.jobs.key = ''
        result = self.request('b', 'Please show me A   DESK LAMP'); self.wait()
        self.assertEqual(result['reused_from'], 'a'*32)
        self.assertEqual(result['approved_geometry_credits'], 0)
        self.assertEqual(FakeProvider.calls, 1)
        self.assertEqual(self.transport.calls, 2)

    def test_similar_but_different_object_is_not_an_exact_match(self):
        self.jobs.key = 'secret'; self.request(); self.wait()
        self.request('b', 'a floor lamp'); self.wait()
        self.assertEqual(FakeProvider.calls, 2)

    def test_changed_cached_bytes_do_not_trigger_generation_fallback(self):
        self.jobs.key = 'secret'; self.request(); self.wait()
        (self.jobs.root / ('a'*32) / 'model.glb').write_bytes(b'corrupt')
        self.request('b'); self.wait()
        self.assertEqual(self.jobs.jobs['b'*32]['status'], 'failed')
        self.assertEqual(FakeProvider.calls, 1)
        self.assertEqual(self.transport.calls, 1)

    def test_failed_generation_is_reserved_and_not_retried(self):
        self.jobs.key = 'secret'
        provider = Mock(); provider.generate_geometry.side_effect = GenerationError('Timed out; no retry.')
        self.jobs.provider = Mock(return_value=provider)
        self.request(); self.wait(); self.request(); self.wait()
        self.assertEqual(provider.generate_geometry.call_count, 1)
        self.assertEqual(self.jobs.reserved_credits(), 5)

    def test_cap_survives_restart_and_includes_lab_reservations(self):
        self.jobs.key = 'secret'; self.jobs.submit(self.body); self.wait()
        self.jobs.update('a'*32, approved_geometry_credits=50, status='failed')
        self.jobs = Jobs(self.jobs.root, self.fixture, key='secret', provider=FakeProvider, transport=self.transport)
        with self.assertRaises(ExperienceError): self.request('b')
        self.assertEqual(FakeProvider.calls, 1)

    def test_pending_delivery_blocks_new_request(self):
        self.jobs.key = 'secret'
        def deliver(path, job, progress):
            progress('waiting_for_headset', 100, delivery_id='f'*32)
            return 'quest', 'f'*32
        self.transport.deliver = Mock(side_effect=deliver)
        self.request(); self.wait()
        self.assertTrue(self.jobs.state()['deliveryPending'])
        self.assertEqual(self.jobs.jobs['a'*32]['status'], 'waiting_for_headset')
        self.jobs = Jobs(self.jobs.root, self.fixture, key='secret', provider=FakeProvider, transport=self.transport)
        self.assertTrue(self.jobs.state()['deliveryPending'])
        with self.assertRaises(ValueError): self.request('b', 'chair')
        self.assertEqual(FakeProvider.calls, 1)

    def test_concurrent_requests_cannot_exceed_credit_cap(self):
        self.jobs.key = 'secret'; self.jobs.submit(self.body); self.wait()
        self.jobs.update('a'*32, approved_geometry_credits=45)
        def request(identifier):
            try: return self.request(identifier, 'object '+identifier)
            except ValueError: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(request, ['b', 'c']))
        self.wait()
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(self.jobs.reserved_credits(), 50)
        self.assertEqual(FakeProvider.calls, 2)

    def test_failed_preflight_blocks_automatic_delivery(self):
        self.jobs.key = 'secret'
        report = fixtures.inspect_glb(fixtures.GLB)
        report['preflight'] = 'FAIL'
        with patch('app.inspect_glb', return_value=report):
            self.request(); self.wait()
        self.assertEqual(self.jobs.jobs['a'*32]['status'], 'delivery_failed')
        self.assertEqual(self.transport.calls, 0)

    def test_delivery_failure_keeps_asset_and_never_regenerates(self):
        self.jobs.key = 'secret'
        self.transport.deliver = Mock(side_effect=DeliveryError('Quest disconnected'))
        self.request(); self.wait()
        self.assertEqual(self.jobs.jobs['a'*32]['status'], 'delivery_failed')
        self.assertTrue((self.jobs.root / ('a'*32) / 'model.glb').exists())
        self.request(); self.wait()
        self.assertEqual(FakeProvider.calls, 1)
        self.assertEqual(self.transport.deliver.call_count, 1)

    def test_invalid_prompt_has_no_side_effects(self):
        for value in (None, '', ' '*10, 'show me ', 'x'*801, 12):
            with self.subTest(value=value), self.assertRaises(ValueError): object_prompt(value)
        self.assertEqual(FakeProvider.calls, 0)

    def test_workflow_is_application_owned_and_saved_match_reuses_analysis(self):
        self.jobs.key = 'secret'; self.request(); self.wait()
        first = self.jobs.jobs['a'*32]
        self.assertEqual(first['investigations']['geometry']['status'], 'awaiting_research')
        self.request('b'); self.wait()
        second = self.jobs.jobs['b'*32]
        self.assertEqual(first['investigations']['geometry']['id'], second['investigations']['geometry']['id'])
        self.assertNotEqual(first['route_decision_id'], second['route_decision_id'])
        groups = self.jobs.workflows.metrics()['groups']
        self.assertEqual(groups['asset_route:oryn-local-rules:1']['actions'], {'generation': 1, 'library': 1})
        self.assertEqual(groups['geometry_triage:oryn-local-rules:1']['calls'], 1)
        self.assertEqual(self.transport.calls, 2)

    def test_failed_investigation_does_not_block_asset_delivery(self):
        self.jobs.key = 'secret'
        with patch.object(self.jobs.workflows, 'prepare', side_effect=ValueError('PRIVATE_TOKEN')):
            self.request(); self.wait()
        job = self.jobs.jobs['a'*32]
        self.assertEqual(job['status'], 'loaded_on_quest')
        self.assertTrue(job['investigation_error'])
        self.assertNotIn('PRIVATE_TOKEN', json.dumps(job))

    def test_failed_route_never_dispatches_paid_generation(self):
        self.jobs.key = 'secret'
        with patch.object(self.jobs.workflows, 'decide_local', side_effect=ValueError('PRIVATE_TOKEN')):
            with self.assertRaises(ExperienceError): self.request()
        self.assertEqual(FakeProvider.calls, 0)
        self.assertEqual(self.jobs.jobs['a'*32]['status'], 'failed')
        self.assertNotIn('PRIVATE_TOKEN', json.dumps(self.jobs.jobs['a'*32]))

    def test_http_request_endpoint_is_guarded_but_needs_no_approval(self):
        self.jobs.key = 'secret'
        server = Server(0, self.jobs)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            body = json.dumps({'request_id':'a'*32, 'prompt':'Show me a lamp'}).encode()
            headers = {'Content-Type':'application/json', 'Origin':server.origin}
            request = urllib.request.Request(server.origin+'/api/request-object', data=body, headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
            self.assertEqual(caught.exception.code, 403); caught.exception.close()
            headers['X-Oryn-Token'] = server.token
            request = urllib.request.Request(server.origin+'/api/request-object', data=body, headers=headers)
            with urllib.request.urlopen(request) as response: self.assertEqual(response.status, 202)
            self.wait(); self.assertEqual(self.transport.calls, 1)
            with urllib.request.urlopen(server.origin+'/objects') as response: self.assertIn(b'Ask. It appears.', response.read())
            with urllib.request.urlopen(server.origin+'/lab') as response: self.assertIn(b'approvalText', response.read())
            investigation = self.jobs.jobs['a'*32]['investigations']['geometry']
            with urllib.request.urlopen(server.origin+'/api/workflow?id='+investigation['id']) as response:
                report = json.load(response)
                self.assertEqual(report['status'], 'awaiting_research')
                self.assertEqual(len(report['decisions']), 1)
            with urllib.request.urlopen(server.origin+'/api/workflow-metrics') as response:
                self.assertEqual(json.load(response)['currency'], 'USD')
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(server.origin+'/api/workflow?id=../../private')
            self.assertEqual(caught.exception.code, 404); caught.exception.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
