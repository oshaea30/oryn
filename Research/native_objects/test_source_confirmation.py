import io
import json
import urllib.error
from unittest.mock import patch
from Research.native_objects import source_confirmation as run
from Research.native_objects.test_connection_spending import ConnectionSpendingTests


class SourceConfirmationTests(ConnectionSpendingTests):
    def call(self,opener=None):
        with patch.object(run.prior,'count_input',lambda *_:100),patch.object(run.previous.urllib.request.OpenerDirector,'open',opener or self.open):
            return run.request(run.CASES[0],self.folder,self.ledger,'fake-credential')

    def test_experiment_cap_blocks_generation(self):
        with patch.object(run.previous.Batch,'spent',lambda *_:run.BATCH.budget),self.assertRaises(run.prior.CommandError):self.call()
        self.assertEqual(self.calls,0)

    def test_unknown_outcome_keeps_reservation_and_safe_diagnostics(self):
        def fail(*args,**kwargs):raise TimeoutError('fake-credential')
        with self.assertRaises(run.prior.CommandError):self.call(fail)
        self.assertGreater(run.BATCH.spent(self.ledger),0)
        self.assertEqual(json.loads((self.folder/'failure.json').read_text())['category'],'timeout')
        for path in self.folder.glob('*.json'):self.assertNotIn('fake-credential',path.read_text())
        with self.assertRaises(run.prior.CommandError):self.call()

    def test_one_case_per_payload_and_no_expected_answers(self):
        self.call();body=json.loads((self.folder/'request.json').read_text())['body'];content=json.loads(body['input'][1]['content'])
        self.assertEqual(set(content),{'request','proposed_role_groups','source_units'})
        self.assertEqual(content['source_units'],run.meaning.source_units(run.CASES[0]['request']))
        self.assertEqual(body['max_output_tokens'],3072)
        self.assertEqual(body['text']['format']['schema'],run.meaning.source_schema(run.CASES[0]['request']))
        self.assertEqual(self.ledger.get(run.BATCH.operation_id(run.CASES[0]['id']))['operation'],'meaning-006')

    def test_unknown_case_cannot_spend(self):
        with self.assertRaises(run.prior.CommandError):run.request({'id':'other'},self.folder,self.ledger,'fake-credential')
        self.assertEqual(self.calls,0)

    def test_funding_and_rate_limits_remain_distinct_and_private(self):
        for code,expected in [('insufficient_quota','provider_funding_required'),('rate_limit_exceeded','rate_limited'),('unknown','http_error')]:
            error=urllib.error.HTTPError('https://secret.invalid',429,'fake-credential',{},io.BytesIO(json.dumps({'error':{'code':code,'message':'fake-credential'}}).encode()))
            self.assertEqual(run.previous.failure_category(error),expected)

    def test_funding_stops_batch_before_next_call(self):
        calls=[]
        def model(case,folder):
            calls.append(case['id']);raise run.prior.CommandError('Provider funding required; top up the API account before continuing')
        results=run.execute(self.folder,model)
        self.assertEqual(len(calls),1);self.assertEqual(results[0]['status'],'stopped')
        self.assertFalse(results[0]['geometry_executed'])
