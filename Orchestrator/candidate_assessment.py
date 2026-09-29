"""Application-owned, one-shot reference assessment of saved candidate revisions."""
from copy import deepcopy
import json
import re
import threading
import time

from assessment_provider import CONTRACT, OpenAIAssessmentProvider
from cognition import CommandError
from investigation import validate_sources
from research_providers import WikipediaRetrieval
from component_references import ComponentReferences
from workflow import encoded, fingerprint


def words(value):
    return re.findall(r'[a-z0-9]+',value.casefold())


def candidate_terms(value):
    return [w for w in words(value) if w not in {'candidate','possible','potential','hypothesis','tentative'}]


def search_plan(query,candidates):
    """Two bounded searches: descriptive then head-noun. No model-made URLs."""
    obj=words(query)[:8]
    names=list(dict.fromkeys(' '.join(candidate_terms(c['candidate_name'])[:8]) for c in candidates))
    heads=list(dict.fromkeys(n.split()[-1] for n in names if n))
    if not obj or not heads:raise ValueError('Searchable object and candidate terms required.')
    return list(dict.fromkeys([' '.join(obj+names)[:200], ' '.join(obj[-1:]+heads)[:200]]))


def select_references(batches,candidates,old_sources):
    """Replaceable deterministic relevance baseline, not an authority judgment."""
    started=time.monotonic()
    heads={candidate_terms(c['candidate_name'])[-1].rstrip('s') for c in candidates if candidate_terms(c['candidate_name'])}
    old={s['content_sha256'] for s in old_sources};seen=set();ranked=[];decisions=[]
    for batch in batches:
        for source in batch:
            key=(source['id'],source['content_sha256'])
            if key in seen:continue
            seen.add(key)
            title={w.rstrip('s') for w in words(source['title'])}
            excerpt={w.rstrip('s') for w in words(source['excerpt'])}
            matches=sorted(heads & (title|excerpt))
            fresh=source['content_sha256'] not in old
            accepted=bool(matches and fresh)
            decisions.append({'source_id':source['id'],'content_sha256':source['content_sha256'],
                'matched_candidate_terms':matches,'new_excerpt':fresh,
                'decision':'consider_family_context' if accepted else 'exclude_from_this_batch',
                'exact_object_match':'unknown','authority_verified':False})
            if accepted:ranked.append((len(heads & title),len(matches),source))
    ranked.sort(key=lambda x:(-x[0],-x[1],x[2]['id']))
    selected=[];ids=set()
    for _,__,source in ranked:
        if source['id'] not in ids and len(selected)<3:selected.append(source);ids.add(source['id'])
    return selected,{'provider':'deterministic_local','version':'candidate-head-term-v1',
        'latency_ms':round((time.monotonic()-started)*1000,3),'cost_nanos':0,
        'decisions':decisions,'selected_source_ids':[s['id'] for s in selected],
        'quality_outcome':'unreviewed','limitations':['Lexical relevance is not factual support or source authority.']}


