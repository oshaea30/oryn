"""Offline only: synthetic responses test contracts, never semantic intelligence."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from cognition import CommandError
from object_planning import build_request,planning_body,validate_plan,ObjectPlanner,OpenAIObjectPlanner
from spending import policy,PRICE_REVIEWED,PRICE_EXPIRES
from usage_ledger import UsageLedger
from test_investigation import source


def plan():
    return {'object':'test concept','fidelity':'generic_design','intent':'inspect','depth':'major_components',
        'detail_reason':'Only major functional groups requested.','next_step':'propose_geometry','retrieval':'none',
        'components':[{'name':'housing','basis':'design_proposal','source_ids':[]}],
        'assumptions':['A proposed design, not a real product.'],'unknowns':['Geometry and fit not tested.']}


class PlanTests(unittest.TestCase):
    def setUp(self):self.request=build_request('A generic object')
    def validate(self,p):return validate_plan(p,self.request,self.request)
    def test_candidate_never_authorizes_generation_or_execution(self):
        r=self.validate(plan());self.assertEqual(r['status'],'candidate')
        self.assertFalse(r['generation_allowed']);self.assertFalse(r['execution_allowed'])
        self.assertEqual(r['semantic_quality'],'not_assessed')
    def test_stale_request_or_evidence_rejected(self):
        for now in (build_request('Another object'),build_request('A generic object',[source()])):
            with self.assertRaises(CommandError):validate_plan(plan(),self.request,now)
    def test_reference_snapshot_cannot_be_changed_undetected(self):
        req=build_request('A generic object',[source()]);req['context']['sources'][0]['excerpt']='Changed'
        with self.assertRaises(CommandError):planning_body(policy('openai','planning',PRICE_REVIEWED),req)
    def test_invented_citations_and_citation_laundering_rejected(self):
        for basis,ids in [('reference_candidate',['made-up']),('reference_candidate',[]),('design_proposal',['made-up'])]:
            p=plan();p['components'][0].update(basis=basis,source_ids=ids)
            with self.assertRaises(CommandError):self.validate(p)
    def test_exact_without_matching_evidence_cannot_invent_components(self):
        p=plan();p.update(fidelity='exact_product',next_step='retrieve_evidence',retrieval='exact_documents')
        with self.assertRaises(CommandError):self.validate(p)
        p['components']=[];self.assertEqual(self.validate(p)['plan']['next_step'],'retrieve_evidence')
    def test_matching_reference_still_not_verified_or_generation_ready(self):
        s=source();s.update(object_match=True,revision_match=True)
        req=build_request('Specific item',[s]);p=plan();p.update(fidelity='exact_product',next_step='retrieve_evidence',retrieval='exact_documents')
        p['components'][0].update(basis='reference_candidate',source_ids=[s['id']])
        r=validate_plan(p,req,req);self.assertFalse(r['generation_allowed'])
        self.assertEqual(r['evidence_status'],'citation_membership_checked_not_entailment')
        p['next_step']='propose_geometry'
        with self.assertRaises(CommandError):validate_plan(p,req,req)
    def test_unknown_revision_cannot_support_exact_component(self):
        s=source();s['object_match']=True;req=build_request('Exact',[s]);p=plan()
        p.update(fidelity='exact_product',next_step='retrieve_evidence',retrieval='exact_documents')
        p['components'][0].update(basis='reference_candidate',source_ids=[s['id']])
        with self.assertRaises(CommandError):validate_plan(p,req,req)
    def test_repair_and_simulation_do_not_proceed_on_plausibility(self):
        for intent in ('repair','simulate'):
            p=plan();p['intent']=intent
            with self.assertRaises(CommandError):self.validate(p)
    def test_bounds_unknowns_and_duplicate_names(self):
        for field,value in [('components',plan()['components']*2),('unknowns',[]),('components',[plan()['components'][0]]*11),('fidelity','verified')]:
            p=plan();p[field]=value
            with self.assertRaises(CommandError):self.validate(p)
    def test_no_model_fixture_fallback(self):
        with self.assertRaises(CommandError):ObjectPlanner(None).plan('thing',current_context=lambda:('thing',[]))
    def test_adapter_context_is_copied_and_rechecked(self):
        r=ObjectPlanner(lambda req:plan()).plan('anything',current_context=lambda:('anything',[]))
        self.assertEqual(r['plan'],plan())
        with self.assertRaises(CommandError):ObjectPlanner(lambda req:plan()).plan('anything',current_context=lambda:('changed',[]))


class PaidPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.now=PRICE_REVIEWED+3600
        self.ledger=UsageLedger(Path(self.temp.name)/'usage.sqlite3',clock=lambda:self.now)
        self.counter=Mock(return_value=1000);self.sender=Mock(side_effect=self.response)
        self.provider=OpenAIObjectPlanner(self.ledger,'SECRET_FIXTURE',self.counter,self.sender,clock=lambda:self.now)
    def tearDown(self):self.temp.cleanup()
    def response(self,*args):
        self.assertEqual(self.ledger.get('a'*32)['status'],'reserved')
        return {'status':'completed','model':'gpt-6-sol','service_tier':'default',
            'usage':{'input_tokens':1000,'output_tokens':400},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(plan())}]}]}
    def call(self):return self.provider.plan('a'*32,'generic object',current_context=lambda:('generic object',[]))
    def test_exact_count_reserve_settle_same_ledger_and_no_replay(self):
        result=self.call();self.assertEqual(result['cost']['calculated_nanos'],6_500_000)
        self.assertIsNone(result['cost']['actual_nanos']);self.assertNotIn(b'SECRET_FIXTURE',self.ledger.path.read_bytes())
        with self.assertRaises(CommandError):self.call()
        self.counter.assert_called_once();self.sender.assert_called_once()
    def test_body_is_tools_free_and_excludes_evaluation_answers(self):
        self.call();body=self.sender.call_args.args[1]
        self.assertEqual(body['max_output_tokens'],2048);self.assertNotIn('tools',body);self.assertFalse(body['store'])
        self.assertEqual(set(json.loads(body['input'][1]['content'])),{'request','local_evidence'})
    def test_timeout_retains_reservation_and_hides_provider_errors(self):
        self.sender.side_effect=RuntimeError('SECRET_FIXTURE')
        with self.assertRaises(CommandError) as e:self.call()
        self.assertNotIn('SECRET_FIXTURE',str(e.exception));self.assertEqual(self.ledger.get('a'*32)['status'],'uncertain')
        with self.assertRaises(CommandError):self.call()
        self.sender.assert_called_once()
    def test_model_mismatch_halts_paid_cognition(self):
        response=self.response_without_reservation();response['model']='other';self.sender.side_effect=None;self.sender.return_value=response
        with self.assertRaises(CommandError):self.call()
        self.assertTrue(self.ledger.summary()['halted'])
    def response_without_reservation(self):
        return {'status':'completed','model':'gpt-6-sol','service_tier':'default','usage':{'input_tokens':1000,'output_tokens':400},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(plan())}]}]}
    def test_incomplete_or_invalid_output_accounts_usage_without_retry(self):
        response=self.response_without_reservation();response['status']='incomplete';self.sender.side_effect=None;self.sender.return_value=response
        with self.assertRaises(CommandError):self.call()
        self.assertEqual(self.ledger.get('a'*32)['outcome'],'invalid_response')
        self.assertEqual(self.ledger.get('a'*32)['calculated_cost_nanos'],6_500_000)
    def test_stale_paid_response_is_settled_but_not_published(self):
        with self.assertRaises(CommandError):self.provider.plan('a'*32,'generic object',current_context=lambda:('changed',[]))
        self.assertEqual(self.ledger.get('a'*32)['outcome'],'invalid_response')
    def test_expiry_halt_and_cost_limit_prevent_dispatch(self):
        self.now=PRICE_EXPIRES
        with self.assertRaises(CommandError):self.call()
        self.counter.assert_not_called();self.sender.assert_not_called()
        self.now=PRICE_REVIEWED+3600;self.counter.return_value=16000
        with self.assertRaises(CommandError):self.call()
        self.sender.assert_not_called()
        self.counter.return_value=1000
        with self.ledger.transaction() as db:db.execute('UPDATE control SET halted=1')
        with self.assertRaises(CommandError):self.call()
        self.sender.assert_not_called()

class BatchTests(unittest.TestCase):
    def protocol(self):
        root=Path(__file__).resolve().parents[1]
        return json.loads((root/'Research/native_objects/planning_cases_001.json').read_text())
    def test_frozen_review_criteria_never_enter_model_body(self):
        from Research.native_objects.planning_experiment import prepare
        protocol=self.protocol()
        with patch('Research.native_objects.planning_experiment.time.time',return_value=PRICE_REVIEWED+100):
            record=prepare(protocol)
        self.assertEqual(len(record['items']),4)
        self.assertFalse(record['execution_requested'])
        for case,item in zip(protocol['cases'],record['items']):
            body=json.dumps(item['body'])
            for criterion in case['review']:self.assertNotIn(criterion,body)
            self.assertEqual(item['body']['input'][0],record['items'][0]['body']['input'][0])
    def test_batch_rejects_expanded_cost_or_case_count(self):
        from Research.native_objects.planning_experiment import prepare
        for field,value in [('max_calls',5),('max_cost_usd',0.21),('cases',[])]:
            protocol=self.protocol();protocol[field]=value
            with self.assertRaises(ValueError):prepare(protocol)

if __name__=='__main__':unittest.main()

