import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Research.native_objects import connection_experiment as run


class Reply:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):
        return json.dumps({'model':run.prior.chosen('construct')['model'],'service_tier':'default','status':'completed',
            'usage':{'input_tokens':100,'output_tokens':20},
            'output':[{'type':'message','content':[{'type':'output_text','text':'{}'}]}]}).encode()


class ConnectionSpendingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        self.ledger=run.prior.UsageLedger(self.folder/'ledger.sqlite3');self.calls=0
    def open(self,*args,**kwargs):self.calls+=1;return Reply()
    def call(self,opener=None):
        with patch.object(run.prior,'count_input',lambda *_:100),patch.object(run.urllib.request.OpenerDirector,'open',opener or self.open):
            return run.request_model('generic-drone',0,{},self.folder,self.ledger,'fake-credential')
    def test_no_duplicate_dispatch(self):
        self.call()
        with self.assertRaises(run.prior.CommandError):self.call()
        self.assertEqual(self.calls,1)
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
    def test_billing_mismatch_halts(self):
        with patch.object(run.prior,'settled_usage',side_effect=run.prior.CommandError('Mismatch')):
            with self.assertRaises(run.prior.CommandError):self.call()
        self.assertTrue(self.ledger.summary()['halted'])

if __name__=='__main__':unittest.main()
