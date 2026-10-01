from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Research.native_objects import assembly_followup as run
from Research.native_objects.test_connection_spending import ConnectionSpendingTests


class FollowupSpendingTests(ConnectionSpendingTests):
    def call(self,opener=None):
        with patch.object(run.prior,'count_input',lambda *_:100),patch.object(run.transport.urllib.request.OpenerDirector,'open',opener or self.open):
            return run.request(run.CASES[0],'plan',0,{},self.folder,self.ledger,'fake-credential')

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

    def test_unapproved_operations_cannot_spend(self):
        for case,stage,attempt in [('new','plan',0),(run.CASES[0],'extract',1),(run.CASES[0],'plan',2),(run.REPLAY_CASE,'extract',0),(run.REPLAY_CASE,'plan',0)]:
            with self.assertRaises(run.prior.CommandError):run.request(case,stage,attempt,{},self.folder,self.ledger,'fake-credential')
        self.assertEqual(self.calls,0)
        self.assertEqual(len(run.OPERATIONS),7)
        self.assertLessEqual(run.BATCH.prior_upper_bound+run.BATCH.budget,run.BATCH.aggregate_limit)

    def test_same_model_token_caps_and_no_scorecard_in_payload(self):
        context={'original_request':run.SPECS[0]['request'],'proposed_role_groups':run.SPECS[0]['roles']}
        p,body=run.body_for('extract',context);data=json.loads(body['input'][1]['content'])
        self.assertEqual(set(data),{'request','entities','source_units'})
        self.assertEqual(p['model'],run.previous.selected('extract')['model']);self.assertEqual(body['reasoning']['effort'],'medium')
        self.assertEqual(body['max_output_tokens'],3072);self.assertEqual(p['ceiling_nanos'],45_000_000)
        schema=body['text']['format']['schema']
        self.assertEqual(schema['properties']['requirements']['items']['minItems'],10)
        self.assertEqual(schema['properties']['requirements']['maxItems'],48)
        self.assertNotIn('expect',data);self.assertNotIn('scorecard',body['input'][0]['content'])
        p,body=run.body_for('plan',{})
        self.assertEqual(body['text']['format']['schema'],run.pipeline.compact.SCHEMA)
        self.assertEqual(p['max_output_tokens'],12288);self.assertEqual(p['ceiling_nanos'],160_000_000)
        self.assertIn('MEASURED REPAIR BASELINE',body['input'][0]['content'])


class ReplayTests(unittest.TestCase):
    def test_replay_preserves_geometry_and_avoids_network(self):
        data=run.prepare_replay();self.assertTrue(data['audit']['solved_geometry_identical'])
        c=data['contract'];contexts={'extract':{'original_request':data['spec']['request'],'proposed_role_groups':data['spec']['roles']},
            'plan':{'original_request':data['spec']['request'],'requirements':c['inventory'],'requirement_hash':c['inventory_sha256'],
                'spatial_rules':c['spatial_rules'],'assemblies':c['assemblies']}}
        with tempfile.TemporaryDirectory() as temp,patch.object(run.transport,'dispatch',side_effect=AssertionError('No paid dispatch')):
            for stage in ('extract','plan'):
                raw,bill=run.replay(stage,contexts[stage],Path(temp),data)
                self.assertEqual(raw,data['inventory' if stage=='extract' else 'plan']);self.assertTrue(bill['replayed']);self.assertEqual(bill['new_cost_nanos'],0)
            output=Path(temp);folder=output/(run.REPLAY_CASE+'-plan-0');folder.mkdir()
            run.pipeline.evaluate_candidate(data['plan'],c,folder,run.REPLAY_CASE,renderer=lambda _:None,preserve_passes=True)
            run.verify_replayed_execution(output,data)
            changed=json.loads((folder/'compiled.json').read_text());changed['parts'][0]['position'][0]+=.1
            (folder/'compiled.json').write_text(json.dumps(changed))
            with self.assertRaises(run.prior.CommandError):run.verify_replayed_execution(output,data)

    def test_changed_replay_request_or_contract_is_rejected(self):
        data=run.prepare_replay()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(run.prior.CommandError):run.replay('extract',{'original_request':'changed'},Path(temp),data)
            with self.assertRaises(run.prior.CommandError):run.replay('plan',{'original_request':data['spec']['request'],'requirements':{}},Path(temp),data)

    def test_previous_unmapped_front_contact_is_not_a_followup_pass(self):
        contract=json.loads((run.BASELINE/'two-driver-speaker-extract/contract.json').read_text())
        states={'two-driver-speaker':{'status':'unsupported_before_planning','geometry_executed':False,'contract':contract,'attempts':[]}}
        result=run.assess(states,run.BASELINE)[0]
        self.assertFalse(result['predeclared_checks_passed'])
        self.assertFalse(next(c['passed'] for c in result['checks'] if c['kind']=='original_front_face_requirement'))

    def test_character_audit_is_lossless_not_a_token_claim(self):
        for row in run.codec_audit():
            self.assertTrue(row['lossless_roundtrip']);self.assertGreater(row['character_reduction_fraction'],.3)
            self.assertIn('not measured',row['token_reduction'])

if __name__=='__main__':unittest.main()
