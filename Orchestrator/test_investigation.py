"""All providers are in-memory fixtures: no network, keys or paid requests."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from ingestion import ingest
from investigation import Investigations, validate_sources, validate_findings
from test_mesh_islands import fixture
from workflow import WorkflowStore


def source(identifier='ref1', **overrides):
    return dict({'id':identifier,'title':'Fixture engine reference','url':'https://example.org/engine',
                 'excerpt':'This fixture engine contains a crankshaft.','source_type':'test_fixture',
                 'retrieved_at':1790467200,'object_revision':None,'object_match':None,'revision_match':None},**overrides)


def findings(identifier='ref1'):
    return {'overview':[{'text':'The reference describes an engine.','source_ids':[identifier]}],
            'component_families':[{'name':'Crankshaft','description':'Named in the reference.','source_ids':[identifier]}],
            'unknowns':['Which mesh is the crankshaft is unknown.']}


def synthesis(identifier='ref1'):
    return {'findings':findings(identifier),'derived_by':{'provider':'fixture','model':'fixture-v1','method':'offline_fixture'},
            'cost':{'currency':'USD','actual_nanos':0,'calculated_nanos':0,'status':'known_zero_local'}}


class ResearchValidationTests(unittest.TestCase):
    def test_sources_are_bounded_untrusted_snapshots(self):
        original=source(secret='NEVER_SERIALIZE_THIS')
        result=validate_sources([original])[0]
        self.assertNotIn('secret',result)
        self.assertEqual(result['evidence_status'],'unreviewed_reference_candidate')
        self.assertEqual(len(result['content_sha256']),64)
        self.assertIsNone(result['revision_match'])

    def test_reject_bad_sources_and_credentials(self):
        for sources in ([source()]*2, [source(str(i)) for i in range(6)], [source(excerpt='x'*2501)],
                        [source(url='file:///tmp/source')], [source(url='https://user:pass@example.org')],
                        [source(object_match='true')], [source(retrieved_at=float('nan'))]):
            with self.subTest(sources=sources), self.assertRaises(ValueError): validate_sources(sources)

    def test_citations_do_not_promote_component_knowledge(self):
        result=validate_findings(findings(),[source()])
        self.assertEqual(result['epistemic_status'],'candidate')
        self.assertEqual(result['geometry_mappings'],[])
        self.assertEqual(result['scope'],'object_family')

    def test_invalid_research_output_is_rejected(self):
        for value in (findings('invented-source'), {**findings(),'verified':True},
                      {**findings(),'geometry_mappings':[{'mesh':'piston'}]}, {**findings(),'unknowns':[]}):
            with self.subTest(value=value), self.assertRaises(ValueError): validate_findings(value,[source()])


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'workflows.sqlite3'
        self.store=WorkflowStore(self.path)
        self.manifest,_=ingest(fixture(),{})
        self.baseline=self.store.prepare(self.manifest)
        self.retrieval=Mock(); self.retrieval.retrieve.return_value=[source()]
        self.cognitive=Mock(); self.cognitive.investigate.return_value=synthesis()
        self.worker=Investigations(self.store,self.retrieval,self.cognitive)

    def tearDown(self): self.temp.cleanup()

    def enqueue(self): return self.worker.enqueue(self.baseline['id'],'V8 engine')

    def test_fixture_pipeline_records_stages_and_keeps_manifest_unchanged(self):
        before=deepcopy(self.manifest)
        queued=self.enqueue(); completed=self.worker.run_next()
        self.assertEqual(completed['id'],queued['id'])
        self.assertEqual(completed['status'],'reference_notes_ready')
        self.assertTrue(all(s['status']=='completed' for s in completed['stages'].values()))
        self.assertEqual(completed['findings']['geometry_mappings'],[])
        self.assertEqual(self.manifest,before)
        operation, request=self.cognitive.investigate.call_args.args
        self.assertEqual(len(operation),32)
        self.assertEqual(set(request),{'query','sources','geometry'})
        self.assertEqual(set(request['geometry']),{'piece_count','prioritized_count'})
        self.assertNotIn('source_geometry',request)

    def test_completed_request_survives_restart_without_provider_calls(self):
        self.enqueue(); first=self.worker.run_next()
        restarted=Investigations(WorkflowStore(self.path),self.retrieval,self.cognitive)
        restarted.recover_interrupted()
        self.assertEqual(restarted.enqueue(self.baseline['id'],'V8 engine'),first)
        self.assertIsNone(restarted.run_next())
        self.retrieval.retrieve.assert_called_once(); self.cognitive.investigate.assert_called_once()

    def test_two_workers_cannot_claim_the_same_run(self):
        self.enqueue()
        other=Investigations(self.store,self.retrieval,self.cognitive)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda w:w.run_next(),[self.worker,other]))
        self.assertEqual(sum(r is not None for r in results),1)
        self.cognitive.investigate.assert_called_once()

    def test_missing_providers_are_visible_not_simulated(self):
        worker=Investigations(self.store)
        queued=worker.enqueue(self.baseline['id'],'V8 engine')
        self.assertEqual(worker.run_next()['status'],'awaiting_retrieval_provider')
        with self.assertRaises(ValueError): worker.resume_missing_provider(queued['id'])
        worker.retrieval=self.retrieval; worker.resume_missing_provider(queued['id'])
        self.assertEqual(worker.run_next()['status'],'awaiting_cognitive_provider')
        worker.cognitive=self.cognitive; worker.resume_missing_provider(queued['id'])
        self.assertEqual(worker.run_next()['status'],'reference_notes_ready')
        self.retrieval.retrieve.assert_called_once()

    def test_no_sources_skips_cognitive_work(self):
        self.retrieval.retrieve.return_value=[]
        self.enqueue()
        self.assertEqual(self.worker.run_next()['status'],'no_references')
        self.cognitive.investigate.assert_not_called()

    def test_all_revision_mismatches_skip_cognitive_work_but_preserve_sources(self):
        self.retrieval.retrieve.return_value=[source(revision_match=False)]
        self.enqueue(); record=self.worker.run_next()
        self.assertEqual(record['status'],'no_relevant_references')
        self.assertEqual(len(record['sources']),1)
        self.cognitive.investigate.assert_not_called()

    def test_all_five_candidates_retained_only_three_sent_for_reasoning(self):
        self.retrieval.retrieve.return_value=[source('ref'+str(i)) for i in range(5)]
        self.cognitive.investigate.return_value=synthesis('ref0')
        self.enqueue(); record=self.worker.run_next()
        self.assertEqual(record['status'],'reference_notes_ready')
        self.assertEqual(len(record['sources']),5)
        self.assertEqual(len(record['selected_source_ids']),3)
        request=self.cognitive.investigate.call_args.args[1]
        self.assertEqual(len(request['sources']),3)

    def test_provider_failure_is_redacted_and_never_retried(self):
        self.cognitive.investigate.side_effect=RuntimeError('PRIVATE_KEY')
        self.enqueue(); record=self.worker.run_next()
        self.assertEqual(record['status'],'failed')
        self.assertIsNone(record['findings'])
        self.assertNotIn(b'PRIVATE_KEY',self.path.read_bytes())
        self.assertIsNone(self.worker.run_next())
        with self.assertRaises(ValueError): self.worker.resume_missing_provider(record['id'])
        self.cognitive.investigate.assert_called_once()

    def test_unknown_cost_never_becomes_actual_zero(self):
        self.cognitive.investigate.return_value['cost']={'currency':'USD','actual_nanos':0,'calculated_nanos':0,'status':'unknown'}
        self.enqueue(); record=self.worker.run_next()
        self.assertEqual(record['status'],'failed')
        self.assertIsNone(record['findings'])

    def test_bad_citations_fail_without_partial_knowledge(self):
        self.cognitive.investigate.return_value=synthesis('foreign')
        self.enqueue(); record=self.worker.run_next()
        self.assertEqual(record['status'],'failed')
        self.assertIsNone(record['findings'])

    def test_crashed_call_requires_review_not_automatic_resubmission(self):
        queued=self.enqueue()
        queued['status']='running'
        queued['stages']['synthesis']={'status':'running','operation_id':'f'*32}
        self.worker._save(queued)
        restarted=Investigations(self.store,self.retrieval,self.cognitive)
        restarted.recover_interrupted()
        self.assertEqual(restarted.get(queued['id'])['status'],'interrupted')
        self.assertIsNone(restarted.run_next())
        self.cognitive.investigate.assert_not_called()


if __name__=='__main__': unittest.main()
