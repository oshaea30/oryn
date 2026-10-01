import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from Research.native_objects import requirements_experiment as run
from Research.native_objects.test_intent_requirements import inventory, proposal, bindings, req, REQUEST
from Research.native_objects.test_connection_spending import ConnectionSpendingTests

class RequirementSpendingTests(ConnectionSpendingTests):
    def call(self,opener=None):
        with patch.object(run.prior,'count_input',lambda *_:100),patch.object(run.urllib.request.OpenerDirector,'open',opener or self.open):
            return run.request_model('generic-drone','plan',0,{},self.folder,self.ledger,'fake-credential')
    def test_experiment_cap_blocks_generation(self):
        with patch.object(run,'spent',lambda _:run.BUDGET),self.assertRaises(run.prior.CommandError):self.call()
        self.assertEqual(self.calls,0)
    def test_unknown_outcome_keeps_reservation_and_safe_diagnostics(self):
        def fail(*args,**kwargs):raise TimeoutError('fake-credential')
        with self.assertRaises(run.prior.CommandError):self.call(fail)
        self.assertGreater(run.spent(self.ledger),0)
        self.assertEqual(json.loads((self.folder/'failure.json').read_text())['category'],'timeout')
        for path in self.folder.glob('*.json'):self.assertNotIn('fake-credential',path.read_text())
        with self.assertRaises(run.prior.CommandError):self.call()

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
    def test_gate_precedes_builder(self):
        c=inventory();p=run.compact.pack(proposal(),c,bindings()[:-1]);builder=Mock(side_effect=AssertionError('must not build'))
        result,_=run.evaluate_candidate(p,c,self.folder,'test',builder=builder)
        self.assertEqual(result['status'],'coverage_failed');builder.assert_not_called()
    def test_required_unsupported_precedes_builder(self):
        c=inventory([req('light','capability',value='emission',kind='visual')]);b=bindings()+[{'id':'light','kind':'unsupported','refs':[],'note':'No renderer'}]
        p=run.compact.pack(proposal(),c,b);builder=Mock(side_effect=AssertionError('must not build'))
        result,_=run.evaluate_candidate(p,c,self.folder,'test',builder=builder)
        self.assertEqual(result['status'],'unsupported_required');builder.assert_not_called()
    def items(self):
        return [{'case_id':c,'request':REQUEST,'candidate':{'plan':{'fidelity':'generic_design','retrieval':'none','next_step':'propose_geometry','components':[{'name':'host'},{'name':'child'}]}}} for c in run.CASES]
    def test_missing_binding_repaired_against_same_frozen_contract(self):
        calls=[];c=inventory()
        def model(case,stage,attempt,context,folder):
            calls.append((case,stage,attempt,copy.deepcopy(context)))
            if stage=='extract':return c['inventory'],{}
            self.assertEqual(context['requirements'],c['inventory'])
            if attempt:self.assertEqual(context['application_feedback']['coverage_errors'][0]['id'],'inside')
            return run.compact.pack(proposal(),c,bindings() if attempt else bindings()[:-1]),{}
        states=run.execute(self.items(),self.folder,model,renderer=lambda _:None)
        self.assertEqual([x[1] for x in calls[:4]],['extract']*4)
        self.assertEqual([x[2] for x in calls[4:8]],[0]*4)
        for state in states.values():
            self.assertEqual(state['status'],'structural_candidate')
            self.assertFalse(state['attempts'][0]['geometry_executed'])
            self.assertTrue(state['attempts'][1]['geometry_executed'])
    def test_incomplete_response_is_not_retried(self):
        def model(case,stage,attempt,context,folder):
            if stage=='extract':return inventory()['inventory'],{}
            self.assertEqual(attempt,0);raise ValueError('Incomplete provider response')
        states=run.execute(self.items(),self.folder,model,renderer=lambda _:None)
        self.assertTrue(all(s['status']=='response_invalid' and not s['geometry_executed'] and len(s['attempts'])==1 for s in states.values()))
    def test_saved_extraction_revalidation_preserves_response(self):
        c=inventory();case=run.CASES[0];folder=self.folder/(case+'-extract');folder.mkdir()
        response={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(c['inventory'])}]}]}
        for name,data in [('response.json',response),('inventory.json',c['inventory']),('response-metadata.json',{'operation_id':'original'})]:run.prior.write(folder/name,data)
        run.prior.write(self.folder/'result.json',{'cases':[{'case':case,'status':'extraction_failed','attempts':[],'request':REQUEST,'error':'Invalid identity'}]})
        replay=run.saved_extractions(self.folder)[case]
        self.assertEqual(replay['raw'],c['inventory']);self.assertEqual(replay['billing']['new_cost_nanos'],0)
        run.prior.write(folder/'inventory.json',{})
        with self.assertRaises(ValueError):run.saved_extractions(self.folder)
    def test_invalid_extraction_stops_before_plan(self):
        def model(case,stage,attempt,context,folder):
            self.assertEqual(stage,'extract');return {},{}
        states=run.execute(self.items(),self.folder,model,renderer=lambda _:None)
        self.assertTrue(all(s['status']=='extraction_failed' and not s['attempts'] for s in states.values()))
if __name__=='__main__':unittest.main()
