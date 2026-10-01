from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Research.native_objects import repair_experiment as run

class ExperimentTests(unittest.TestCase):
    def test_same_model_limits_and_typed_output(self):
        spec=run.SPECS[-1];p,body=run.body_for('extract',{'original_request':spec['request'],'proposed_role_groups':spec['roles']})
        self.assertEqual(p['model'],'gpt-6-sol');self.assertEqual(p['effort'],'medium');self.assertEqual(p['max_output_tokens'],3072)
        ex=body['text']['format']['schema']['properties']['exclusions']['items']['properties']['d']['enum']
        self.assertIn('motion',ex);self.assertNotIn('animate',ex)
        self.assertEqual(set(json.loads(body['input'][1]['content'])),{'request','entities','source_units'})
        self.assertLessEqual(run.BATCH.budget+run.BATCH.prior_upper_bound,run.BATCH.aggregate_limit)
        self.assertEqual(len(run.OPERATIONS),6);self.assertEqual(run.selected('patch')['max_output_tokens'],6144)

    def test_pending_resumes_same_stage_and_failed_cases_do_not_get_extra_calls(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);original=run.pipeline.evaluate_candidate
            def evaluate(*a,**kw):kw['renderer']=lambda _:None;return original(*a,**kw)
            with patch.object(run.pipeline,'evaluate_candidate',side_effect=evaluate):states=run.initialize(folder)
            protocol={'files_sha256':run.frozen_sources()};ledger=run.prior.UsageLedger(folder/'ledger.sqlite3');calls=[]
            def pending(*a,**kw):calls.append(a[0]);raise run.background.Pending('retained ID')
            with patch.object(run.background,'dispatch',side_effect=pending):run.run(folder,ledger,'fake',protocol,states)
            self.assertEqual(calls,[run.BATCH.operation_id(run.OPERATIONS[0])]);self.assertEqual(states['cooling-fan-row']['status'],'geometry_failed')
            def response(ident,p,body,*a,**kw):
                calls.append(ident);data=json.loads(body['input'][1]['content'])
                bill={'dispatch_seconds':1,'creation_calls':1,'poll_calls':1,'usage':{'input_tokens':100,'output_tokens':20},'calculated_cost_nanos':1000}
                if ident==run.BATCH.operation_id(run.OPERATIONS[0]):return {'base_sha256':data['repair_scope']['base_sha256'],'status':'unsupported','reason':'No permitted correction','shapes':[],'ports':[]},bill
                if ident==run.BATCH.operation_id(run.OPERATIONS[1]):
                    raw=json.loads((run.SOURCE/'results/assembly-010/two-driver-speaker-extract/inventory.json').read_text());return run.typed.encode(raw),bill
                raise ValueError('Incomplete generation')
            with patch.object(run.background,'dispatch',side_effect=response):run.run(folder,ledger,'fake',protocol,states)
            self.assertEqual(calls[0],calls[1]);self.assertEqual(len(calls),4)
            self.assertEqual(states['cooling-fan-row']['status'],'repair_unsupported')
            self.assertEqual(states['two-driver-speaker']['status'],'unsupported_before_planning')
            self.assertEqual(states['generic-drone']['status'],'plan_rejected')
            with patch.object(run.background,'dispatch',side_effect=AssertionError('No repeats')):run.run(folder,ledger,'fake',protocol,states)

if __name__=='__main__':unittest.main()
