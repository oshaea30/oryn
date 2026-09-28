"""Bounded application-owned vision pilot. Explicit dispatch; never scan/retry."""
from copy import deepcopy
import hashlib
import threading
import time

from cognition import CommandError
from vision_provider import OpenAIMappingProvider


class VisionService:
    def __init__(self, jobs, provider_factory=OpenAIMappingProvider):
        self.jobs, self.factory = jobs, provider_factory
        self.lock = threading.Lock()
        self.thread = None
        self.jobs.episodes.recover()

    @staticmethod
    def binding(key):
        return hashlib.sha256(('oryn-vision-policy:' + key).encode()).hexdigest()

    def state(self):
        research = self.jobs.research
        ready = bool(research and research.key and not research.budget_error and
                     self.jobs.episodes.policy_ready(self.binding(research.key)))
        return {'connected': True, 'policy_ready': ready,
                'busy': bool(self.thread and self.thread.is_alive()),
                'dispatch': 'explicit_episode', 'automatic_paid_retries': False}

    def configure_policy(self, confirmation):
        research = self.jobs.research
        if research is None: raise ValueError('Research service required.')
        with research.lock:
            if not research.key or research.budget_error: raise ValueError('Research key/budget unavailable.')
            self.jobs.episodes.configure_policy(self.binding(research.key), confirmation)
        return self.state()

    def start_episode(self, identifier):
        """Return promptly. Lost responses/repeated clicks cannot dispatch twice."""
        with self.lock:
            record = self.jobs.episodes.get(identifier)
            if record['status'] != 'waiting_policy':
                return {'id': identifier, 'status': record['status'], 'dispatched': False}
            if self.thread and self.thread.is_alive(): raise ValueError('Vision pilot already running.')
            if not self.state()['policy_ready']: raise ValueError('Vision data policy confirmation required.')
            # Require local preview preparation, so dispatch never hides rendering
            # failures or accepts arbitrary client-provided images/URLs.
            observed = next((e for e in self.jobs.episodes.events(identifier)
                             if e['kind'] == 'observations_prepared'), None)
            if not observed: raise ValueError('Prepare local object images first.')
            for n in range(len(record['targets'])): self.jobs.episodes.image(identifier, n)
            claimed = self.jobs.episodes.claim(identifier)
            if claimed is None: return {'id': identifier, 'dispatched': False}
            self.thread = threading.Thread(target=self._run, args=(claimed,),
                                           daemon=True, name='oryn-vision-pilot')
            try: self.thread.start()
            except Exception:
                self.jobs.episodes.finish(identifier, 'interrupted', error='Worker did not start; no automatic retry.')
                raise ValueError('Vision worker unavailable.') from None
            return {'id': identifier, 'status': 'running', 'dispatched': True}

    def _run(self, record):
        episodes = self.jobs.episodes
        identifier = record['id']
        start = time.monotonic()
        research = self.jobs.research
        def event(kind, payload): episodes.append(identifier, kind, kind, payload)
        try:
            # A key/policy change cannot race either image-bearing request.
            with research.lock:
                if not self.state()['policy_ready']: raise ValueError('Policy/key changed before dispatch.')
                package = deepcopy(self.jobs.geometry_evidence.get(record['evidence_id']))
                if package['status'] != 'ready' or package['asset_id'] != record['asset_id']:
                    raise ValueError('Evidence binding changed.')
                package['targets'] = list(record['targets'])
                package['views'] = [v for v in package['views'] if v['geometry_id'] in record['targets']]
                observed = next(e for e in episodes.events(identifier) if e['kind'] == 'observations_prepared')
                images = [{**meta, 'png': episodes.image(identifier, n)}
                          for n, meta in enumerate(observed['payload']['images'])]
                references = [s for s in record['sources'] if s['id'] in record['selected_source_ids']]
                event('policy_checked', {'sharing_disabled': True, 'basis': 'operator_confirmed_data_controls',
                    'store': False, 'room_images': False, 'raw_glb': False,
                    'max_object_nanos': 50_000_000, 'daily_nanos': 2_000_000_000})
                result, refs, provenance = self.factory(research.ledger, research.key).propose_mappings(
                    record, package, references, images, event)
                # The evidence package can have eight targets; this pilot examines
                # only three. Preserve the others as application-owned unknowns.
                result = deepcopy(result)
                result['unknown_geometry_ids'] += record['not_examined_geometry_ids']
                revision = self.jobs.geometry_evidence.save_candidates(record['evidence_id'], result, refs, provenance)
                event('candidates_persisted', {'revision_id': revision['id'], 'mappings': revision['mappings'],
                    'unknown_geometry_ids': revision['unknown_geometry_ids'],
                    'not_examined_geometry_ids': record['not_examined_geometry_ids'],
                    'capabilities_promoted': False, 'runtime_changed': False})
                episodes.finish(identifier, 'completed', candidate_revision_id=revision['id'],
                                latency_ms=round((time.monotonic()-start)*1000), error=None)
        except Exception as error:
            # Provider adapters redact their own errors. Never expose arbitrary
            # renderer/database exceptions or credentials in history.
            message = str(error) if isinstance(error, CommandError) else 'Vision pilot stopped before publication. Inspect saved history; no automatic retry.'
            episodes.finish(identifier, 'failed', error=message,
                            latency_ms=round((time.monotonic()-start)*1000))
