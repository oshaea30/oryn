"""Application event history: observations, proposals and reviews, not hidden thoughts."""
from copy import deepcopy
import json
import hashlib
import re
import shutil
import threading
import time

from spending import DAILY_LIMIT
from workflow import encoded, fingerprint

CONTRACT='oryn-vision-episode-v1'
MAX_VISION_TARGETS=3


class Episodes:
    def __init__(self, workflows):
        self.workflows=workflows
        self.render_lock=threading.Lock()
        with workflows.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS vision_runs
                (id TEXT PRIMARY KEY,status TEXT NOT NULL,record TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS episode_events
                (sequence INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,
                 episode_id TEXT NOT NULL,kind TEXT NOT NULL,created REAL NOT NULL,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS episode_images
                (episode_id TEXT NOT NULL,ordinal INTEGER NOT NULL,png BLOB NOT NULL,metadata TEXT NOT NULL,
                 PRIMARY KEY(episode_id,ordinal));
                CREATE TABLE IF NOT EXISTS vision_policy
                (id INTEGER PRIMARY KEY CHECK(id=1),record TEXT NOT NULL);''')

    @staticmethod
    def _append(db, identifier, key, kind, payload):
        event_id=fingerprint({'episode':identifier,'key':key})
        value=encoded(payload)
        existing=db.execute('SELECT kind,payload FROM episode_events WHERE id=?',(event_id,)).fetchone()
        if existing and (existing[0]!=kind or existing[1]!=value):
            raise ValueError('Existing episode event cannot be overwritten.')
        db.execute('INSERT OR IGNORE INTO episode_events (id,episode_id,kind,created,payload) VALUES (?,?,?,?,?)',
                   (event_id,identifier,kind,time.time(),value))
        return event_id

    def append(self, identifier, key, kind, payload):
        with self.workflows.connect() as db:
            if db.execute('SELECT 1 FROM vision_runs WHERE id=?',(identifier,)).fetchone() is None:
                raise ValueError('Unknown episode.')
            return self._append(db,identifier,key,kind,payload)

    def ensure(self, evidence, research):
        if evidence['status']!='ready' or research['status']!='reference_notes_ready' or evidence['asset_id']!=research['asset_id']:
            raise ValueError('Matching ready geometry and reference evidence required.')
        identity={'contract':CONTRACT,'asset_id':evidence['asset_id'],'evidence_id':evidence['id'],
                  'research_id':research['id'],'targets':evidence['targets'][:MAX_VISION_TARGETS]}
        identifier=fingerprint(identity)
        record={'id':identifier,**identity,'status':'waiting_policy','created_at':time.time(),
                'query':research['query'],'sources':deepcopy(research['sources']),
                'selected_source_ids':list(research['selected_source_ids']),
                'prior_synthesis_operation':research['stages']['synthesis'].get('operation_id'),
                'reference_findings':deepcopy(research['findings']),
                'operation_id':fingerprint({'episode':identifier,'stage':'vision'})[:32],
                'candidate_revision_id':None,'error':None,
                'not_examined_geometry_ids':evidence['targets'][MAX_VISION_TARGETS:]}
        with self.workflows.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM vision_runs WHERE id=?',(identifier,)).fetchone() is None:
                db.execute('INSERT INTO vision_runs VALUES (?,?,?)',(identifier,record['status'],encoded(record)))
                self._append(db,identifier,'opened','episode_opened',{
                    'question':'What could these geometric pieces represent?',**identity,
                    'reference_research_snapshot':{'sources':record['sources'],'findings':record['reference_findings'],
                      'synthesis_operation':record['prior_synthesis_operation']},
                    'dataset_eligibility':'not_reviewed','reference_reuse_rights':'not_assessed',
                    'expected_structure':'No verified component plan exists; family notes are unverified context.'})
        return self.get(identifier)

    def get(self, identifier):
        with self.workflows.connect() as db:
            row=db.execute('SELECT record FROM vision_runs WHERE id=?',(identifier,)).fetchone()
        if not row:raise ValueError('Unknown vision episode.')
        return json.loads(row[0])

    def events(self, identifier):
        self.get(identifier)
        with self.workflows.connect() as db:
            rows=db.execute('SELECT sequence,id,kind,created,payload FROM episode_events WHERE episode_id=? ORDER BY sequence',(identifier,)).fetchall()
        return [{'sequence':r[0],'id':r[1],'kind':r[2],'created_at':r[3],'payload':json.loads(r[4])} for r in rows]

    def retain_observations(self, identifier, package, images):
        """Local preparation only. Retain exact PNG evidence before any egress.

        No HTTP image-upload route. Callers provide the locally generated package.
        """
        from vision_render import validate_png
        record=self.get(identifier)
        if package['id']!=record['evidence_id'] or package['asset_id']!=record['asset_id'] or not 1<=len(images)<=MAX_VISION_TARGETS:
            raise ValueError('Object evidence binding mismatch.')
        views={v['geometry_id']:v for v in package['views']}
        if [i['geometry_id'] for i in images]!=record['targets']:raise ValueError('Raster target sequence changed.')
        metadata=[]
        for image in images:
            validate_png(image['png'])
            if image['view_id']!=views[image['geometry_id']]['view_id'] or hashlib.sha256(image['png']).hexdigest()!=image['png_sha256']:
                raise ValueError('Raster/view binding mismatch.')
            metadata.append({k:image[k] for k in ('geometry_id','view_id','png_sha256','renderer','width','height')})
        payload={'evidence_id':package['id'],'images':metadata,
                 'measurements':[m for m in package['measurements'] if m['geometry_id'] in record['targets']],
                 'views':[views[g] for g in record['targets']], 'limitations':package['limitations'],
                 'outbound_images':False,'dataset_eligibility':'not_reviewed'}
        with self.workflows.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            stored=db.execute('SELECT COALESCE(SUM(LENGTH(png)),0) FROM episode_images').fetchone()[0]
            additions=[]
            for ordinal,(image,meta) in enumerate(zip(images,metadata)):
                previous=db.execute('SELECT png,metadata FROM episode_images WHERE episode_id=? AND ordinal=?',(identifier,ordinal)).fetchone()
                if previous and (previous[0]!=image['png'] or previous[1]!=encoded(meta)):
                    raise ValueError('Existing raster evidence cannot be overwritten.')
                if not previous:additions.append((identifier,ordinal,image['png'],encoded(meta)))
            if stored+sum(len(a[2]) for a in additions)>128*1024*1024:raise ValueError('Episode raster storage quota exceeded.')
            db.executemany('INSERT INTO episode_images VALUES (?,?,?,?)',additions)
            self._append(db,identifier,'observations_prepared','observations_prepared',payload)

    def prepare_local(self, identifier, evidence_store, renderer=None):
        """Application-owned local render step; no provider or credential access."""
        if not self.render_lock.acquire(blocking=False):raise ValueError('Local renderer is busy.')
        try:return self._prepare_local(identifier,evidence_store,renderer)
        finally:self.render_lock.release()

    def _prepare_local(self, identifier, evidence_store, renderer):
        record=self.get(identifier)
        if any(e['kind']=='observations_prepared' for e in self.events(identifier)):
            for n in range(len(record['targets'])):self.image(identifier,n)
            return {'prepared':True,'reused':True,'images':len(record['targets']),'outbound_images':False}
        if record['status']!='waiting_policy':raise ValueError('Episode not eligible for local preparation.')
        if shutil.disk_usage(self.workflows.path.parent).free<576*1024*1024:raise ValueError('Local free-space reserve required.')
        from vision_render import rasterize
        package=deepcopy(evidence_store.get(record['evidence_id']))
        if package['status']!='ready':raise ValueError('Local geometry evidence not ready.')
        package['targets']=record['targets']
        package['views']=[v for v in package['views'] if v['geometry_id'] in record['targets']]
        images=(renderer or rasterize)(evidence_store,package)
        self.retain_observations(identifier,package,images)
        return {'prepared':True,'reused':False,'images':len(images),'outbound_images':False}

    def image(self, identifier, ordinal):
        if type(ordinal)is not int or not 0<=ordinal<MAX_VISION_TARGETS:raise ValueError('Invalid raster ordinal.')
        with self.workflows.connect() as db:
            row=db.execute('SELECT png,metadata FROM episode_images WHERE episode_id=? AND ordinal=?',(identifier,ordinal)).fetchone()
        if not row or hashlib.sha256(row[0]).hexdigest()!=json.loads(row[1])['png_sha256']:
            raise ValueError('Retained raster unavailable or corrupt.')
        return row[0]

    def finish(self, identifier, status, **fields):
        if status not in {'completed','failed','blocked','interrupted'}:raise ValueError('Invalid episode state.')
        with self.workflows.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT record FROM vision_runs WHERE id=?',(identifier,)).fetchone()
            if not row:raise ValueError('Unknown episode.')
            record=json.loads(row[0]);record.update(fields,status=status,finished_at=time.time())
            self._append(db,identifier,'finished','episode_finished',{'status':status,**fields})
            db.execute('UPDATE vision_runs SET status=?,record=? WHERE id=?',(status,encoded(record),identifier))

    def claim(self, identifier):
        with self.workflows.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT record FROM vision_runs WHERE id=? AND status='waiting_policy'",(identifier,)).fetchone()
            if not row:return None
            record=json.loads(row[0]);record['status']='running'
            self._append(db,identifier,'claimed','work_claimed',{'operation_id':record['operation_id']})
            db.execute("UPDATE vision_runs SET status='running',record=? WHERE id=?",(encoded(record),identifier))
            return record

    def recover(self):
        with self.workflows.connect() as db:
            identifiers=[r[0] for r in db.execute("SELECT id FROM vision_runs WHERE status='running'")]
        for identifier in identifiers:
            self.finish(identifier,'interrupted',error='Prior vision work may have completed. No automatic retry.')

    def configure_policy(self, key_binding, confirmation):
        if (not isinstance(confirmation,dict) or set(confirmation)!={'object_only_vision','sharing_disabled','accept_budget'} or
                any(confirmation[k] is not True for k in confirmation) or
                not isinstance(key_binding,str) or not re.fullmatch('[a-f0-9]{64}',key_binding)):
            raise ValueError('One-time data policy and account sharing confirmation required.')
        record={'contract':CONTRACT,'credential_binding':key_binding,'confirmed_at':time.time(),
                'confirmed_by':'local_operator','verification':'operator_attestation_not_provider_api',
                'store':False,'room_images':False,'raw_glb':False,'object_only_vision':True,
                'sharing_disabled':True,'max_object_nanos':50_000_000,'daily_nanos':DAILY_LIMIT,
                'automatic_paid_retries':False}
        with self.workflows.connect() as db:
            db.execute('INSERT OR REPLACE INTO vision_policy VALUES (1,?)',(encoded(record),))

    def policy_ready(self, key_binding):
        with self.workflows.connect() as db:
            row=db.execute('SELECT record FROM vision_policy WHERE id=1').fetchone()
        if not row:return False
        value=json.loads(row[0])
        return value.get('contract')==CONTRACT and value.get('credential_binding')==key_binding and value.get('sharing_disabled') is True

    def review(self, identifier, body, evidence_store):
        """Human feedback is a new event, never a mutation or verified promotion."""
        required={'request_id','revision_id','geometry_id','decision','reason','replacement_name','source_ids','previous_review_id'}
        if not isinstance(body,dict) or set(body)!=required:raise ValueError('Invalid review fields.')
        if not isinstance(body['request_id'],str) or not re.fullmatch('[a-f0-9]{32}',body['request_id']):raise ValueError('Review request ID required.')
        if body['decision'] not in {'accepted','rejected','corrected'}:raise ValueError('Unknown review decision.')
        if not isinstance(body['reason'],str) or not 1<=len(body['reason'].strip())<=1000:raise ValueError('Review reason required.')
        name=body['replacement_name']
        if not isinstance(name,str) or len(name)>200 or (bool(name.strip()) != (body['decision']=='corrected')):raise ValueError('Correction name required only for correction.')
        record=self.get(identifier)
        if record['status']!='completed' or record['candidate_revision_id']!=body['revision_id']:raise ValueError('Completed bound candidate revision required.')
        report=evidence_store.report(record['evidence_id'])
        revision=next((r for r in report['candidate_revisions'] if r['id']==body['revision_id']),None)
        if not revision or body['geometry_id'] not in {m['geometry_id'] for m in revision['mappings']}:raise ValueError('Unknown candidate.')
        ids=body['source_ids'];valid={s['id'] for s in record['sources']}
        for event in self.events(identifier):
            result=event['payload']
            if (event['kind']=='assessment_finished' and result.get('status')=='completed' and
                    result.get('candidate_revision_id')==body['revision_id']):
                valid.update(s['id'] for s in result.get('sources',[]))
        if not isinstance(ids,list) or any(not isinstance(i,str) or i not in valid for i in ids) or len(ids)>5:raise ValueError('Invalid review evidence.')
        payload={**deepcopy(body),'actor':'local_operator','authentication_scope':'local_development_console',
                 'promoted_to_verified':False,'epistemic_status':'candidate',
                 'dataset_eligibility':'not_assessed'}
        if body['decision']=='corrected':
            payload['replacement_candidate']={'name':name.strip(),'status':'candidate',
                'derived_by':{'method':'human_correction','actor':'local_operator'},
                'supersedes':{'revision_id':body['revision_id'],'geometry_id':body['geometry_id']}}
        with self.workflows.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            event_id=fingerprint({'episode':identifier,'key':'review:'+body['request_id']})
            old=db.execute('SELECT payload FROM episode_events WHERE id=?',(event_id,)).fetchone()
            if old:
                if old[0]!=encoded(payload):raise ValueError('Review ID already used for different feedback.')
                return event_id
            prior=None
            for event_id_raw,raw in db.execute("SELECT id,payload FROM episode_events WHERE episode_id=? AND kind='human_review' ORDER BY sequence DESC",(identifier,)):
                if json.loads(raw)['geometry_id']==body['geometry_id']:
                    prior=event_id_raw;break
            if body['previous_review_id']!=prior:raise ValueError('Review changed; refresh before submitting.')
            return self._append(db,identifier,'review:'+body['request_id'],'human_review',payload)
