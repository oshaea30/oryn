from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Research.native_objects import background_requests as bg
from Research.native_objects import assembly_followup as prior_run

class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
        self.time=1790869000.;self.clock=lambda:self.time
        self.ledger=bg.prior.UsageLedger(self.path/'ledger.sqlite3',clock=self.clock)
        self.batch=bg.transport.Batch('test-background',('case',),200_000_000,0,200_000_000)
        self.ident=self.batch.operation_id('case');self.p=prior_run.selected('extract')
        self.body=bg.prior.body(self.p,'test','{}',{'type':'object','properties':{},'required':[],'additionalProperties':False},'test')
        self.calls=[]
    def sleep(self,seconds):self.time+=seconds
    def response(self,status='completed',**kw):
        return {'id':'resp_safe123','status':status,'model':self.p['model'],'service_tier':'default','usage':{'input_tokens':100,'output_tokens':20},
            'output':[{'type':'message','content':[{'type':'output_text','text':'{}'}]}],**kw}
    def send(self,method,suffix,key,body):
        self.calls.append((method,suffix))
        self.assertEqual(key,'fake-credential')
        if suffix=='':self.assertTrue(body['background']);self.assertFalse(body['store'])
        return self.response('queued' if not suffix else 'completed')
    def call(self,sender=None,body=None):
        return bg.dispatch(self.ident,self.p,body or self.body,self.path/'job',self.ledger,'fake-credential',self.batch,
            sender=sender or self.send,counter=lambda *_:100,clock=self.clock,sleeper=self.sleep)
    def test_count_adapter_keeps_exact_input_fields_without_generation_flags(self):
        def count(key,body):
            self.assertEqual(body,self.body);self.assertNotIn('background',body);self.assertNotIn('metadata',body)
            return 100
        bg.dispatch(self.ident,self.p,self.body,self.path/'job',self.ledger,'fake-credential',self.batch,sender=self.send,counter=count,clock=self.clock,sleeper=self.sleep)

    def test_poll_settle_and_resume_without_new_creation(self):
        raw,meta=self.call();self.assertEqual(raw,{})
        self.assertEqual(self.calls,[('POST',''),('GET','/resp_safe123')]);before=self.ledger.get(self.ident)
        self.call();self.assertEqual(len(self.calls),2);self.assertEqual(before,self.ledger.get(self.ident))
        self.assertEqual(meta['creation_calls'],1)
        for p in (self.path/'job').glob('*.json'):self.assertNotIn('fake-credential',p.read_text())
    def test_get_timeout_is_recoverable_with_same_id_and_reservation(self):
        def sender(m,s,k,b):
            if s:raise TimeoutError('fake-credential')
            return self.send(m,s,k,b)
        with self.assertRaises(bg.Pending):self.call(sender)
        self.assertEqual(self.ledger.get(self.ident)['status'],'reserved')
        self.call();self.assertEqual(sum(m=='POST' and s=='' for m,s in self.calls),1)
        self.assertEqual(self.ledger.get(self.ident)['status'],'completed')
    def test_post_timeout_without_id_is_never_retried(self):
        calls=[]
        def failed(*args):calls.append(1);raise TimeoutError('fake-credential')
        with self.assertRaises(bg.prior.CommandError):self.call(failed)
        with self.assertRaises(bg.prior.CommandError):self.call(failed)
        self.assertEqual(len(calls),1);self.assertEqual(self.ledger.get(self.ident)['status'],'uncertain')
    def test_changed_request_and_different_journal_cannot_repeat(self):
        self.call();changed=deepcopy(self.body);changed['input'][1]['content']='changed'
        with self.assertRaises(bg.prior.CommandError):self.call(body=changed)
        with self.assertRaises(bg.prior.CommandError):bg.dispatch(self.ident,self.p,self.body,self.path/'new',self.ledger,'fake-credential',self.batch,sender=self.send,counter=lambda *_:100)
        self.assertEqual(len(self.calls),2)
    def test_budget_and_unknown_operation_stop_before_dispatch(self):
        with patch.object(bg.transport.Batch,'spent',return_value=self.batch.budget),self.assertRaises(bg.prior.CommandError):self.call()
        with self.assertRaises(bg.prior.CommandError):bg.dispatch('wrong',self.p,self.body,self.path/'new',self.ledger,'fake',self.batch,sender=self.send)
        self.assertEqual(self.calls,[])
    def test_deadline_cancels_known_job_without_new_generation(self):
        def sender(m,s,k,b):
            self.calls.append((m,s))
            if not s:self.time+=365;return self.response('in_progress')
            return self.response('cancelled')
        with self.assertRaises(ValueError):self.call(sender)
        self.assertEqual(self.calls,[('POST',''),('POST','/resp_safe123/cancel')])
        self.assertEqual(self.ledger.get(self.ident)['status'],'completed')
    def test_terminal_write_crash_can_retrieve_existing_job(self):
        def sender(m,s,k,b):
            if not s:return self.response('queued')
            return self.response()
        original=bg.save
        def fail(path,value):
            if path.name=='response.json':raise OSError('interruption')
            return original(path,value)
        with patch.object(bg,'save',fail),self.assertRaises(OSError):self.call(sender)
        _,meta=self.call();self.assertEqual(self.calls,[('GET','/resp_safe123')]);self.assertEqual(meta['creation_calls'],1)
    def test_non_object_response_halts_without_repeat(self):
        with self.assertRaises(bg.prior.CommandError):self.call(lambda *args:[])
        self.assertTrue(self.ledger.summary()['halted'])
        self.assertEqual(self.ledger.get(self.ident)['status'],'uncertain')

    def test_wrong_response_identity_or_billing_halts(self):
        def sender(m,s,k,b):return self.response('queued' if not s else 'completed',id='resp_first' if not s else 'resp_other')
        with self.assertRaises(bg.prior.CommandError):self.call(sender)
        self.assertTrue(self.ledger.summary()['halted'])
    def test_schema_incomplete_is_settled_and_never_regenerated(self):
        with self.assertRaises(ValueError):self.call(lambda *args:self.response('incomplete'))
        with self.assertRaises(ValueError):self.call()
        self.assertEqual(self.calls,[]);self.assertEqual(self.ledger.get(self.ident)['status'],'completed')
    def test_terminal_missing_usage_keeps_money_and_halts(self):
        with self.assertRaises(bg.prior.CommandError):self.call(lambda *args:self.response(usage=None))
        self.assertTrue(self.ledger.summary()['halted']);self.assertEqual(self.ledger.get(self.ident)['status'],'uncertain')

if __name__=='__main__':unittest.main()
