"""Offline-capable durable investigation executor. No network or paid adapters.

Providers are injected by the application only after their data and spending
policies are configured. Missing providers block visibly; they are not simulated.
"""
from copy import deepcopy
import hashlib
import json
import threading
import time
from typing import Protocol
from urllib.parse import urlsplit

from workflow import encoded, fingerprint


class RetrievalProvider(Protocol):
    def retrieve(self, query: str) -> list[dict]: ...


class CognitiveProvider(Protocol):
    def investigate(self, operation_id: str, request: dict, *, investigation_id: str) -> dict: ...


def validate_sources(sources):
    """Bound evidence snapshots before any cognitive adapter sees them."""
    if not isinstance(sources, list) or len(sources) > 5:
        raise ValueError('At most five reference candidates allowed.')
    clean, seen = [], set()
    for source in sources:
        if not isinstance(source, dict): raise ValueError('Invalid reference.')
        item = {k:source.get(k) for k in ('id','title','url','excerpt','source_type','retrieved_at','object_revision')}
        for key, maximum in (('id',100),('title',300),('url',2000),('excerpt',2500),('source_type',80)):
            if not isinstance(item[key], str) or not 1 <= len(item[key].strip()) <= maximum:
                raise ValueError('Invalid reference metadata.')
        parsed = urlsplit(item['url'])
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Reference requires an HTTPS citation, not credentials or local files.')
        if item['id'] in seen: raise ValueError('Duplicate reference ID.')
        seen.add(item['id'])
        if type(item['retrieved_at']) not in (int,float) or not 0 <= item['retrieved_at'] < 1e12:
            raise ValueError('Reference retrieval timestamp required.')
        if item['object_revision'] is not None and (not isinstance(item['object_revision'],str) or len(item['object_revision']) > 100):
            raise ValueError('Invalid object revision.')
        for name in ('object_match','revision_match'):
            if source.get(name) is not None and type(source[name]) is not bool:
                raise ValueError('Match metadata must be true, false or unknown.')
            item[name] = source.get(name)
        item['content_sha256'] = hashlib.sha256(item['excerpt'].encode()).hexdigest()
        item['evidence_status'] = 'unreviewed_reference_candidate'
        clean.append(item)
    return clean


def validate_findings(value, sources):
    """Validate structure/citation membership, NOT factual entailment or anatomy."""
    if not isinstance(value,dict) or set(value) != {'overview','component_families','unknowns'}:
        raise ValueError('Invalid research output contract.')
    if any(not isinstance(value[k],list) for k in value) or len(value['overview']) > 3 or len(value['component_families']) > 5 or not 1 <= len(value['unknowns']) <= 6:
        raise ValueError('Research output exceeds limits.')
    ids = {s['id'] for s in sources}
    def text_ok(v): return isinstance(v,str) and 1 <= len(v.strip()) <= 500
    for field, keys in (('overview', {'text','source_ids'}),('component_families', {'name','description','source_ids'})):
        for claim in value[field]:
            if (not isinstance(claim,dict) or set(claim) != keys or
                    not isinstance(claim['source_ids'],list) or not 1 <= len(claim['source_ids']) <= 5 or
                    any(not isinstance(i,str) or i not in ids for i in claim['source_ids']) or
                    any(not text_ok(claim[k]) for k in keys - {'source_ids'})):
                raise ValueError('Invalid claim or unsupported citation.')
    if any(not text_ok(v) for v in value['unknowns']): raise ValueError('Invalid unknowns.')
    return {**deepcopy(value), 'scope':'object_family', 'epistemic_status':'candidate',
            'evidence_status':'source_linked_not_verified', 'geometry_mappings':[],
            'human_review':'not_reviewed', 'limitations':[
                'Citation membership checked; factual support has not been independently verified.',
                'Exact product/revision, internal completeness and mesh identities remain unknown.']}


