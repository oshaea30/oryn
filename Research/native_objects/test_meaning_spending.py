import json
from unittest.mock import patch
from Research.native_objects import meaning_experiment as run
from Research.native_objects.test_connection_spending import ConnectionSpendingTests

class MeaningSpendingTests(ConnectionSpendingTests):
    def call(self,opener=None):
        with patch.object(run.prior,'count_input',lambda *_:100),patch.object(run.urllib.request.OpenerDirector,'open',opener or self.open):
            return run.request(run.CASES[0],self.folder,self.ledger,'fake-credential')
    def test_experiment_cap_blocks_generation(self):
        with patch.object(run.Batch,'spent',lambda *_:run.BUDGET),self.assertRaises(run.prior.CommandError):self.call()
        self.assertEqual(self.calls,0)
    def test_unknown_outcome_keeps_reservation_and_safe_diagnostics(self):
        def fail(*args,**kwargs):raise TimeoutError('fake-credential')
        with self.assertRaises(run.prior.CommandError):self.call(fail)
        self.assertGreater(run.spent(self.ledger),0)
        self.assertEqual(json.loads((self.folder/'failure.json').read_text())['category'],'timeout')
        for path in self.folder.glob('*.json'):self.assertNotIn('fake-credential',path.read_text())
        with self.assertRaises(run.prior.CommandError):self.call()
    def test_scorecard_is_not_in_model_payload(self):
        self.call();body=json.loads((self.folder/'request.json').read_text())['body'];data=json.loads(body['input'][1]['content'])
        self.assertEqual(set(data),{'request','proposed_role_groups'})
        self.assertNotIn('expect',data)
    def test_unknown_case_cannot_spend(self):
        with self.assertRaises(run.prior.CommandError):run.request({'id':'other'},self.folder,self.ledger,'fake-credential')
        self.assertEqual(self.calls,0)
