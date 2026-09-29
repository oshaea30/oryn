"""Fixture-only follow-up assessments. No actual reference or model requests."""
from copy import deepcopy
import json
from types import SimpleNamespace
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import urllib.request
import urllib.error
from pathlib import Path

from assessment_provider import OpenAIAssessmentProvider,validate_assessments
from candidate_assessment import CandidateAssessmentService,search_plan,select_references
from cognition import CommandError
from investigation import validate_sources
from test_investigation import source
import test_vision_episodes as vision_fixtures


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        f=self.f=vision_fixtures.VisionEpisodeTests();f.setUp();self.addCleanup(f.doCleanups)
        f.episodes.retain_observations(f.episode['id'],f.package,f.images)
        self.revision=f.publish();self.original=deepcopy(self.revision)
        self.refs=validate_sources([source('ref2',title='Crankshaft construction',excerpt='A crankshaft converts reciprocating motion into rotation.')])
        self.retrieval=Mock();self.retrieval.retrieve.return_value=self.refs
        self.counter=Mock(return_value=1000);self.sender=Mock(side_effect=self.response)
        self.provider=OpenAIAssessmentProvider(f.ledger,'PRIVATE_FIXTURE',self.counter,self.sender,clock=lambda:f.now)
        research=SimpleNamespace(key='PRIVATE_FIXTURE',budget_error='',ledger=f.ledger,lock=threading.Lock())
        self.jobs=SimpleNamespace(workflows=f.store,episodes=f.episodes,geometry_evidence=f.geometry,research=research,
                                 vision=SimpleNamespace(state=lambda:{'policy_ready':True}))
        self.service=CandidateAssessmentService(self.jobs,self.retrieval,lambda ledger,key:self.provider)

    def output(self):
        return {'assessments':[{'geometry_id':'p1','outcome':'insufficient_evidence',
            'observation':'Fixture silhouette does not establish a shaft.',
            'comparison':'Reference describes motion, not this surface.',
            'view_ids':['v1'],'missing_evidence':['A component-specific drawing.'],
            'evidence':[{'source_id':'ref2','quote':'A crankshaft converts reciprocating motion into rotation.'}]}]}

    def response(self,*args):
        result=self.f.response();result['output'][1]['content'][0]['text']=json.dumps(self.output());return result

    def run_service(self):
        result=self.service.start_episode(self.f.episode['id'])
        if self.service.thread:self.service.thread.join(5)
        return result,self.service.get(self.f.episode['id'])

    def test_saved_candidate_assessment_is_additive_and_budgeted(self):
        response,record=self.run_service()
        self.assertTrue(response['dispatched']);self.assertEqual(record['status'],'completed')
        self.assertEqual(record['assessments'][0]['epistemic_status'],'candidate')
        self.assertEqual(record['assessments'][0]['outcome'],'insufficient_evidence')
        self.assertEqual(self.f.geometry.report(self.f.package['id'])['candidate_revisions'],[self.original])
        self.assertEqual(self.f.episodes.get(self.f.episode['id'])['status'],'completed')
        self.assertEqual(self.f.ledger.get(record['operation_id'])['operation'],'candidate_reference_assessment')
        self.assertEqual(self.f.ledger.investigation_summary(record['asset_id'])['charged_and_reserved_nanos'],9_000_000)
        body=self.sender.call_args.args[1]
        self.assertFalse(body['store']);self.assertNotIn('tools',body);self.assertEqual(body['max_output_tokens'],1536)
        self.assertEqual(len([p for p in body['input'][1]['content'] if p['type']=='input_image']),1)
        history=json.dumps(self.f.episodes.events(self.f.episode['id']))
        self.assertNotIn('PRIVATE_FIXTURE',history);self.assertNotIn('DO_NOT_STORE_REASONING',history)
        self.assertIn('assessment_reference_triage',history)

    def test_duplicate_requests_and_restart_never_repeat_assessment(self):
        self.run_service()
        restarted=CandidateAssessmentService(self.jobs,self.retrieval,lambda ledger,key:self.provider)
        self.assertFalse(restarted.start_episode(self.f.episode['id'])['dispatched'])
        self.sender.assert_called_once();self.counter.assert_called_once()
        self.assertLessEqual(self.retrieval.retrieve.call_count,2)

    def test_no_new_references_preserves_unknown_without_paid_call(self):
        self.retrieval.retrieve.return_value=self.f.sources
        _,record=self.run_service()
        self.assertEqual(record['status'],'completed');self.assertEqual(record['assessments'][0]['outcome'],'insufficient_evidence')
        self.sender.assert_not_called();self.counter.assert_not_called()

    def test_retrieval_failure_is_recorded_no_retry(self):
        self.retrieval.retrieve.side_effect=RuntimeError('PRIVATE_FIXTURE')
        _,record=self.run_service();self.assertEqual(record['status'],'failed')
        self.assertNotIn('PRIVATE_FIXTURE',record['error']);self.assertFalse(self.service.start_episode(self.f.episode['id'])['dispatched'])
        self.retrieval.retrieve.assert_called_once();self.sender.assert_not_called()

    def test_failed_generation_keeps_reservation_and_original_candidate(self):
        self.sender.side_effect=TimeoutError()
        _,record=self.run_service();self.assertEqual(record['status'],'failed')
        self.assertEqual(self.f.ledger.get(record['operation_id'])['status'],'uncertain')
        self.assertFalse(self.service.start_episode(self.f.episode['id'])['dispatched']);self.sender.assert_called_once()
        self.assertEqual(self.f.geometry.report(self.f.package['id'])['candidate_revisions'],[self.original])

    def test_validation_rejects_false_quotes_missing_bindings_and_promotions(self):
        for mutate in (
            lambda a:a.update(outcome='verified'),lambda a:a.update(epistemic_status='reference-supported'),
            lambda a:a.update(evidence=[{'source_id':'ref2','quote':'Fabricated reference quote'}]),
            lambda a:a.update(view_ids=['v99']),lambda a:a.update(outcome='supports_candidate',evidence=[]),
            lambda a:a.update(missing_evidence=[])):
            with self.subTest(mutation=mutate):
                value=self.output();mutate(value['assessments'][0])
                with self.assertRaises((ValueError,KeyError)):
                    self.provider.validate_result(value,{'p1':self.f.targets[0]},{'v1':self.f.package['views'][0]['view_id']},
                        {**self.f.package,'targets':[self.f.targets[0]]},self.refs,{'provider':'fixture'})

    def test_invalid_output_retained_but_not_applied(self):
        response=self.response();value=self.output();value['assessments'][0]['outcome']='verified'
        response['output'][1]['content'][0]['text']=json.dumps(value)
        self.sender.side_effect=None;self.sender.return_value=response
        _,record=self.run_service();self.assertEqual(record['status'],'failed')
        kinds=[e['kind'] for e in self.f.episodes.events(self.f.episode['id'])]
        self.assertIn('assessment_provider_response',kinds);self.assertIn('assessment_validation_rejected',kinds)
        self.assertEqual(record['assessments'],[])

    def test_key_policy_required_before_external_work(self):
        self.jobs.vision.state=lambda:{'policy_ready':False}
        with self.assertRaises(ValueError):self.service.start_episode(self.f.episode['id'])
        self.retrieval.retrieve.assert_not_called();self.sender.assert_not_called()

    def test_lexical_plan_and_triage_do_not_claim_authority(self):
        candidates=[{'candidate_name':'Cylinder-bank upper cover'}]*2
        queries=search_plan('V8 engine',candidates)
        self.assertEqual(queries,['v8 engine cylinder bank upper cover','engine cover'])
        refs=validate_sources([source('ref2',title='Rocker covers',excerpt='A cover encloses engine parts.'),source('ref3',title='Unrelated',excerpt='An unrelated subject.')])
        selected,decision=select_references([refs,refs],candidates,[])
        self.assertEqual([s['id'] for s in selected],['ref2']);self.assertEqual(len(decision['decisions']),2)
        self.assertEqual(decision['cost_nanos'],0);self.assertFalse(decision['decisions'][0]['authority_verified'])

    def test_new_reference_ids_can_support_later_human_correction(self):
        self.run_service()
        body={'request_id':'d'*32,'revision_id':self.revision['id'],'geometry_id':self.f.targets[0],
            'decision':'rejected','reason':'Fixture-only conflicting observation.','replacement_name':'',
            'source_ids':['ref2'],'previous_review_id':None}
        self.f.episodes.review(self.f.episode['id'],body,self.f.geometry)
        self.assertEqual(self.f.geometry.report(self.f.package['id'])['candidate_revisions'],[self.original])

    def test_cumulative_prior_usage_blocks_assessment_generation(self):
        ledger=self.f.ledger;op='e'*32;amount=35_000_000
        ledger.create_quote({'request_id':op,'actor_id':'developer','provider':'openai','profile':'fixture',
            'model':'gpt-6-sol','effort':'medium','operation':'fixture','fingerprint':'fixture','price_version':'fixture',
            'input_tokens':1000,'max_output_tokens':1024,'reserved_nanos':amount,'ceiling_nanos':50_000_000,
            'created':self.f.now,'expires':self.f.now+120})
        ledger.reserve(op,'developer','fixture',amount,investigation_id=self.f.manifest['asset_id'])
        _,record=self.run_service();self.assertEqual(record['status'],'failed');self.sender.assert_not_called()
        self.assertEqual(ledger.investigation_summary(record['asset_id'])['charged_and_reserved_nanos'],39_500_000)

    def test_concurrent_requests_claim_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.service.start_episode(self.f.episode['id']),range(2)))
        self.service.thread.join(5)
        self.assertEqual(sum(r['dispatched'] for r in results),1);self.sender.assert_called_once()

    def test_interrupted_assessment_never_resubmits(self):
        from unittest.mock import patch
        with patch('candidate_assessment.threading.Thread.start'):
            self.service.start_episode(self.f.episode['id'])
        restarted=CandidateAssessmentService(self.jobs,self.retrieval,lambda ledger,key:self.provider)
        self.assertEqual(restarted.get(self.f.episode['id'])['status'],'interrupted')
        self.assertFalse(restarted.start_episode(self.f.episode['id'])['dispatched'])
        self.retrieval.retrieve.assert_not_called();self.sender.assert_not_called()

    def test_http_assessment_auth_and_read_only_history(self):
        from app import Jobs,Server
        jobs=Jobs(Path(self.f.tmp.name)/'http-jobs',Path(self.f.tmp.name)/'model.glb')
        jobs.episodes=self.f.episodes;jobs.geometry_evidence=self.f.geometry;jobs.assessments=self.service
        server=Server(0,jobs);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            body={'episode_id':self.f.episode['id']}
            def post(token,origin):
                return urllib.request.urlopen(urllib.request.Request(server.origin+'/api/assess-candidates',
                    data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Oryn-Token':token,'Origin':origin},method='POST'))
            for token,origin in (('',server.origin),(server.token,'https://untrusted.invalid')):
                with self.assertRaises(urllib.error.HTTPError) as error:post(token,origin)
                self.assertEqual(error.exception.code,403);error.exception.close()
            self.retrieval.retrieve.assert_not_called()
            with post(server.token,server.origin) as response:self.assertEqual(response.status,202)
            self.service.thread.join(5)
            with urllib.request.urlopen(server.origin+'/api/episode?id='+body['episode_id']) as response:
                self.assertEqual(json.load(response)['assessment']['status'],'completed')
            self.sender.assert_called_once()
        finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()