class Investigations:
    """One local worker. Stage claims persist before provider calls; no retries.

    The immutable ingestion manifest and current Quest scene are never written.
    Restarted in-flight work needs review, while untouched queued work may resume.
    """
    def __init__(self, store, retrieval=None, cognitive=None):
        self.store, self.retrieval, self.cognitive = store, retrieval, cognitive
        self.worker_lock = threading.Lock()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS research_runs (id TEXT PRIMARY KEY, status TEXT NOT NULL, record TEXT NOT NULL)')

    def enqueue(self, investigation_id, query):
        if not isinstance(query,str) or not 1 <= len(query.strip()) <= 800:
            raise ValueError('Object query required.')
        investigation = self.store.report(investigation_id)
        if investigation['status'] != 'awaiting_research':
            raise ValueError('Local investigation baseline must be ready.')
        identity = {'investigation_id':investigation_id,'query_key':' '.join(query.casefold().split()),'contract':'oryn-research-v1'}
        identifier = fingerprint(identity)
        record = {'id':identifier, **identity, 'query':query.strip(), 'asset_id':investigation['asset_id'], 'status':'queued',
                  'created_at':time.time(), 'sources':[], 'selected_source_ids':[], 'findings':None,
                  'geometry':{'piece_count':investigation['unresolved_count'],
                              'prioritized_count':len(investigation['investigation_targets'])},
                  'stages':{'retrieval':{'status':'pending'}, 'reference_triage':{'status':'pending'},
                            'synthesis':{'status':'pending'}}, 'blocker':None}
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO research_runs VALUES (?, ?, ?)', (identifier,'queued',encoded(record)))
        return self.get(identifier)

    def get(self, identifier):
        with self.store.connect() as db:
            row = db.execute('SELECT record FROM research_runs WHERE id=?',(identifier,)).fetchone()
        if not row: raise ValueError('Unknown research run.')
        return json.loads(row[0])

    def _save(self, record):
        record['updated_at'] = time.time()
        with self.store.connect() as db:
            db.execute('UPDATE research_runs SET status=?,record=? WHERE id=?',
                       (record['status'],encoded(record),record['id']))

    def recover_interrupted(self):
        """Startup only, before the worker starts; never resubmit in-flight work."""
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for identifier, raw in db.execute("SELECT id,record FROM research_runs WHERE status='running'").fetchall():
                record=json.loads(raw)
                record.update(status='interrupted',blocker='previous_external_work_may_have_completed_no_retry')
                db.execute('UPDATE research_runs SET status=?,record=? WHERE id=?',('interrupted',encoded(record),identifier))

    def resume_missing_provider(self, identifier):
        """Explicit application operation after configuring the missing provider.

        Never resumes failed, interrupted or already attempted external stages.
        """
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT record FROM research_runs WHERE id=?',(identifier,)).fetchone()
            if not row: raise ValueError('Unknown research run.')
            record=json.loads(row[0])
            stage = 'retrieval' if record['status']=='awaiting_retrieval_provider' else 'synthesis' if record['status']=='awaiting_cognitive_provider' else None
            if not stage or record['stages'][stage]['status'] != 'pending':
                raise ValueError('Only unattempted work awaiting a provider can resume.')
            if (stage=='retrieval' and self.retrieval is None) or (stage=='synthesis' and self.cognitive is None):
                raise ValueError('Provider still unavailable.')
            record.update(status='queued',blocker=None)
            db.execute('UPDATE research_runs SET status=?,record=? WHERE id=?',('queued',encoded(record),identifier))

    def run_next(self):
        if not self.worker_lock.acquire(blocking=False): return None
        try:
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute("SELECT record FROM research_runs WHERE status='queued' ORDER BY rowid LIMIT 1").fetchone()
                if not row: return None
                record=json.loads(row[0]); record.update(status='running',blocker=None)
                db.execute('UPDATE research_runs SET status=?,record=? WHERE id=?',('running',encoded(record),record['id']))
            self._run(record)
            return self.get(record['id'])
        finally:
            self.worker_lock.release()

    def _run(self, record):
        stage = None
        try:
            if record['stages']['retrieval']['status'] == 'pending':
                if self.retrieval is None:
                    record.update(status='awaiting_retrieval_provider',blocker='reference_retrieval_not_connected')
                    return
                stage='retrieval'; start=time.perf_counter()
                record['stages'][stage]={'status':'running','started_at':time.time()}; self._save(record)
                record['sources']=validate_sources(self.retrieval.retrieve(record['query']))
                record['stages'][stage].update(status='completed',latency_ms=(time.perf_counter()-start)*1000)
                self._save(record)
            if not record['sources']:
                record.update(status='no_references',blocker='no_sources_no_synthesis_performed')
                return
            if record['stages']['reference_triage']['status'] == 'pending':
                stage='reference_triage'
                facts=[{k:s[k] for k in ('id','object_match','revision_match')} for s in record['sources']]
                decision=self.store.decide_local(record['id'],'reference_triage',facts)
                priorities={'accept_candidate':0,'investigate':1,'reject':2}
                selected=sorted(decision['results'],key=lambda r:priorities[r['action']])
                record['selected_source_ids']=[r['id'] for r in selected if r['action']!='reject'][:3]
                record['stages'][stage]={'status':'completed','decision_id':decision['id'],
                                         'latency_ms':decision['latency_ms'],'cost':decision['cost']}
                self._save(record)
            if not record['selected_source_ids']:
                record.update(status='no_relevant_references',blocker='all_reference_candidates_rejected')
                return
            if self.cognitive is None:
                record.update(status='awaiting_cognitive_provider',blocker='cognitive_investigation_not_connected')
                return
            stage='synthesis'; start=time.perf_counter()
            operation_id=fingerprint({'run_id':record['id'],'stage':stage})[:32]
            record['stages'][stage]={'status':'running','operation_id':operation_id,'started_at':time.time()}
            self._save(record)
            sources=[s for s in record['sources'] if s['id'] in record['selected_source_ids']]
            # Send only the bounded payload; no paths, GLBs, room images or secrets.
            request={'query':record['query'],'sources':deepcopy(sources),'geometry':dict(record['geometry'])}
            result=self.cognitive.investigate(operation_id,request,investigation_id=record['asset_id'])
            record['findings']=validate_findings(result['findings'],sources)
            derived=result['derived_by']
            if not isinstance(derived,dict) or set(derived)!={'provider','model','method'} or any(not isinstance(v,str) or not 1<=len(v)<=100 for v in derived.values()):
                raise ValueError('Research provenance required.')
            cost=result['cost']
            if (not isinstance(cost,dict) or set(cost)!={'currency','actual_nanos','calculated_nanos','status'} or cost['currency']!='USD' or
                cost['status'] not in ('known_zero_local','usage_estimate','unknown') or
                any(v is not None and (type(v)is not int or v<0) for v in (cost['actual_nanos'],cost['calculated_nanos']))):
                raise ValueError('Invalid research cost provenance.')
            if ((cost['status']=='known_zero_local' and (cost['actual_nanos']!=0 or cost['calculated_nanos']!=0)) or
                (cost['status']=='usage_estimate' and (cost['actual_nanos'] is not None or cost['calculated_nanos'] is None)) or
                (cost['status']=='unknown' and (cost['actual_nanos'] is not None or cost['calculated_nanos'] is not None))):
                raise ValueError('Unknown or estimated cost must not be presented as actual zero.')
            record['derived_by']=derived
            record['stages'][stage].update(status='completed',latency_ms=(time.perf_counter()-start)*1000,cost=cost)
            record.update(status='reference_notes_ready',blocker=None)
        except Exception:
            if stage:
                record['stages'][stage].update(status='failed',failure_code='stage_failed_no_automatic_retry')
            record.update(status='failed',blocker='research_failed_no_automatic_retry',findings=None)
        finally:
            self._save(record)