class CandidateAssessmentService:
    def __init__(self,jobs,retrieval=None,provider_factory=OpenAIAssessmentProvider):
        self.jobs=jobs;self.retrieval=retrieval if retrieval is not None else ComponentReferences()
        self.factory=provider_factory;self.lock=threading.Lock();self.thread=None
        with jobs.workflows.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS candidate_assessments_v2 (episode_id TEXT PRIMARY KEY,status TEXT NOT NULL,record TEXT NOT NULL)')
            db.execute('BEGIN IMMEDIATE')
            for episode_id,raw in db.execute("SELECT episode_id,record FROM candidate_assessments_v2 WHERE status='running'").fetchall():
                record=json.loads(raw);record.update(status='interrupted',error='Assessment interrupted. No automatic retry.')
                db.execute('UPDATE candidate_assessments_v2 SET status=?,record=? WHERE episode_id=?',('interrupted',encoded(record),episode_id))
                jobs.episodes._append(db,episode_id,record['id']+':finished','assessment_finished',record)

    def get(self,identifier):
        with self.jobs.workflows.connect() as db:
            row=db.execute('SELECT record FROM candidate_assessments_v2 WHERE episode_id=?',(identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def start_episode(self,identifier):
        with self.lock:
            previous=self.get(identifier)
            if previous:return {'status':previous['status'],'dispatched':False}
            if self.thread and self.thread.is_alive():raise ValueError('Assessment worker busy.')
            if not self.jobs.vision or not self.jobs.vision.state()['policy_ready']:raise ValueError('Confirmed image policy required.')
            episode=self.jobs.episodes.get(identifier)
            if episode['status']!='completed':raise ValueError('Completed vision episode required.')
            revisions=self.jobs.geometry_evidence.report(episode['evidence_id'])['candidate_revisions']
            revision=next((r for r in revisions if r['id']==episode['candidate_revision_id']),None)
            if not revision or not 1<=len(revision['mappings'])<=3:raise ValueError('One to three saved candidates required.')
            candidates=deepcopy(revision['mappings'])
            identity={'contract':CONTRACT,'reference_pass':'curated-v2','episode_id':identifier,'candidate_revision_id':revision['id']}
            record={**identity,'id':fingerprint(identity),'asset_id':episode['asset_id'],
                'query':episode['query'],'candidates':candidates,'status':'running','created_at':time.time(),
                'queries':search_plan(episode['query'],candidates),'sources':[],'assessments':[],
                'epistemic_status':'candidate','capabilities_promoted':False,'error':None}
            record['operation_id']=fingerprint({'assessment':record['id'],'stage':'comparison'})[:32]
            with self.jobs.workflows.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT 1 FROM candidate_assessments_v2 WHERE episode_id=?',(identifier,)).fetchone():return {'dispatched':False}
                db.execute('INSERT INTO candidate_assessments_v2 VALUES (?,?,?)',(identifier,'running',encoded(record)))
                self.jobs.episodes._append(db,identifier,record['id']+':opened','assessment_opened',record)
            self.thread=threading.Thread(target=self._run,args=(record,episode),daemon=True,name='oryn-candidate-assessment')
            try:self.thread.start()
            except Exception:
                self.finish(record,'interrupted',error='Assessment worker unavailable; no retry.')
                raise ValueError('Assessment worker unavailable.') from None
            return {'id':record['id'],'status':'running','dispatched':True}

    def finish(self,record,status,**fields):
        record={**record,**fields,'status':status,'finished_at':time.time()}
        with self.jobs.workflows.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.jobs.episodes._append(db,record['episode_id'],record['id']+':finished','assessment_finished',record)
            db.execute('UPDATE candidate_assessments_v2 SET status=?,record=? WHERE episode_id=?',(status,encoded(record),record['episode_id']))

    def _run(self,record,episode):
        start=time.monotonic();identifier=record['episode_id'];episodes=self.jobs.episodes
        def event(kind,payload):episodes.append(identifier,record['id']+':'+kind,'assessment_'+kind,payload)
        try:
            # Key/policy changes cannot race image dispatch; geometry delivery stays independent.
            with self.jobs.research.lock:
                if not self.jobs.vision.state()['policy_ready']:raise ValueError('Policy changed.')
                batches=[]
                for n,query in enumerate(record['queries']):
                    event('retrieval_dispatch_'+str(n),{'query':query,'provider':type(self.retrieval).__name__,'scope':'family_reference_not_exact_mesh'})
                    before=time.monotonic();sources=validate_sources(self.retrieval.retrieve(query));batches.append(sources)
                    event('retrieval_result_'+str(n),{'query':query,'sources':sources,'latency_ms':round((time.monotonic()-before)*1000),
                        'provider_cost_nanos':0,'reuse_rights':'not_assessed'})
                selected,triage=select_references(batches,record['candidates'],episode['sources'])
                event('reference_triage',triage);record['sources']=selected
                if not selected:
                    assessments=[{'geometry_id':c['geometry_id'],'outcome':'insufficient_evidence','epistemic_status':'candidate',
                        'observation':'No additional visual assessment performed.',
                        'comparison':'Targeted retrieval found no new lexically relevant excerpts.',
                        'missing_evidence':['Relevant component references and object-specific evidence.'],
                        'view_ids':[],'evidence':[],'derived_by':{'method':'deterministic_reference_gate'},'independently_verified':False}
                        for c in record['candidates']]
                else:
                    package=deepcopy(self.jobs.geometry_evidence.get(episode['evidence_id']))
                    if package['asset_id']!=record['asset_id'] or package['status']!='ready':raise ValueError('Evidence binding changed.')
                    package['targets']=[c['geometry_id'] for c in record['candidates']]
                    by_geometry={v['geometry_id']:v for v in package['views']}
                    package['views']=[by_geometry[g] for g in package['targets']]
                    observed=next(e for e in episodes.events(identifier) if e['kind']=='observations_prepared')
                    saved={m['geometry_id']:(n,m) for n,m in enumerate(observed['payload']['images'])}
                    images=[{**saved[g][1],'png':episodes.image(identifier,saved[g][0])} for g in package['targets']]
                    assessments,_,provenance=self.factory(self.jobs.research.ledger,self.jobs.research.key).propose_mappings(
                        record,package,selected,images,event)
                    record['derived_by']=provenance
                self.finish(record,'completed',assessments=assessments,latency_ms=round((time.monotonic()-start)*1000))
        except Exception as error:
            self.finish(record,'failed',error=str(error) if isinstance(error,CommandError) else 'Assessment stopped; saved evidence retained. No automatic retry.',
                        latency_ms=round((time.monotonic()-start)*1000))
