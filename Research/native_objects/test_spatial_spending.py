import json
from unittest.mock import patch
from Research.native_objects import spatial_experiment as run
from Research.native_objects.test_connection_spending import ConnectionSpendingTests


class SpatialSpendingTests(ConnectionSpendingTests):
    def call(self,opener=None):
        context={'original_request':'Show two parts.','proposed_role_groups':['Housing','Insert']}
        with patch.object(run.prior,'count_input',lambda *_:100),patch.object(run.transport.urllib.request.OpenerDirector,'open',opener or self.open):
            return run.request(run.CASES[0],'extract',0,context,self.folder,self.ledger,'fake-credential')
    def test_experiment_cap_blocks_generation(self):
        with patch.object(run.transport.Batch,'spent',lambda *_:run.BATCH.budget),self.assertRaises(run.prior.CommandError):self.call()
        self.assertEqual(self.calls,0)
    def test_unknown_outcome_keeps_reservation_and_safe_diagnostics(self):
        def fail(*args,**kwargs):raise TimeoutError('fake-credential')
        with self.assertRaises(run.prior.CommandError):self.call(fail)
        self.assertGreater(run.BATCH.spent(self.ledger),0)
        self.assertEqual(json.loads((self.folder/'failure.json').read_text())['category'],'timeout')
        for path in self.folder.glob('*.json'):self.assertNotIn('fake-credential',path.read_text())
        with self.assertRaises(run.prior.CommandError):self.call()
    def test_unknown_operation_and_extra_repair_cannot_spend(self):
        for case,stage,attempt in [('new','extract',0),(run.CASES[0],'extract',1),(run.CASES[0],'plan',2)]:
            with self.assertRaises(run.prior.CommandError):run.request(case,stage,attempt,{},self.folder,self.ledger,'fake-credential')
        self.assertEqual(self.calls,0)
    def test_payload_contains_no_expectations_or_scorecard(self):
        self.call();body=json.loads((self.folder/'request.json').read_text())['body'];data=json.loads(body['input'][1]['content'])
        self.assertEqual(set(data),{'request','entities','source_units'});self.assertEqual(body['reasoning']['effort'],'medium')
        self.assertEqual(body['max_output_tokens'],3072)
    def test_plan_uses_frozen_rules_instead_of_new_geometry_schema(self):
        context={'spatial_rules':[{'id':'r','operator':'on_top','reference':'','axis':''}]}
        p,body=run.body_for('plan',context)
        self.assertEqual(body['text']['format']['schema'],run.pipeline.compact.SCHEMA)
        self.assertEqual(json.loads(body['input'][1]['content']),context)
        self.assertEqual(p['max_output_tokens'],12288)
