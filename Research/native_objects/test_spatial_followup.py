import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Research.native_objects import spatial_followup as run
from Research.native_objects.test_spatial_spending import SpatialSpendingTests


class FollowupSpendingTests(SpatialSpendingTests):
    def call(self,opener=None):
        context={'original_request':'Show two parts.','proposed_role_groups':['Housing','Insert']}
        with patch.object(run.prior,'count_input',lambda *_:100),patch.object(run.previous.transport.urllib.request.OpenerDirector,'open',opener or self.open):
            return run.request(run.CASES[0],'extract',0,context,self.folder,self.ledger,'fake-credential')
    def test_experiment_cap_blocks_generation(self):
        with patch.object(run.previous.transport.Batch,'spent',lambda *_:run.BATCH.budget),self.assertRaises(run.prior.CommandError):self.call()
        self.assertEqual(self.calls,0)
    def test_unknown_outcome_keeps_reservation_and_safe_diagnostics(self):
        def fail(*args,**kwargs):raise TimeoutError('fake-credential')
        with self.assertRaises(run.prior.CommandError):self.call(fail)
        self.assertGreater(run.BATCH.spent(self.ledger),0)
        self.assertEqual(json.loads((self.folder/'failure.json').read_text())['category'],'timeout')
        for path in self.folder.glob('*.json'):self.assertNotIn('fake-credential',path.read_text())
        with self.assertRaises(run.prior.CommandError):self.call()
    def test_followup_cannot_revisit_other_completed_cases(self):
        with self.assertRaises(run.prior.CommandError):run.request('generic-speaker','plan',1,{},self.folder,self.ledger,'fake-credential')
        self.assertEqual(self.calls,0)
    def test_planning_gets_longer_deadline_without_more_tokens(self):
        with patch.object(run.previous.transport,'dispatch',return_value=({},{})) as sender:
            run.request(run.CASES[0],'plan',0,{},self.folder,self.ledger,'fake-credential')
        self.assertEqual(sender.call_args.kwargs['timeout'],240)
        self.assertEqual(sender.call_args.args[1]['max_output_tokens'],12288)


class EligibilityTests(unittest.TestCase):
    def test_only_completed_rejected_extractions_without_plans_are_eligible(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d);states=[]
            for case in run.CASES:
                folder=source/(case+'-extract');folder.mkdir()
                (folder/'inventory.json').write_text('{}')
                (folder/'response-metadata.json').write_text(json.dumps({'status':'completed'}))
                states.append({'case':case,'status':'extraction_failed','attempts':[],'geometry_executed':False})
            (source/'result.json').write_text(json.dumps({'cases':states}))
            self.assertEqual(set(run.eligible(source)),set(run.CASES))
            target=source/(run.CASES[0]+'-extract')/'response-metadata.json'
            target.write_text(json.dumps({'status':'incomplete'}))
            with self.assertRaises(ValueError):run.eligible(source)
            target.write_text(json.dumps({'status':'completed'}));states[0]['attempts']=[{'status':'coverage_failed'}]
            (source/'result.json').write_text(json.dumps({'cases':states}))
            with self.assertRaises(ValueError):run.eligible(source)
