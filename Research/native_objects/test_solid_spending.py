import tempfile
import json
import urllib.error
from pathlib import Path
import unittest
from unittest.mock import patch
from Research.native_objects import solid_experiment as run

class SolidSpendingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.ledger=run.UsageLedger(self.folder/'usage.sqlite3')
        self.policy=run.chosen('review');self.calls=0
        self.request=run.body(self.policy,'Synthetic test policy','Synthetic test',{'type':'object'},'test')
    def response(self,*_):
        self.calls+=1
        return {'model':self.policy['model'],'service_tier':'default','status':'completed',
                'usage':{'input_tokens':100,'output_tokens':20},
                'output':[{'type':'message','content':[{'type':'output_text','text':'{}'}]}]}
    def call(self,sender=None):
        with patch.object(run,'count_input',lambda *_:100),patch.object(run,'send',sender or self.response):
            return run.request_model('generic-drone',0,'review',self.policy,self.request,self.folder,self.ledger,'fake-test-key')
    def test_no_duplicate_dispatch(self):
        _,billing=self.call()
        with self.assertRaises(run.CommandError):self.call()
        self.assertEqual(self.calls,1)
        self.assertEqual(run.spent(self.ledger),billing['calculated_cost_nanos'])
    def test_experiment_cap_blocks_before_generation(self):
        with patch.object(run,'spent',lambda _:run.BUDGET),self.assertRaises(run.CommandError):self.call()
        self.assertEqual(self.calls,0)
    def test_unknown_transport_keeps_spending_reservation(self):
        def fail(*_):raise TimeoutError()
        with self.assertRaises(run.CommandError):self.call(fail)
        self.assertGreater(run.spent(self.ledger),0)
        with self.assertRaises(run.CommandError):self.call()
        self.assertEqual(self.calls,0)
    def test_safe_failure_diagnostics(self):
        def fail(*_):raise urllib.error.URLError(TimeoutError('fake-test-key secret URL'))
        with self.assertRaises(run.CommandError):self.call(fail)
        text=(self.folder/'review-failure.json').read_text()
        self.assertNotIn('fake-test-key',text)
        self.assertNotIn('secret URL',text)
        report=json.loads(text)
        self.assertEqual(report['category'],'timeout')
        self.assertGreaterEqual(report['dispatch_elapsed_seconds'],0)
        self.assertTrue(report['budget_reservation_held'])
        self.assertFalse(report['automatic_retry'])
    def test_unknown_usage_halts_shared_ledger(self):
        with self.assertRaises(run.CommandError):self.call(lambda *_:{'status':'completed'})
        self.assertTrue(self.ledger.summary()['halted'])
    def test_credentials_not_in_journal(self):
        self.call()
        for path in self.folder.glob('*.json'):self.assertNotIn('fake-test-key',path.read_text())
if __name__=='__main__':unittest.main()
