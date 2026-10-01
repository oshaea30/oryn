import copy
import tempfile
from pathlib import Path
import unittest
from Research.native_objects import connection_experiment as run
from Research.native_objects.test_assembly_connections import fixture


class ConnectionLoopTests(unittest.TestCase):
    def item(self):return {'case_id':'generic-drone','request':'synthetic test','candidate':{'plan':{'fidelity':'generic_design','retrieval':'none','next_step':'propose_geometry','components':[{'name':'host'},{'name':'child'}],'assumptions':[]}}}
    def test_feedback_repairs_geometry_under_same_contract(self):
        initial=fixture(True);initial['parts'][1]['forms'][0]['size']=[.18,.15,.18]
        contexts=[]
        def model(case,attempt,context,folder):
            contexts.append(copy.deepcopy(context));return (initial if attempt==0 else fixture(True)),{}
        with tempfile.TemporaryDirectory() as folder:result=run.run_case(self.item(),Path(folder),model,lambda _:None)
        self.assertEqual([a['status'] for a in result['attempts']],['structural_failure','structural_candidate'])
        self.assertTrue(contexts[1]['application_feedback']['failed_geometry_checks'])
        self.assertIn('locked_requirements',contexts[1])
        self.assertFalse(result['native_generation_goal_passed'])
    def test_repair_cannot_erase_requirement(self):
        initial=fixture(True);initial['parts'][1]['forms'][0]['size']=[.18,.15,.18]
        altered=fixture(True);altered['mates'][0]['minimum_clearance']=0
        def model(case,attempt,context,folder):return (initial if attempt==0 else altered),{}
        with tempfile.TemporaryDirectory() as folder:result=run.run_case(self.item(),Path(folder),model,lambda _:None)
        self.assertEqual(result['attempts'][-1]['status'],'rejected')
        self.assertIn('locked',result['attempts'][-1]['error'])
    def test_compiler_failure_can_repair_geometry_without_changing_contract(self):
        initial=fixture();initial['parts'][0]['forms'][0]['kind']='ellipsoid'
        contexts=[]
        def model(case,attempt,context,folder):
            contexts.append(context);return (initial if attempt==0 else fixture()),{}
        with tempfile.TemporaryDirectory() as folder:result=run.run_case(self.item(),Path(folder),model,lambda _:None)
        self.assertEqual([a['status'] for a in result['attempts']],['rejected','structural_candidate'])
        self.assertIn('compiler_error',contexts[1]['application_feedback'])
    def test_exact_product_remains_blocked_without_dispatch(self):
        item=self.item();item['candidate']['plan']['fidelity']='exact_product'
        def forbidden(*_):self.fail('Must not dispatch')
        with tempfile.TemporaryDirectory() as folder:result=run.run_case(item,Path(folder),forbidden,forbidden)
        self.assertEqual(result['status'],'blocked_evidence')
    def test_transport_failure_never_retries(self):
        calls=[]
        def fail(*_):calls.append(1);raise run.prior.CommandError('No response')
        with tempfile.TemporaryDirectory() as folder:result=run.run_case(self.item(),Path(folder),fail,lambda _:None)
        self.assertEqual(len(calls),1);self.assertEqual(result['attempts'][0]['status'],'request_failed')

if __name__=='__main__':unittest.main()
