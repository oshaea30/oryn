"""Application-owned background research, independent of the delivery worker."""
import threading

from spending import DAILY_LIMIT
from credential_store import CredentialError, validate_key
from investigation import Investigations
from research_providers import WikipediaRetrieval, OpenAICognitiveProvider
from usage_ledger import UsageLedger


class ResearchService:
    def __init__(self, jobs, credential_store=None, key='', ledger=None, retrieval=None, cognitive_factory=OpenAICognitiveProvider):
        self.jobs,self.credentials,self.factory=jobs,credential_store,cognitive_factory
        self.ledger=ledger if ledger is not None else UsageLedger()
        self.key=key
        self.key_storage='session' if key else 'missing'
        self.error=''
        if not key and credential_store is not None:
            try:
                self.key=credential_store.load()
                if self.key: self.key_storage='keychain'
            except CredentialError as error:
                self.error=str(error)
        self.engine=Investigations(jobs.workflows,
            retrieval if retrieval is not None else WikipediaRetrieval(),
            cognitive_factory(self.ledger,self.key) if self.key else None)
        self.budget_error=''
        try:
            with jobs.workflows.connect() as db:
                import json
                records=[json.loads(r[0]) for r in db.execute('SELECT record FROM research_runs')]
            for record in records:
                stage=record['stages']['synthesis'];op=stage.get('operation_id')
                if op and self.ledger.get(op):self.ledger.bind_investigation(op,record['asset_id'])
                elif stage.get('cost',{}).get('status')=='usage_estimate':raise ValueError('Missing previous usage.')
        except Exception:
            self.budget_error='Previous research usage could not be reconciled; paid research blocked.'
            self.engine.cognitive=None
        self.engine.recover_interrupted()
        if self.key and not self.budget_error: self._resume_waiting()
        self.lock=threading.Lock()
        self.stop_event=threading.Event()
        self.thread=None

    def state(self):
        try:
            budget=self.ledger.summary()
        except Exception:
            budget={'halted':True,'remaining_nanos':0,'error':'Cognition budget unavailable; paid research is blocked.'}
        return {'enabled':True,'configured':bool(self.key),'keyStorage':self.key_storage,'error':self.budget_error or self.error,
                'policy':{'max_investigation_nanos':50_000_000,'shared_daily_nanos':DAILY_LIMIT,
                          'max_references':5,'max_synthesis_references':3,'automatic_retries':False},
                'budget':budget}

    def configure_key(self, value):
        if self.budget_error:raise ValueError(self.budget_error)
        key=validate_key(value)
        with self.lock:
            if self.credentials is not None: self.credentials.save(key)
            self.key=key; self.key_storage='keychain' if self.credentials is not None else 'session'
            self.engine.cognitive=self.factory(self.ledger,key)
            self.error=''
            # Only unattempted synthesis resumes; failures/uncertainty never do.
            self._resume_waiting()
        return {'configured':True,'keyStorage':self.key_storage}

    def _resume_waiting(self):
        with self.jobs.workflows.connect() as db:
            identifiers=[r[0] for r in db.execute("SELECT id FROM research_runs WHERE status='awaiting_cognitive_provider'")]
        for identifier in identifiers:
            self.engine.resume_missing_provider(identifier)

    def enqueue_job(self, job_id):
        with self.jobs.lock:
            job=self.jobs.jobs.get(job_id)
            if not job or job.get('demo') or 'geometry' not in job.get('variants',{}):
                raise ValueError('A saved generated object is required for investigation.')
            # Recheck source and manifest even for a cached/repeated request.
            self.jobs.prepare_ingestion(job_id,'geometry')
            baseline=job.get('investigations',{}).get('geometry',{})
            record=self.engine.enqueue(baseline.get('id'),job['prompt'])
            self.jobs.update(job_id,_preserve_updated=True,research_id=record['id'],research_error='')
            return self.summary(record['id'])

    def summary(self, identifier):
        record=self.engine.get(identifier)
        operation=record['stages']['synthesis'].get('operation_id')
        billing=None
        if operation:
            try:
                entry=self.ledger.get(operation)
                if entry:
                    billing={k:entry[k] for k in ('status','reserved_nanos','calculated_cost_nanos','actual_cost_nanos','outcome')}
            except Exception:
                billing={'status':'unavailable','actual_cost_nanos':None}
        return {k:record[k] for k in ('id','status','blocker','findings','stages')} | {
            'billing':billing,
            'derived_by':record.get('derived_by'),
            'investigation_budget':self.ledger.investigation_summary(record['asset_id']),
            'sources':[{k:s[k] for k in ('id','title','url','source_type','content_sha256')} for s in record['sources']],
            'selected_source_ids':record['selected_source_ids']}

    def start(self):
        if self.thread is not None: return
        def work():
            while not self.stop_event.is_set():
                try:
                    record=self.engine.run_next()
                except Exception:
                    self.error='Research worker stopped; saved models remain available. Inspect persisted work before restarting.'
                    return
                if record is None: self.stop_event.wait(1)
        self.thread=threading.Thread(target=work,daemon=True,name='oryn-research')
        self.thread.start()

    def stop(self):
        self.stop_event.set()
