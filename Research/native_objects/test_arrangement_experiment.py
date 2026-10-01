import json
from unittest.mock import patch
from Research.native_objects import arrangement_experiment as run
from Research.native_objects.test_connection_spending import ConnectionSpendingTests
from Research.native_objects.test_assembly_arrangements import contract


class ArrangementSpendingTests(ConnectionSpendingTests):
    def call(self,opener=None):
        context={'original_request':run.SPECS[0]['request'],'proposed_role_groups':run.SPECS[0]['roles']}
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

    def test_unchanged_model_budget_and_no_answer_key_in_payload(self):
        self.call();body=json.loads((self.folder/'request.json').read_text())['body'];data=json.loads(body['input'][1]['content'])
        self.assertEqual(set(data),{'request','entities','source_units'});self.assertEqual(body['reasoning']['effort'],'medium')
        self.assertEqual(body['max_output_tokens'],3072)
        self.assertNotIn('expect',data);self.assertNotIn('scorecard',body['input'][0]['content'])
        p,plan=run.body_for('plan',{})
        self.assertEqual(plan['text']['format']['schema'],run.pipeline.compact.SCHEMA)
        self.assertEqual(p['max_output_tokens'],12288);self.assertEqual(p['ceiling_nanos'],160_000_000)
        self.assertLessEqual(run.BATCH.prior_upper_bound+run.BATCH.budget,run.BATCH.aggregate_limit)

    def test_original_drone_request_and_roles_preserved(self):
        original=next(c for c in run.previous.items() if c['case_id']=='generic-drone')
        self.assertEqual(original['request'],run.SPECS[0]['request'])
        self.assertEqual([c['name'] for c in original['candidate']['plan']['components']],run.SPECS[0]['roles'])

    def test_wrong_family_cannot_pass_benchmark_by_valid_ids_alone(self):
        result=run.assess_contract('generic-drone',contract())
        self.assertFalse(result['predeclared_checks_passed']);self.assertEqual(result['interpretation_complete'],'unassessed')
