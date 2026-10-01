from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from Research.native_objects import strong_model_experiment as run

class StrongModelTests(unittest.TestCase):
    def test_research_allowance_preserves_routine_limits(self):
        p=run.selected();self.assertEqual((p['model'],p['effort'],p['max_output_tokens']),('gpt-6-astra','xhigh',32768))
        self.assertEqual(run.prior.quote_cost(p,32768),2048000000)
        self.assertLessEqual(run.prior.quote_cost(p,32768),p['ceiling_nanos'])
        for count in (True,32769,0,None):
            with self.assertRaises(run.prior.CommandError):run.prior.quote_cost(p,count)
        routine=run.prior.policy('openai','routine',run.prior.PRICE_EXPIRES-1)
        self.assertEqual(routine['model'],'gpt-6-sol');self.assertEqual(routine['max_output_tokens'],1024)
        with self.assertRaises(run.prior.CommandError):run.prior.quote_cost(routine,16001)
        self.assertEqual(run.BATCH.budget,10_000_000_000)
        self.assertLessEqual(run.BATCH.budget+run.BATCH.prior_upper_bound,run.BATCH.aggregate_limit)

    def test_identical_prompt_and_schema_except_capacity(self):
        spec=run.baseline.SPECS[-1];context={'original_request':spec['request'],'proposed_role_groups':spec['roles']}
        _,old=run.baseline.body_for('extract',context);_,body,_=run.body_for('extract',context)
        self.assertTrue(run.capacity_audit(old,body)['input_identical'])
        for field,value in [('input',[]),('text',{}),('store',True)]:
            bad=deepcopy(body);bad[field]=value
            with self.assertRaises(run.prior.CommandError):run.capacity_audit(old,bad)

    def test_long_deadline_only_for_reviewed_research_profile(self):
        bg=run.baseline.background
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);now=[run.prior.PRICE_EXPIRES-2000];clock=lambda:now[0]
            ledger=run.prior.UsageLedger(folder/'ledger.sqlite3',clock=clock)
            batch=run.baseline.previous.transport.Batch('test-strong',('one',),3_000_000_000,0,3_000_000_000)
            p=run.selected();calls=[]
            spec=run.baseline.SPECS[-1];_,body,_=run.body_for('extract',{'original_request':spec['request'],'proposed_role_groups':spec['roles']})
            def send(method,suffix,key,payload):
                calls.append((method,suffix));now[0]+=400 if not suffix else 0
                return {'id':'resp_test','status':'queued' if not suffix else 'completed','model':p['model'],'service_tier':'default',
                    'usage':{'input_tokens':100,'output_tokens':20},'output':[{'type':'message','content':[{'type':'output_text','text':'{}'}]}]}
            def sleep(seconds):now[0]+=seconds
            bg.dispatch(batch.operation_id('one'),p,body,folder/'job',ledger,'fake',batch,sender=send,counter=lambda *_:100,clock=clock,sleeper=sleep,wait_seconds=900)
            self.assertEqual(calls,[('POST',''),('GET','/resp_test')])
            before=len(calls)
            with self.assertRaisesRegex(run.prior.CommandError,'Unreviewed background wait policy'):
                bg.dispatch(batch.operation_id('one'),run.baseline.selected('plan'),body,folder/'bad',ledger,'fake',batch,wait_seconds=900,sender=send)
            self.assertEqual(len(calls),before)

    def test_completed_wrong_plans_keep_gates_and_no_extra_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);evaluate=run.baseline.pipeline.evaluate_candidate
            def no_render(*args,**kw):kw['renderer']=lambda _:None;return evaluate(*args,**kw)
            with patch.object(run.baseline.pipeline,'evaluate_candidate',side_effect=no_render):states=run.baseline.initialize(folder)
            protocol={'files_sha256':run.frozen_sources()};ledger=run.prior.UsageLedger(folder/'ledger.sqlite3');calls=[]
            def send(ident,p,body,*args,**kw):
                self.assertEqual(kw['wait_seconds'],900);calls.append(ident)
                op=next(o for o in run.OPERATIONS if run.BATCH.operation_id(o)==ident)
                files={
                    'generic-drone/plan/0':'repair-012/generic-drone-plan-0/compact-plan.json',
                    'generic-drone/patch/1':'repair-013/generic-drone-plan-1/patch.json',
                    'two-driver-speaker/extract/0':'repair-012/two-driver-speaker-extract/compact-inventory.json',
                    'cooling-fan-row/patch/1':'repair-012/cooling-fan-row-plan-1/patch.json'}
                result=json.loads((run.SOURCE/'results'/files[op]).read_text())
                return result,{'dispatch_seconds':1,'usage':{'input_tokens':100,'output_tokens':20},'calculated_cost_nanos':1000}
            with patch.object(run.baseline.pipeline,'evaluate_candidate',side_effect=no_render),patch.object(run.baseline.background,'dispatch',side_effect=send),patch.object(run,'comparison_audit',return_value={'input_identical':True}):
                run.run(folder,states,protocol,ledger,'fake')
                self.assertEqual(len(calls),4);self.assertEqual(states['generic-drone']['status'],'geometry_failed')
                self.assertEqual(states['two-driver-speaker']['status'],'unsupported_before_planning')
                self.assertEqual(states['cooling-fan-row']['status'],'structural_candidate')
                run.run(folder,states,protocol,ledger,'fake');self.assertEqual(len(calls),4)

if __name__=='__main__':unittest.main()
