"""Oryn's local generation console. Python standard library; no cloud server."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from providers import GenerationError, MeshyProvider, PROFILES, validate_glb
from asset_inspection import inspect_glb
from transport import AdbTransport, DeliveryError
from credential_store import CredentialError, MacKeychain, validate_key
from ingestion import prepare_asset, summary as ingestion_summary
from workflow import WorkflowStore, summary as workflow_summary
from geometry_evidence import GeometryEvidenceStore
from investigation_episodes import Episodes
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r"^[a-f0-9]{32}$")
TERMINAL = {"loaded_on_quest", "ready", "failed", "texture_failed", "delivery_failed", "waiting_for_headset", "interrupted"}
VARIANT_FILES = {"geometry": "model.glb", "textured": "textured.glb"}
EXPERIENCE_CREDITS = 5
EXPERIENCE_DAILY_CREDITS = 50


class ExperienceError(ValueError):
    """Controlled, user-facing request errors; never provider exception text."""


def object_prompt(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 800:
        raise ExperienceError("Describe an object in 1–800 characters.")
    # This is an object-request box, not a general assistant or semantic search.
    prompt = re.sub(r"^(?:please\s+)?(?:show me|generate|create|make)(?:\s+|$)", "", value.strip(), flags=re.I).strip()
    if not prompt:
        raise ExperienceError("Include the object you want to see.")
    return prompt


def prompt_key(value):
    return " ".join(object_prompt(value).casefold().split())


class Jobs:
    def __init__(self, root, fixture, key="", provider=MeshyProvider, transport=None, credential_store=None):
        self.root, self.fixture = Path(root), Path(fixture)
        self.root.mkdir(parents=True, exist_ok=True)
        self.workflows = WorkflowStore(self.root / 'workflows.sqlite3')
        self.geometry_evidence = GeometryEvidenceStore(self.workflows)
        self.episodes = Episodes(self.workflows)
        self.vision = None  # Main wires bounded, explicit episode dispatch.
        self.assessments = None
        self.research = None  # Main wires live providers after local-only backfill.
        self.key, self.provider = key, provider
        self.credential_store = credential_store
        self.key_storage, self.credential_error = "session" if key else "missing", ""
        if not key and credential_store is not None:
            try:
                self.key = credential_store.load()
                if self.key:
                    self.key_storage = "keychain"
            except CredentialError as error:
                self.credential_error = str(error)
        self.transport = transport or AdbTransport()
        self.lock = threading.RLock()
        self.jobs, self.busy = {}, False
        self.receipts = {}
        for path in sorted(self.root.glob("*/job.json")):
            try:
                job = json.loads(path.read_text())
                if not ID.fullmatch(job["id"]):
                    continue
                self.jobs[job["id"]] = job
                if job["status"] == "waiting_for_headset":
                    if isinstance(job.get("delivery_id"), str) and ID.fullmatch(job["delivery_id"]) and job.get("serial"):
                        self.receipts[job["id"]] = (job["serial"], job["delivery_id"])
                    else:
                        self.update(job["id"], status="delivery_failed", error="Service restarted during transfer; inspect headset before sending again (sending twice can create a second copy).")
                if job["status"] not in TERMINAL:
                    self.update(job["id"], status="interrupted", error="Service restarted; no tasks were resubmitted. Check saved provider task IDs before retrying.")
                # Older cached jobs are inspected locally; never regenerate or send
                # during migration. Preserve their existing receipt/task state.
                cached = self.root / job["id"] / "model.glb"
                if not job.get("variants") and cached.exists():
                    try:
                        report = inspect_glb(cached.read_bytes())
                        self.update(job["id"], variants={"geometry": report}, legacy=True)
                    except GenerationError:
                        self.update(job["id"], inspection_error="Cached model did not pass structural inspection.")
            except (OSError, ValueError, KeyError, TypeError):
                continue
        # Local-only backfill: preserve delivery history, source files and records.
        # Never generate, deliver or overwrite an existing ingestion revision here.
        for job_id, job in self.jobs.items():
            for variant, report in list(job.get('variants', {}).items()):
                if variant in VARIANT_FILES and report.get('preflight') == 'PASS':
                    try:
                        self.prepare_ingestion(job_id, variant)
                    except (OSError, ValueError, KeyError, TypeError, GenerationError):
                        self.update(job_id, _preserve_updated=True, ingestion_error='Saved asset ingestion failed validation; original and existing manifest preserved. No automatic delivery.')

    def update(self, job_id, *, _preserve_updated=False, **fields):
        with self.lock:
            stamp = self.jobs[job_id].get('updated', self.jobs[job_id]['created']) if _preserve_updated else time.time()
            self.jobs[job_id].update(fields, updated=stamp)
            folder = self.root / job_id
            folder.mkdir(exist_ok=True)
            temp = folder / "job.json.partial"
            temp.write_text(json.dumps(self.jobs[job_id], indent=2))
            temp.replace(folder / "job.json")

    def refresh_episode_history(self):
        """Local metadata only. This does not claim or execute vision work."""
        if self.research is None:return
        with self.lock:
            for job in self.jobs.values():
                if not job.get('research_id') or not job.get('geometry_evidence_id'):continue
                try:
                    evidence=self.geometry_evidence.get(job['geometry_evidence_id'])
                    research=self.research.engine.get(job['research_id'])
                    if evidence['status']!='ready' or research['status']!='reference_notes_ready':continue
                    episode=self.episodes.ensure(evidence,research)
                    if job.get('episode_id')!=episode['id']:
                        self.update(job['id'],_preserve_updated=True,episode_id=episode['id'])
                except Exception:
                    continue  # A missing historical record never invalidates delivery.

    def state(self):
        with self.lock:
            jobs = [dict(job) for job in sorted(self.jobs.values(), key=lambda job: job['created'], reverse=True)]
            for job in jobs:
                if job.get('geometry_evidence_id'):
                    try:
                        job['geometry_evidence'] = self.geometry_evidence.summary(job['geometry_evidence_id'])
                    except Exception:
                        job['geometry_evidence_error'] = 'Local geometry evidence unavailable; model interaction is unchanged.'
            if self.research is not None:
                for job in jobs:
                    if job.get('research_id'):
                        try:
                            job['research'] = self.research.summary(job['research_id'])
                        except Exception:
                            job['research_error'] = 'Saved research is unavailable; model interaction remains available.'
            return {"configured": bool(self.key), "busy": self.busy, "provider": "Meshy", "profiles": PROFILES,
                "keyStorage": self.key_storage, "credentialError": self.credential_error,
                "experienceContract": 1, "deliveryPending": bool(self.receipts),
                "experiencePolicy": {"credits_per_generation": EXPERIENCE_CREDITS,
                    "rolling_day_limit": EXPERIENCE_DAILY_CREDITS, "reserved_last_day": self.reserved_credits()},
                "jobs": jobs, 'researchConnection': self.research.state() if self.research is not None else None}

    def configure_key(self, value):
        key = validate_key(value)
        with self.lock:
            if self.credential_store is not None:
                # Persist first: a denied/locked Keychain must not report success.
                self.credential_store.save(key)
            self.key = key
            self.key_storage = "keychain" if self.credential_store is not None else "session"
            self.credential_error = ""
            return {"configured": True, "keyStorage": self.key_storage}

    def reserved_credits(self):
        # Persisted before dispatch; failed/uncertain calls retain their reservation.
        # Include lab spending too. This is a local cap, not account-wide billing.
        cutoff = time.time() - 86400
        return sum(job.get("approved_geometry_credits", 0) + job.get("approved_texture_credits", 0)
            for job in self.jobs.values() if job.get("updated", job["created"]) >= cutoff)

    def request_object(self, body):
        """A direct user request authorizes one bounded generate/load operation."""
        prompt = object_prompt(body.get("prompt"))
        # Client cannot escalate model/profile, add texturing or change the cap.
        return self.submit({"request_id": body.get("request_id"), "mode": "meshy",
            "profile": "structure", "prompt": prompt}, experience=True)

    def submit(self, body, *, experience=False):
        job_id = body.get("request_id", "")
        if not isinstance(job_id, str) or not ID.fullmatch(job_id):
            raise ValueError("A unique request_id is required.")
        mode = body.get("mode")
        profile = body.get("profile", "structure")
        if not isinstance(profile, str) or profile not in PROFILES:
            raise ValueError("Choose Structure Test or Quality Test.")
        prompt = body.get("prompt", "")
        if mode not in ("meshy", "demo"):
            raise ValueError("Choose Meshy generation or the explicit test-model delivery.")
        if mode == "meshy" and (not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 800):
            raise ValueError("Enter an object description of 1-800 characters.")
        with self.lock:
            if job_id in self.jobs:
                existing = self.jobs[job_id]
                if experience and (not existing.get("experience") or prompt_key(existing["prompt"]) != prompt_key(prompt)):
                    raise ExperienceError("This request ID belongs to a different request. Check the existing result.")
                return dict(self.jobs[job_id])  # Idempotent retry, including after restart.
            if self.busy or (experience and self.receipts):
                raise ValueError("A job is already running. Wait before starting another.")
            if len(self.jobs) >= 20:
                raise ValueError("This prototype keeps at most 20 jobs. Archive local job folders before creating more.")
            if shutil.disk_usage(self.root).free < 512 * 1024 * 1024:
                raise ValueError("Free at least 512 MB before generating assets.")
            reuse = None
            if experience:
                for saved in sorted(self.jobs.values(), key=lambda j: j["created"], reverse=True):
                    report = saved.get("variants", {}).get("geometry", {})
                    if not saved.get("demo") and saved.get("profile") == "structure" and report.get("preflight") == "PASS" and prompt_key(saved["prompt"]) == prompt_key(prompt):
                        reuse = saved
                        break
                if not reuse and not self.key:
                    raise ExperienceError("Add the Meshy key once in connection settings, then request your object.")
                if not reuse and (PROFILES["structure"]["geometry_credits"] != EXPERIENCE_CREDITS or self.reserved_credits() + EXPERIENCE_CREDITS > EXPERIENCE_DAILY_CREDITS):
                    raise ExperienceError("The automatic generation credit limit has been reached. Saved assets remain available; nothing was charged.")
            if not experience and mode == "meshy" and (not self.key or body.get("approve_paid") is not True):
                raise ValueError("Configure the local API key and explicitly approve this paid generation first.")
            if not experience and mode == "meshy" and body.get("approved_credits") != PROFILES[profile]["geometry_credits"]:
                raise ValueError("Approve the credit estimate for the selected geometry profile.")
            job = {"id": job_id, "prompt": prompt.strip() if mode == "meshy" else "TEST ONLY: existing avocado — not AI-generated",
                "demo": mode == "demo", "profile": profile, "provider": "meshy", "variants": {},
                "approved_geometry_credits": 0 if mode == "demo" or reuse else PROFILES[profile]["geometry_credits"],
                "experience": experience, "reused_from": reuse["id"] if reuse else None,
                "status": "queued", "progress": 0, "created": time.time(), "error": ""}
            self.jobs[job_id] = job
            self.update(job_id)
            if experience:
                # Bounded routing seam. Hard credit, eligibility and integrity gates
                # above/below remain application-owned, not model permissions.
                try:
                    decision = self.workflows.decide_local(job_id, 'asset_route',
                        [{'id': job_id, 'exact_saved_match': reuse is not None}])
                    expected = 'library' if reuse else 'generation'
                    if decision['results'][0]['action'] != expected:
                        raise ValueError('Unsupported acquisition route.')
                    self.update(job_id, route_decision_id=decision['id'])
                except Exception:
                    self.update(job_id, status='failed', error='Acquisition routing failed; no provider call was made.')
                    raise ExperienceError('Acquisition routing failed; nothing was dispatched.') from None
            self.busy = True
            key = self.key  # Snapshot; never written to a job or sent to Quest.
            threading.Thread(target=self.work, args=(job_id, key), daemon=True).start()
            return dict(job)

    def progress(self, job_id, phase, amount, **extra):
        self.update(job_id, status=phase, progress=amount, **extra)

    def work(self, job_id, key):
        job = self.jobs[job_id]
        try:
            if job.get("reused_from"):
                self.progress(job_id, "loading_saved_asset", 0)
                source = self.jobs[job["reused_from"]]
                data = (self.root / source["id"] / "model.glb").read_bytes()
                report = inspect_glb(data)
                if report["preflight"] != "PASS" or report["sha256"] != source["variants"]["geometry"]["sha256"]:
                    raise GenerationError("Saved asset changed or failed inspection. Stopped without spending credits.")
            elif job["demo"]:
                self.progress(job_id, "reading_test_fixture", 0)
                data = self.fixture.read_bytes()
            else:
                data = self.provider(key).generate_geometry(job["prompt"], job["profile"],
                    lambda phase, amount: self.progress(job_id, phase, amount),
                    lambda name, value: self.update(job_id, **{name: value}))
            self.save_asset(job_id, "geometry", data)
            # Request mode includes delivery; the developer lab still stops at
            # inspection. Neither path silently adds a texturing task.
            if job["demo"] or job.get("experience"):
                self.deliver(job_id, "geometry")
        except GenerationError as error:
            self.update(job_id, status="failed", error=str(error))
        except Exception:
            # Do not reflect provider exceptions/URLs/headers/secrets to browser logs.
            self.update(job_id, status="failed", error="Local generation step failed. Existing provider task IDs are saved; no automatic retry was made.")
        finally:
            with self.lock:
                self.busy = False

    def save_asset(self, job_id, variant, data):
        validate_glb(data)
        path = self.root / job_id / VARIANT_FILES[variant]
        path.with_suffix(".partial").write_bytes(data)
        path.with_suffix(".partial").replace(path)
        self.progress(job_id, "inspecting_" + variant, 100)
        report = inspect_glb(data)
        report_path = path.with_suffix(".inspection.json")
        report_path.with_suffix(".partial").write_text(json.dumps(report, indent=2))
        report_path.with_suffix(".partial").replace(report_path)
        with self.lock:
            variants = dict(self.jobs[job_id].get("variants", {}))
            variants[variant] = report
            self.update(job_id, status="preparing_assembly", progress=100, bytes=len(data), variants=variants)
        if report['preflight'] == 'PASS':
            self.prepare_ingestion(job_id, variant)
        self.update(job_id, status='ready')
        if variant == 'geometry' and self.jobs[job_id].get('experience') and self.research is not None:
            try:
                self.research.enqueue_job(job_id)  # SQLite only; remote work runs separately.
            except Exception:
                self.update(job_id, _preserve_updated=True, research_error='Research could not be queued; model delivery continues.')

    def prepare_ingestion(self, job_id, variant):
        job = self.jobs[job_id]
        provenance = {'job_id': job_id, 'provider': None if job.get('demo') else job.get('provider'), 'profile': job.get('profile'),
            'provider_task_id': job.get('preview_task_id') if variant == 'geometry' else job.get('refine_task_id'),
            'reused_from': job.get('reused_from')}
        source = self.root / job_id / VARIANT_FILES[variant]
        if inspect_glb(source.read_bytes())['sha256'] != job['variants'][variant]['sha256']:
            raise GenerationError('Source no longer matches the saved generation report.')
        manifest, chosen = prepare_asset(self.root / job_id, variant, provenance)
        # An importable but replaced source must not silently acquire a new identity.
        if manifest['source_geometry']['sha256'] != job['variants'][variant]['sha256']:
            raise GenerationError('Source no longer matches the saved generation report.')
        ingestions = dict(job.get('ingestions', {}))
        ingestions[variant] = ingestion_summary(manifest)
        self.update(job_id, _preserve_updated=True, ingestions=ingestions, ingestion_error='')
        # Cheap, deterministic analysis is reusable across deliveries and restarts.
        # A failed investigation must not erase geometry or prevent interaction.
        try:
            investigation = self.workflows.prepare(manifest)
            investigations = dict(job.get('investigations', {}))
            investigations[variant] = workflow_summary(investigation)
            self.update(job_id, _preserve_updated=True, investigations=investigations, investigation_error='')
            if variant == 'geometry' and not job.get('demo') and investigation.get('investigation_targets'):
                try:
                    evidence_id = self.geometry_evidence.enqueue(source, manifest, investigation['investigation_targets'])
                    self.update(job_id, _preserve_updated=True, geometry_evidence_id=evidence_id, geometry_evidence_error='')
                except Exception:
                    self.update(job_id, _preserve_updated=True, geometry_evidence_error='Local geometry evidence could not be queued; model interaction is unchanged.')
        except Exception:
            self.update(job_id, _preserve_updated=True, investigation_error='Investigation preparation unavailable; model capabilities are unchanged.')
        return manifest, chosen

    def texture(self, body):
        job_id, request_id = body.get("id"), body.get("request_id")
        if not isinstance(job_id, str) or not isinstance(request_id, str) or not ID.fullmatch(request_id):
            raise ValueError("Valid job and texture request IDs required.")
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                raise ValueError("Unknown job.")
            if job.get("texture_request_id") == request_id:
                return dict(job)  # Safe after a lost response or service restart.
            if job.get("texture_request_id") or job.get("refine_task_id"):
                raise ValueError("A texture task was already attempted. Check provider history; no paid retry is allowed for this job.")
            if self.busy or job_id in self.receipts:
                raise ValueError("Wait for the current operation or headset receipt.")
            if job.get("demo") or job.get("profile") != "quality" or not job.get("preview_task_id") or "geometry" not in job.get("variants", {}):
                raise ValueError("Texturing requires completed Quality Test geometry. T2 texturing is not yet verified.")
            if not self.key or body.get("approve_paid") is not True or body.get("approved_credits") != 10:
                raise ValueError("Explicitly approve the separate 10-credit texture task.")
            if shutil.disk_usage(self.root).free < 512 * 1024 * 1024:
                raise ValueError("Free at least 512 MB before texturing.")
            self.update(job_id, texture_request_id=request_id, approved_texture_credits=10,
                status="queued_texture", progress=0, error="")
            self.busy = True
            threading.Thread(target=self.texture_work, args=(job_id, self.key), daemon=True).start()
            return dict(job)

    def texture_work(self, job_id, key):
        job = self.jobs[job_id]
        try:
            data = self.provider(key).texture(job["preview_task_id"], job["profile"],
                lambda phase, amount: self.progress(job_id, phase, amount),
                lambda name, value: self.update(job_id, **{name: value}))
            self.save_asset(job_id, "textured", data)
        except GenerationError as error:
            self.update(job_id, status="texture_failed", error=str(error))
        except Exception:
            self.update(job_id, status="texture_failed", error="Texture step failed. Original geometry is preserved. Check provider task history; no automatic paid retry.")
        finally:
            with self.lock:
                self.busy = False

    def balance(self):
        with self.lock:
            key = self.key
        if not key:
            raise ValueError("Configure an API key in the local console first.")
        return {"balance": self.provider(key).balance(), "checked_at": time.time()}

    def deliver(self, job_id, variant):
        try:
            report = self.jobs[job_id].get("variants", {}).get(variant)
            if not report or report["preflight"] != "PASS":
                raise DeliveryError("Model failed static preflight. Inspect the report before delivery.")
            manifest, chosen = self.prepare_ingestion(job_id, variant)
            self.update(job_id, delivery_variant=variant, delivery_asset_sha256=manifest['runtime']['sha256'])
            receipt = self.transport.deliver(chosen, self.jobs[job_id],
                lambda phase, amount, **extra: self.progress(job_id, phase, amount, **extra))
            if receipt:
                with self.lock:
                    self.receipts[job_id] = receipt
                    self.update(job_id, serial=receipt[0])
        except (DeliveryError, GenerationError) as error:
            self.update(job_id, status="delivery_failed", error=str(error))

    def redeliver(self, job_id, variant="geometry"):
        with self.lock:
            if not isinstance(variant, str) or variant not in VARIANT_FILES:
                raise ValueError("Choose a saved geometry or textured variant.")
            if not isinstance(job_id, str) or job_id not in self.jobs or variant not in self.jobs[job_id].get("variants", {}):
                raise ValueError("No completed local model for this job.")
            if self.busy or job_id in self.receipts:
                raise ValueError("An operation or headset receipt is pending; open Oryn in the headset first.")
            # Recheck the exact saved bytes, not a stale report, before transport.
            path = self.root / job_id / VARIANT_FILES[variant]
            report = inspect_glb(path.read_bytes())
            if report["preflight"] != "PASS" or report["sha256"] != self.jobs[job_id]["variants"][variant]["sha256"]:
                raise ValueError("Cached model changed or failed preflight; delivery blocked.")
            self.busy = True
            self.update(job_id, error="")
        def send():
            try:
                self.deliver(job_id, variant)
            except Exception:
                self.update(job_id, status="delivery_failed", error="Delivery failed; generated model remains saved locally.")
            finally:
                with self.lock:
                    self.busy = False
        threading.Thread(target=send, daemon=True).start()

    def refresh_receipts(self):
        with self.lock:
            pending = dict(self.receipts)
        for job_id, (serial, delivery_id) in pending.items():
            receipt = self.transport.receipt(serial, delivery_id)
            if receipt:
                ok = receipt.get("status") == "loaded"
                self.update(job_id, status="loaded_on_quest" if ok else "delivery_failed",
                    error="" if ok else "Quest rejected the model: " + str(receipt.get("error", "unknown error"))[:200])
                with self.lock:
                    self.receipts.pop(job_id, None)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, port, jobs):
        super().__init__(("127.0.0.1", port), Handler)
        self.jobs = jobs
        self.token = secrets.token_urlsafe(32)
        self.origin = f"http://127.0.0.1:{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # No keys, prompts or signed URLs in HTTP logs.

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def respond(self, status, value, html=False, content_type=None):
        data = value if html or content_type else json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type or ("text/html; charset=utf-8" if html else "application/json"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.valid_host():
            return self.respond(403, {"error": "Local console only"})
        if self.path == "/":
            return self.respond(200, (Path(__file__).parent / "experience.html").read_bytes(), html=True)
        if self.path == "/lab":
            return self.respond(200, (Path(__file__).parent / "index.html").read_bytes(), html=True)
        if urlsplit(self.path).path == '/geometry-evidence':
            return self.respond(200, (Path(__file__).parent / 'geometry_evidence.html').read_bytes(), html=True)
        if urlsplit(self.path).path == '/investigation-episode':
            return self.respond(200,(Path(__file__).parent/'investigation_episode.html').read_bytes(),html=True)
        if urlsplit(self.path).path == '/api/episode':
            try:
                query=parse_qs(urlsplit(self.path).query,strict_parsing=True)
                if set(query)!={'id'} or len(query['id'])!=1 or not re.fullmatch('[a-f0-9]{64}',query['id'][0]):raise ValueError()
                identifier=query['id'][0]
                record=self.server.jobs.episodes.get(identifier)
                record['assessment']=self.server.jobs.assessments.get(identifier) if self.server.jobs.assessments else None
                record['vision']=self.server.jobs.vision.state() if self.server.jobs.vision else {'connected':False,'policy_ready':False}
                if self.server.jobs.research is not None:
                    record['budget']=self.server.jobs.research.ledger.investigation_summary(record['asset_id'])
                return self.respond(200,{**record,'events':self.server.jobs.episodes.events(identifier)})
            except (ValueError,KeyError):return self.respond(404,{'error':'Unknown episode.'})
        if urlsplit(self.path).path == '/api/episode-image':
            try:
                query=parse_qs(urlsplit(self.path).query,strict_parsing=True)
                if set(query)!={'id','piece'} or any(len(v)!=1 for v in query.values()) or not re.fullmatch('[a-f0-9]{64}',query['id'][0]):raise ValueError()
                return self.respond(200,self.server.jobs.episodes.image(query['id'][0],int(query['piece'][0])),content_type='image/png')
            except (ValueError,KeyError):return self.respond(404,{'error':'Unknown episode image.'})
        if urlsplit(self.path).path in {'/api/geometry-evidence','/api/geometry-view'}:
            try:
                query = parse_qs(urlsplit(self.path).query, strict_parsing=True)
                is_view = urlsplit(self.path).path == '/api/geometry-view'
                if set(query) != ({'id','piece'} if is_view else {'id'}) or any(len(v)!=1 for v in query.values()) or not re.fullmatch(r'[a-f0-9]{64}',query['id'][0]):
                    raise ValueError('Invalid evidence ID.')
                if is_view:
                    svg = self.server.jobs.geometry_evidence.view(query['id'][0],int(query['piece'][0]))
                    return self.respond(200,svg.encode(),content_type='image/svg+xml')
                return self.respond(200,self.server.jobs.geometry_evidence.report(query['id'][0]))
            except (ValueError,KeyError):
                return self.respond(404,{'error':'Geometry evidence unavailable.'})
        if self.path == "/health":
            return self.respond(200, {"status": "ok"})
        if self.path == "/api/state":
            return self.respond(200, dict(self.server.jobs.state(), token=self.server.token))
        if self.path == '/api/workflow-metrics':
            return self.respond(200, self.server.jobs.workflows.metrics())
        if self.path.startswith('/api/workflow?'):
            try:
                query = parse_qs(urlsplit(self.path).query, strict_parsing=True)
                if set(query) != {'id'} or len(query['id']) != 1 or not re.fullmatch(r'[a-f0-9]{64}', query['id'][0]):
                    raise ValueError('Invalid investigation ID.')
                return self.respond(200, self.server.jobs.workflows.report(query['id'][0]))
            except ValueError:
                return self.respond(404, {'error': 'Unknown investigation.'})
        self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if not self.valid_host() or self.headers.get("Origin", self.server.origin) != self.server.origin or not secrets.compare_digest(self.headers.get("X-Oryn-Token", ""), self.server.token):
            return self.respond(403, {"error": "Invalid local request"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192 or self.headers.get("Content-Type") != "application/json":
                raise ValueError("Expected a small JSON request")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Expected an object")
            if self.path == "/api/key":
                return self.respond(200, self.server.jobs.configure_key(body.get("key", "")))
            if self.path == '/api/research-key' and self.server.jobs.research is not None:
                return self.respond(200, self.server.jobs.research.configure_key(body.get('key','')))
            if self.path == '/api/investigate' and self.server.jobs.research is not None:
                return self.respond(202, self.server.jobs.research.enqueue_job(body.get('id')))
            if self.path == '/api/episode-review':
                if set(body)!={'episode_id','review'}:raise ValueError('Invalid review request.')
                event=self.server.jobs.episodes.review(body['episode_id'],body['review'],self.server.jobs.geometry_evidence)
                return self.respond(200,{'event_id':event})
            if self.path == '/api/vision-policy' and self.server.jobs.vision is not None:
                return self.respond(200,self.server.jobs.vision.configure_policy(body))
            if self.path == '/api/investigate-episode' and self.server.jobs.vision is not None:
                if set(body)!={'episode_id'} or not isinstance(body['episode_id'],str) or not re.fullmatch('[a-f0-9]{64}',body['episode_id']):raise ValueError('Invalid episode ID.')
                return self.respond(202,self.server.jobs.vision.start_episode(body['episode_id']))
            if self.path == '/api/assess-candidates' and self.server.jobs.assessments is not None:
                if set(body)!={'episode_id'} or not isinstance(body['episode_id'],str) or not re.fullmatch('[a-f0-9]{64}',body['episode_id']):raise ValueError('Invalid episode ID.')
                return self.respond(202,self.server.jobs.assessments.start_episode(body['episode_id']))
            if self.path == '/api/prepare-episode-evidence':
                if set(body)!={'episode_id'} or not isinstance(body['episode_id'],str) or not re.fullmatch('[a-f0-9]{64}',body['episode_id']):raise ValueError('Invalid episode ID.')
                return self.respond(200,self.server.jobs.episodes.prepare_local(body['episode_id'],self.server.jobs.geometry_evidence))
            if self.path == "/api/generate":
                return self.respond(202, self.server.jobs.submit(body))
            if self.path == "/api/request-object":
                return self.respond(202, self.server.jobs.request_object(body))
            if self.path == "/api/deliver":
                self.server.jobs.redeliver(body.get("id"), body.get("variant", "geometry"))
                return self.respond(202, {"accepted": True})
            if self.path == "/api/texture":
                return self.respond(202, self.server.jobs.texture(body))
            if self.path == "/api/balance":
                return self.respond(200, self.server.jobs.balance())
            return self.respond(404, {"error": "Not found"})
        except (GenerationError, ExperienceError, CredentialError) as error:
            return self.respond(400, {"error": str(error)})
        except (ValueError, TypeError):
            # Validation messages are controlled locally; never echo request bodies.
            return self.respond(400, {"error": "Request rejected. Check connection settings, prompt length, pending operations and available disk space. The developer lab also requires matching credit approval."})
        except Exception:
            return self.respond(500, {"error": "Local operation failed. Check job history before retrying; paid tasks never auto-retry."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    os.umask(0o077)
    jobs = Jobs(ROOT / ".oryn-generation", ROOT / "RuntimeAssets/Avocado.glb", os.environ.get("ORYN_MESHY_API_KEY", ""), credential_store=MacKeychain())
    from research_service import ResearchService
    jobs.research = ResearchService(jobs, credential_store=MacKeychain(account=b'openai-api-key'),
        key=os.environ.get('ORYN_OPENAI_API_KEY',''))
    server = Server(args.port, jobs)
    from vision_service import VisionService
    jobs.vision = VisionService(jobs)
    from candidate_assessment import CandidateAssessmentService
    jobs.assessments = CandidateAssessmentService(jobs)
    jobs.research.start()
    jobs.geometry_evidence.start()
    def receipts():
        while True:
            time.sleep(5)
            jobs.refresh_receipts()
            jobs.refresh_episode_history()
    threading.Thread(target=receipts, daemon=True).start()
    print(f"Oryn generation console: {server.origin}", flush=True)
    print("Local only. Request mode automatically generates and delivers within its credit cap. Developer lab remains staged. Ctrl+C stops.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        jobs.research.stop()
        jobs.geometry_evidence.stop()
        server.server_close()


if __name__ == "__main__":
    main()
