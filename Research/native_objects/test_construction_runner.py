import json
from pathlib import Path
import tempfile
import time
import unittest
from Research.native_objects.construction_experiment import generate,parse,selected_policy,execute,UsageLedger,CommandError
from Research.native_objects.test_construction import fixture


def item():
    return {'case_id':'generic-drone','request':'Synthetic fixture only',
        'candidate':{'plan':{'fidelity':'generic_design','next_step':'propose_geometry','retrieval':'none',
            'components':[{'name':'A'},{'name':'B'}],'assumptions':[]}}}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.ledger=UsageLedger(Path(self.temp.name)/'ledger.sqlite3');self.chosen=selected_policy(int(time.time()));self.calls=0

    def sender(self,key,body):
        self.calls+=1
        return {'status':'completed','model':self.chosen['model'],'service_tier':'default',
            'usage':{'input_tokens':100,'output_tokens':100},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(fixture())}]}]}

    def run_case(self,sender=None):
        return generate(item(),self.ledger,'fake-test-key',self.chosen,counter=lambda *_:100,sender=sender or self.sender)

    def test_quoted_cost_and_duplicate_refusal(self):
        response,cost=self.run_case();self.assertEqual(parse(response),fixture())
        self.assertLess(cost['calculated_cost_nanos'],120_000_000)
        with self.assertRaises(CommandError):self.run_case()
        self.assertEqual(self.calls,1)

    def test_timeout_retains_reservation_without_retry(self):
        def fail(*args):raise TimeoutError('never printed')
        with self.assertRaises(CommandError):self.run_case(fail)
        self.assertGreater(self.ledger.summary()['charged_and_reserved_nanos'],0)
        with self.assertRaises(CommandError):self.run_case()
        self.assertEqual(self.calls,0)

    def test_unknown_usage_halts(self):
        def bad(*args):return {'status':'completed','usage':{'input_tokens':99999,'output_tokens':1}}
        with self.assertRaises(CommandError):self.run_case(bad)
        self.assertTrue(self.ledger.summary()['halted'])

    def test_incomplete_billed_and_preserved(self):
        def incomplete(*args):
            r=self.sender(*args);r['status']='incomplete';return r
        r,cost=self.run_case(incomplete)
        with self.assertRaises(ValueError):parse(r)
        self.assertEqual(self.ledger.get(cost['operation_id'])['outcome'],'incomplete')

    def test_exact_gate_does_not_call_model(self):
        x=item();x['case_id']='exact-product';x['candidate']['plan']['fidelity']='exact_product'
        output=Path(self.temp.name)/'output';output.mkdir()
        records=execute([x],output,self.ledger,None,self.chosen)
        self.assertEqual(records[0]['status'],'blocked_evidence')
        self.assertEqual(self.ledger.summary()['charged_and_reserved_nanos'],0)

if __name__=='__main__':unittest.main()
