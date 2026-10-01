from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from Research.native_objects import strong_model_continuation as run

class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
    def stopped_ledger(self):
        job=self.path/'job';shutil.copytree(run.FAILED,job)
        evidence=run.funding_evidence(job)
        ledger=run.prior.UsageLedger(self.path/'ledger.sqlite3');p=run.previous.selected();now=int(ledger.clock())
        q={'request_id':evidence['operation_id'],'actor_id':'developer','provider':'openai','profile':p['profile'],'model':p['model'],'effort':p['effort'],
            'operation':'strong-model-014','fingerprint':evidence['body_sha256'],'price_version':p['price_version'],'input_tokens':20099,
            'max_output_tokens':p['max_output_tokens'],'reserved_nanos':run.prior.quote_cost(p,20099),'ceiling_nanos':p['ceiling_nanos'],'created':now,'expires':now+120}
        ledger.create_quote(q);ledger.reserve(q['request_id'],'developer',q['fingerprint'],q['reserved_nanos']);ledger.uncertain(q['request_id'],halt=True)
        return ledger,evidence,job
    def test_review_keeps_every_accounting_field_and_is_idempotent(self):
        ledger,evidence,_=self.stopped_ledger();before=ledger.get(evidence['operation_id']);amount=ledger.summary()['charged_and_reserved_nanos']
        audit=run.restore_admission(ledger,self.path/'review.json',evidence)
        self.assertFalse(ledger.summary()['halted']);self.assertEqual(before,ledger.get(evidence['operation_id']))
        self.assertEqual(ledger.summary()['charged_and_reserved_nanos'],amount);self.assertEqual(audit['released_nanos'],0)
        self.assertEqual(audit,run.restore_admission(ledger,self.path/'review.json',evidence))
    def test_failed_response_must_be_exact_empty_terminal_funding_failure(self):
        _,_,folder=self.stopped_ledger();original=run.read(folder/'response.json')
        variants=[dict(original,status='completed'),dict(original,usage={'input_tokens':1}),dict(original,error={'code':'server_error'}),dict(original,output=[{'type':'reasoning'}])]
        for bad in variants:
            (folder/'response.json').write_text(json.dumps(bad))
            with self.assertRaises(run.prior.CommandError):run.funding_evidence(folder,run.sha(folder/'response.json'))
        (folder/'response.json').write_text(json.dumps(original))
        with self.assertRaises(run.prior.CommandError):run.funding_evidence(folder) # Exact retained bytes, not just semantic equality.
    def test_later_failure_cannot_be_unhalted_by_old_review(self):
        ledger,evidence,_=self.stopped_ledger();old=ledger.get(evidence['operation_id'])
        with ledger.transaction() as db:db.execute('UPDATE usage SET finished=finished-1 WHERE request_id=?',(evidence['operation_id'],))
        # A second affected request is enough to make the cause ambiguous.
        with ledger.transaction() as db:
            cols=list(old);values=[old[k] for k in cols];values[cols.index('request_id')]='different'
            db.execute('INSERT INTO usage ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',values)
        with self.assertRaises(run.prior.CommandError):run.restore_admission(ledger,self.path/'review.json',evidence)
        self.assertTrue(ledger.summary()['halted'])
    def test_interrupted_review_recovers_but_new_halt_requires_new_review(self):
        ledger,evidence,_=self.stopped_ledger();path=self.path/'review.json';run.restore_admission(ledger,path,evidence)
        audit=run.read(path);audit['status']='prepared';path.write_text(json.dumps(audit))
        self.assertEqual(run.restore_admission(ledger,path,evidence)['status'],'completed')
        with ledger.transaction() as db:db.execute('UPDATE control SET halted=1 WHERE id=1')
        with self.assertRaises(run.prior.CommandError):run.restore_admission(ledger,path,evidence)
        self.assertTrue(ledger.summary()['halted'])
    def test_changed_hold_is_never_released(self):
        ledger,evidence,_=self.stopped_ledger()
        with ledger.transaction() as db:db.execute('UPDATE usage SET charged_nanos=charged_nanos-1 WHERE request_id=?',(evidence['operation_id'],))
        with self.assertRaises(run.prior.CommandError):run.restore_admission(ledger,self.path/'review.json',evidence)
        self.assertTrue(ledger.summary()['halted'])
    def test_copy_and_fixed_prompts_are_unchanged(self):
        states=run.prepare(self.path);rows=list(run.remaining_bodies(self.path,states));self.assertEqual(len(rows),3)
        self.assertTrue(all(a['input_identical'] for _,_,_,a in rows))
        self.assertEqual(run.sha(self.path/'generic-drone-plan-0/package.json'),run.sha(run.PARENT/'generic-drone-plan-0/package.json'))
        self.assertNotIn('generic-drone/plan/0',run.OPERATIONS)
    def test_whole_remaining_budget_includes_failed_hold_and_conditional_call(self):
        states=run.prepare(self.path)
        class Ledger:
            def summary(self):return {'remaining_nanos':8_809_877_500,'halted':True}
        counts=iter([20099,3913,13371])
        def spent(batch,ledger):return 2_921_787_500 if batch.experiment=='strong-model-014' else 0
        with patch.object(run.prior,'count_input',side_effect=lambda *_:next(counts)),patch.object(run.previous.BATCH.__class__,'spent',spent):
            audit=run.preflight(self.path,states,'fake',Ledger(),allow_reviewed_halt=True)
        self.assertEqual(audit['whole_batch_maximum_nanos'],7_430_487_500)
        self.assertEqual(audit['combined_comparison_worst_with_old_hold_nanos'],10_352_275_000)
        self.assertLessEqual(audit['whole_batch_maximum_nanos']+run.BATCH.prior_upper_bound,run.BATCH.aggregate_limit)
    def test_continuation_never_regenerates_initial_drone_or_completed_operations(self):
        states=run.prepare(self.path);protocol={'files_sha256':run.frozen_sources()};ledger=run.prior.UsageLedger(self.path/'ledger.sqlite3');calls=[]
        def send(ident,p,body,*args,**kw):
            op=next(o for o in run.OPERATIONS if run.BATCH.operation_id(o)==ident);calls.append(op)
            if op.endswith('extract/0'):result=run.read(run.SOURCE/'results/repair-012/two-driver-speaker-extract/compact-inventory.json')
            else:
                context=json.loads(body['input'][1]['content']);result={'base_sha256':context['repair_scope']['base_sha256'],'status':'unsupported','reason':'test boundary','shapes':[],'ports':[]}
            return result,{'dispatch_seconds':1,'usage':{'input_tokens':100,'output_tokens':20},'calculated_cost_nanos':1000}
        with patch.object(run.baseline.background,'dispatch',side_effect=send):
            run.previous.run(self.path,states,protocol,ledger,'fake',batch=run.BATCH,operation_order=run.OPERATIONS,snapshot=run.frozen_sources)
            self.assertEqual(calls,['generic-drone/patch/1','two-driver-speaker/extract/0','cooling-fan-row/patch/1'])
            run.previous.run(self.path,states,protocol,ledger,'fake',batch=run.BATCH,operation_order=run.OPERATIONS,snapshot=run.frozen_sources)
            self.assertEqual(len(calls),3)
        self.assertEqual(states['generic-drone']['status'],'repair_unsupported')

if __name__=='__main__':unittest.main()
