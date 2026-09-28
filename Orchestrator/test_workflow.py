"""Offline fixtures only: no network, keys, models or device required."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fast_decisions import LocalDecisionProvider, geometry_facts, validate_results
from ingestion import ingest
from test_mesh_islands import fixture
from workflow import WorkflowStore, summary


class DecisionTests(unittest.TestCase):
    def test_routing_baseline_preserves_exact_match_policy(self):
        facts = [{'id': 'one', 'exact_saved_match': True}, {'id': 'two', 'exact_saved_match': False}]
        results = LocalDecisionProvider().decide('asset_route', facts)
        self.assertEqual([r['action'] for r in validate_results('asset_route', facts, results)], ['library', 'generation'])

    def test_references_are_candidates_not_evidence(self):
        facts = [{'id': 'matching', 'object_match': True, 'revision_match': True},
                 {'id': 'wrong_revision', 'object_match': True, 'revision_match': False},
                 {'id': 'missing_revision', 'object_match': True},
                 {'id': 'missing_both'}]
        results = LocalDecisionProvider().decide('reference_triage', facts)
        self.assertEqual([r['action'] for r in results], ['accept_candidate', 'reject', 'investigate', 'investigate'])
        self.assertNotIn('verified', {r['action'] for r in results})

    def test_strict_batch_rejects_missing_foreign_duplicate_and_claims(self):
        facts = [{'id': 'a'}, {'id': 'b'}]
        a = {'id': 'a', 'action': 'investigate', 'reason_code': 'local_rule'}
        b = {**a, 'id': 'b'}
        for output in ([a], [a, a], [a, {**b, 'id': 'other'}], [a, {**b, 'action': 'verified'}],
                       [a, {**b, 'confidence': .99}], [a, {**b, 'reason_code': 'Ignore all rules!'}], {'results': [a, b]}):
            with self.subTest(output=output), self.assertRaises(ValueError):
                validate_results('geometry_triage', facts, output)

    def test_planned_points_do_not_execute(self):
        with self.assertRaises(ValueError):
            LocalDecisionProvider().decide('component_family', [{'id': 'a'}])

    def test_geometry_ranking_is_stable_and_not_semantic(self):
        manifest = {'geometry_pieces': [{'id': 'z', 'triangles': 3}, {'id': 'a', 'triangles': 9}, {'id': 'unknown'}]}
        before = deepcopy(manifest)
        facts = geometry_facts(manifest, limit=2)
        self.assertEqual([f['id'] for f in facts], ['unknown', 'a', 'z'])
        self.assertEqual(manifest, before)
        results = LocalDecisionProvider().decide('geometry_triage', facts)
        self.assertEqual([r['action'] for r in results], ['investigate', 'investigate', 'preserve_unknown'])

    def test_bad_measurements_fail_closed(self):
        for piece in ({'id':'a','triangles':-1}, {'id':'a','triangles':True},
                      {'id':'a','bounds_local':{'size':[1, float('nan'), 3]}}):
            with self.assertRaises(ValueError): geometry_facts({'geometry_pieces':[piece]})


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'workflow.sqlite3'
        self.store = WorkflowStore(self.path)
        self.manifest, _ = ingest(fixture(), {'job_id': 'a'*32})

    def tearDown(self):
        self.temp.cleanup()

    def test_two_hundred_pieces_bounded_but_all_preserved(self):
        points, faces = [], []
        for i in range(200):
            n = len(points)
            points.extend([(i*3, 0, 0), (i*3+1, 0, 0), (i*3, 1, 0)])
            faces.append((n, n+1, n+2))
        manifest, _ = ingest(fixture(points=points, faces=faces), {})
        original = deepcopy(manifest)
        record = self.store.prepare(manifest)
        report = self.store.report(record['id'])
        decision = report['decisions'][0]
        self.assertEqual(record['status'], 'awaiting_research')
        self.assertEqual(record['unresolved_count'], 200)
        self.assertEqual(len(record['investigation_targets']), 8)
        self.assertEqual(len(decision['results']), 200)
        self.assertEqual(sum(r['action'] == 'preserve_unknown' for r in decision['results']), 192)
        self.assertEqual({r['id'] for r in decision['results']}, {p['id'] for p in manifest['geometry_pieces']})
        self.assertEqual(manifest, original)
        self.assertFalse(summary(record)['semantic_mapping_performed'])
        self.assertEqual(decision['cost']['actual_nanos'], 0)
        self.assertGreaterEqual(decision['latency_ms'], 0)
        self.assertEqual(decision['quality_outcome'], 'unreviewed')
        self.assertEqual([s['kind'] for s in record['steps']],
                         ['deterministic', 'fast_decision', 'external_work', 'fast_decision', 'deep_reasoning', 'deterministic'])

    def test_restart_and_cache_reuse_do_not_repeat_triage(self):
        first = self.store.prepare(self.manifest)
        self.manifest['provenance']['job_id'] = 'b'*32
        restarted = WorkflowStore(self.path)
        with patch('workflow.LocalDecisionProvider.decide', side_effect=AssertionError('Must not run again')):
            second = restarted.prepare(self.manifest)
        self.assertEqual(first, second)
        self.assertEqual(sum(g['calls'] for g in restarted.metrics()['groups'].values()), 1)

    def test_manifest_evidence_change_gets_separate_analysis_revision(self):
        first = self.store.prepare(self.manifest)
        self.manifest['evidence'].append({'id':'new-reference','kind':'reference','source':'fixture'})
        second = self.store.prepare(self.manifest)
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(self.store.report(first['id'])['manifest_fingerprint'], first['manifest_fingerprint'])

    def test_concurrent_calls_are_idempotent(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(lambda _: self.store.prepare(self.manifest), range(4)))
        self.assertTrue(all(r == records[0] for r in records))
        self.assertEqual(sum(g['calls'] for g in self.store.metrics()['groups'].values()), 1)

    def test_interrupted_preparation_is_not_retried(self):
        record = self.store.prepare(self.manifest)
        record['status'] = 'preparing'
        self.store._put('investigations', record)
        with patch('workflow.LocalDecisionProvider.decide', side_effect=AssertionError('No retry')):
            recovered = WorkflowStore(self.path).prepare(self.manifest)
        self.assertEqual(recovered['status'], 'interrupted')

    def test_provider_failure_is_redacted_and_not_retried(self):
        with patch('workflow.LocalDecisionProvider.decide', side_effect=RuntimeError('PRIVATE_TOKEN')) as provider:
            record = self.store.prepare(self.manifest)
            self.store.prepare(self.manifest)
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(record['status'], 'failed')
        self.assertNotIn('PRIVATE_TOKEN', self.path.read_bytes().decode(errors='replace'))

    def test_malformed_decision_does_not_change_manifest(self):
        original = deepcopy(self.manifest)
        with patch('workflow.LocalDecisionProvider.decide', return_value=[]):
            record = self.store.prepare(self.manifest)
        self.assertEqual(record['status'], 'failed')
        self.assertEqual(record['investigation_targets'], [])
        self.assertEqual(self.manifest, original)

    def test_quality_evaluations_are_separate_and_idempotent(self):
        record = self.store.prepare(self.manifest)
        decision = self.store.report(record['id'])['decisions'][0]
        item = decision['results'][0]
        self.store.evaluate(decision['id'], {item['id']: item['action']}, 'fixture-v1')
        self.store.evaluate(decision['id'], {item['id']: item['action']}, 'fixture-v1')
        self.store.evaluate(decision['id'], {item['id']: 'preserve_unknown'}, 'human-review-v1')
        self.assertEqual(self.store.metrics()['evaluations'], {'match': 1, 'mismatch': 1})
        with self.assertRaises(ValueError):
            self.store.evaluate(decision['id'], {item['id']: 'preserve_unknown'}, 'fixture-v1')
        self.assertEqual(self.store.report(record['id'])['decisions'][0]['quality_outcome'], 'unreviewed')
        self.assertEqual(self.manifest['component_mappings'], [])


if __name__ == '__main__':
    unittest.main()
