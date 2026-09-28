"""Persistent local investigation baseline; no provider I/O or headset actions.

Durable decision records are independent of immutable geometry manifests. Reused
assets share analysis by manifest content, not prompt. Nothing here promotes a
geometry piece to a component, performs research, or authorizes paid work.
"""
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time

from fast_decisions import CONTRACT, POINTS, FastDecisionProvider, LocalDecisionProvider, geometry_facts, validate_results


VERSION = 'oryn-investigation-baseline-v1'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


class WorkflowStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()
        # Each transaction owns its connection; no thread-bound shared cursors.
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY, record TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS investigations (
                    id TEXT PRIMARY KEY, record TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evaluations (
                    decision_id TEXT NOT NULL, item_id TEXT NOT NULL,
                    expected_action TEXT NOT NULL, outcome TEXT NOT NULL,
                    evaluator TEXT NOT NULL, created REAL NOT NULL,
                    PRIMARY KEY(decision_id, item_id, evaluator));
            ''')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _get(self, table, identifier):
        assert table in {'decisions', 'investigations'}
        with self.connect() as db:
            row = db.execute(f'SELECT record FROM {table} WHERE id=?', (identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def _put(self, table, record):
        assert table in {'decisions', 'investigations'}
        with self.connect() as db:
            db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?, ?)', (record['id'], encoded(record)))

    def decide_local(self, scope, point, facts):
        """Fixed no-cost production baseline; no injectable remote execution path.

        Running is persisted before evaluation. A process interruption is visible
        and never silently repeated, even though these baseline rules are free.
        """
        provider: FastDecisionProvider = LocalDecisionProvider()
        facts = deepcopy(facts)
        identity = {'contract': CONTRACT, 'scope': scope, 'point': point,
                    'provider': provider.name, 'version': provider.version, 'input': facts}
        identifier = fingerprint(identity)
        with self.lock:
            existing = self._get('decisions', identifier)
            if existing:
                if existing['status'] != 'completed':
                    raise ValueError('Prior decision is incomplete; no implicit retry.')
                return existing
            record = {'id': identifier, **identity, 'status': 'running', 'started_at': time.time(),
                      'latency_ms': None, 'cost': {'currency': 'USD', 'actual_nanos': 0,
                       'status': 'known_zero_local'}, 'quality_outcome': 'unreviewed', 'results': []}
            self._put('decisions', record)
            start = time.perf_counter()
            try:
                results = validate_results(point, facts, provider.decide(point, deepcopy(facts)))
            except Exception:
                record.update(status='failed', failure_code='invalid_or_failed_decision',
                              latency_ms=(time.perf_counter() - start) * 1000)
                self._put('decisions', record)
                raise ValueError('Local decision failed; no actions or automatic retry.') from None
            record.update(status='completed', results=results, finished_at=time.time(),
                          latency_ms=(time.perf_counter() - start) * 1000)
            self._put('decisions', record)
            return record

    def prepare(self, manifest):
        # Provenance job IDs differ across cache reuse; asset analysis does not.
        content = {k: manifest[k] for k in ('asset_id', 'revision', 'pipeline', 'source_geometry',
                   'geometry_pieces', 'components', 'component_mappings', 'unresolved_mappings', 'evidence', 'capabilities')}
        key = fingerprint({'workflow': VERSION, 'manifest': content})
        with self.lock:
            existing = self._get('investigations', key)
            if existing:
                if existing['status'] == 'preparing':
                    existing.update(status='interrupted', blocker='local_preparation_interrupted')
                    self._put('investigations', existing)
                return existing
            record = {'id': key, 'workflow_version': VERSION, 'asset_id': manifest['asset_id'],
                      'manifest_revision': manifest['revision'], 'manifest_fingerprint': fingerprint(content),
                      'created_at': time.time(), 'status': 'preparing', 'decision_ids': [], 'steps': [],
                      'investigation_targets': [], 'unresolved_count': len(manifest['unresolved_mappings']),
                      'blocker': None}
            self._put('investigations', record)
            try:
                started = time.perf_counter()
                facts = geometry_facts(manifest)
                record['steps'].append({'id': 'measure_geometry', 'kind': 'deterministic', 'status': 'completed',
                                        'items': len(facts), 'latency_ms': (time.perf_counter()-started)*1000})
                decision = self.decide_local(key, 'geometry_triage', facts)
                targets = [r['id'] for r in decision['results'] if r['action'] == 'investigate']
                # Hard application bound, independent of provider recommendations.
                if len(targets) > 8:
                    raise ValueError('Geometry analysis budget exceeded.')
                record['decision_ids'].append(decision['id'])
                record['investigation_targets'] = targets
                record['steps'] += [
                    {'id': 'triage_geometry', 'kind': 'fast_decision', 'status': 'completed', 'decision_id': decision['id']},
                    {'id': 'retrieve_references', 'kind': 'external_work', 'status': 'blocked', 'reason': 'retrieval_worker_not_connected'},
                    {'id': 'triage_references', 'kind': 'fast_decision', 'status': 'waiting', 'depends_on': 'retrieve_references'},
                    {'id': 'investigate_components', 'kind': 'deep_reasoning', 'status': 'blocked',
                     'reason': 'investigation_cognitive_provider_not_connected', 'depends_on': 'triage_references'},
                    {'id': 'validate_mapping_evidence', 'kind': 'deterministic', 'status': 'waiting', 'depends_on': 'investigate_components'},
                ]
                record.update(status='awaiting_research', blocker='research_and_semantic_mapping_not_connected')
            except Exception:
                record.update(status='failed', blocker='local_preparation_failed')
            record['updated_at'] = time.time()
            self._put('investigations', record)
            return record

    def report(self, identifier):
        record = self._get('investigations', identifier)
        if record is None:
            raise ValueError('Unknown investigation.')
        return {**record, 'decisions': [self._get('decisions', i) for i in record['decision_ids']],
                'decision_points': deepcopy(POINTS)}

    def evaluate(self, decision_id, labels, evaluator):
        """Offline human/labeled-fixture outcomes. Never a model's self-confidence.

        No HTTP writer. This records routing quality, NOT component verification.
        Repeating the same evaluator+item is idempotent; conflicting labels fail.
        """
        if not isinstance(evaluator, str) or not 1 <= len(evaluator) <= 100:
            raise ValueError('Evaluator identity required.')
        record = self._get('decisions', decision_id)
        if not record or record['status'] != 'completed' or not isinstance(labels, dict) or not labels:
            raise ValueError('Completed decision and nonempty labels required.')
        results = {r['id']: r['action'] for r in record['results']}
        if any(i not in results or value not in POINTS[record['point']]['actions'] for i, value in labels.items()):
            raise ValueError('Invalid evaluation labels.')
        with self.lock, self.connect() as db:
            for item_id, expected in labels.items():
                row = db.execute('SELECT expected_action FROM evaluations WHERE decision_id=? AND item_id=? AND evaluator=?',
                                 (decision_id, item_id, evaluator)).fetchone()
                if row and row[0] != expected:
                    raise ValueError('Existing evaluation preserved; use a new evaluator revision.')
                db.execute('INSERT OR IGNORE INTO evaluations VALUES (?, ?, ?, ?, ?, ?)',
                           (decision_id, item_id, expected, 'match' if results[item_id] == expected else 'mismatch', evaluator, time.time()))

    def metrics(self):
        with self.connect() as db:
            records = [json.loads(row[0]) for row in db.execute('SELECT record FROM decisions')]
            evaluated = dict(db.execute('SELECT outcome, COUNT(*) FROM evaluations GROUP BY outcome'))
        groups = {}
        for record in records:
            key = record['point'] + ':' + record['provider'] + ':' + record['version']
            group = groups.setdefault(key, {'calls': 0, 'completed': 0, 'failed': 0, 'incomplete': 0,
                'items': 0, 'latency_ms_total': 0, 'actual_cost_nanos': 0, 'actions': {}})
            group['calls'] += 1
            group['completed' if record['status'] == 'completed' else 'failed' if record['status'] == 'failed' else 'incomplete'] += 1
            group['items'] += len(record['input'])
            group['latency_ms_total'] += record['latency_ms'] or 0
            group['actual_cost_nanos'] += record['cost']['actual_nanos']
            for result in record['results']:
                group['actions'][result['action']] = group['actions'].get(result['action'], 0) + 1
        return {'scope': 'local_decisions_only_not_generation_or_research_cost', 'currency': 'USD',
                'groups': groups, 'evaluations': evaluated,
                'note': 'Completed means contract-valid, not semantically correct. Latency is batch execution, not per-item or end-to-end.'}


def summary(record):
    return {k: record[k] for k in ('id', 'asset_id', 'manifest_revision', 'status', 'blocker', 'unresolved_count')} | {
        'selected_for_investigation': len(record['investigation_targets']),
        'semantic_mapping_performed': False,
    }
