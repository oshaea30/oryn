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

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r"^[a-f0-9]{32}$")
TERMINAL = {"loaded_on_quest", "ready", "failed", "texture_failed", "delivery_failed", "waiting_for_headset", "interrupted"}
VARIANT_FILES = {"geometry": "model.glb", "textured": "textured.glb"}


class Jobs:
    def __init__(self, root, fixture, key="", provider=MeshyProvider, transport=None):
        self.root, self.fixture = Path(root), Path(fixture)
        self.root.mkdir(parents=True, exist_ok=True)
        self.key, self.provider = key, provider
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

    def update(self, job_id, **fields):
        with self.lock:
            self.jobs[job_id].update(fields, updated=time.time())
            folder = self.root / job_id
            folder.mkdir(exist_ok=True)
            temp = folder / "job.json.partial"
            temp.write_text(json.dumps(self.jobs[job_id], indent=2))
            temp.replace(folder / "job.json")

    def state(self):
        with self.lock:
            return {"configured": bool(self.key), "busy": self.busy, "provider": "Meshy", "profiles": PROFILES,
                "jobs": [dict(job) for job in sorted(self.jobs.values(), key=lambda job: job["created"], reverse=True)]}

    def submit(self, body):
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
                return dict(self.jobs[job_id])  # Idempotent retry, including after restart.
            if self.busy:
                raise ValueError("A job is already running. Wait before starting another.")
            if len(self.jobs) >= 20:
                raise ValueError("This prototype keeps at most 20 jobs. Archive local job folders before creating more.")
            if shutil.disk_usage(self.root).free < 512 * 1024 * 1024:
                raise ValueError("Free at least 512 MB before generating assets.")
            if mode == "meshy" and (not self.key or body.get("approve_paid") is not True):
                raise ValueError("Configure the local API key and explicitly approve this paid generation first.")
            if mode == "meshy" and body.get("approved_credits") != PROFILES[profile]["geometry_credits"]:
                raise ValueError("Approve the credit estimate for the selected geometry profile.")
            job = {"id": job_id, "prompt": prompt.strip() if mode == "meshy" else "TEST ONLY: existing avocado — not AI-generated",
                "demo": mode == "demo", "profile": profile, "provider": "meshy", "variants": {},
                "approved_geometry_credits": 0 if mode == "demo" else PROFILES[profile]["geometry_credits"],
                "status": "queued", "progress": 0, "created": time.time(), "error": ""}
            self.jobs[job_id] = job
            self.update(job_id)
            self.busy = True
            key = self.key  # Snapshot; never written to a job or sent to Quest.
            threading.Thread(target=self.work, args=(job_id, key), daemon=True).start()
            return dict(job)

    def progress(self, job_id, phase, amount, **extra):
        self.update(job_id, status=phase, progress=amount, **extra)

    def work(self, job_id, key):
        job = self.jobs[job_id]
        try:
            if job["demo"]:
                self.progress(job_id, "reading_test_fixture", 0)
                data = self.fixture.read_bytes()
            else:
                data = self.provider(key).generate_geometry(job["prompt"], job["profile"],
                    lambda phase, amount: self.progress(job_id, phase, amount),
                    lambda name, value: self.update(job_id, **{name: value}))
            self.save_asset(job_id, "geometry", data)
            # The test button explicitly requests delivery. Paid generation stops
            # after inspection: no implicit texturing or headset transfer.
            if job["demo"]:
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
            self.update(job_id, status="ready", progress=100, bytes=len(data), variants=variants)

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
            self.update(job_id, delivery_variant=variant)
            receipt = self.transport.deliver(self.root / job_id / VARIANT_FILES[variant], self.jobs[job_id],
                lambda phase, amount, **extra: self.progress(job_id, phase, amount, **extra))
            if receipt:
                with self.lock:
                    self.receipts[job_id] = receipt
                    self.update(job_id, serial=receipt[0])
        except DeliveryError as error:
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

    def respond(self, status, value, html=False):
        data = value if html else json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8" if html else "application/json")
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
            return self.respond(200, (Path(__file__).parent / "index.html").read_bytes(), html=True)
        if self.path == "/health":
            return self.respond(200, {"status": "ok"})
        if self.path == "/api/state":
            return self.respond(200, dict(self.server.jobs.state(), token=self.server.token))
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
                key = body.get("key", "")
                if not isinstance(key, str) or not 10 <= len(key.strip()) <= 500 or '\n' in key or '\r' in key:
                    raise ValueError("Enter a valid API key")
                with self.server.jobs.lock:
                    self.server.jobs.key = key.strip()
                return self.respond(200, {"configured": True})
            if self.path == "/api/generate":
                return self.respond(202, self.server.jobs.submit(body))
            if self.path == "/api/deliver":
                self.server.jobs.redeliver(body.get("id"), body.get("variant", "geometry"))
                return self.respond(202, {"accepted": True})
            if self.path == "/api/texture":
                return self.respond(202, self.server.jobs.texture(body))
            if self.path == "/api/balance":
                return self.respond(200, self.server.jobs.balance())
            return self.respond(404, {"error": "Not found"})
        except GenerationError as error:
            return self.respond(400, {"error": str(error)})
        except (ValueError, TypeError):
            # Validation messages are controlled locally; never echo request bodies.
            return self.respond(400, {"error": "Request rejected. Check key, profile/credit approval, prompt length, pending operations, and available disk space. T2 texture and duplicate texture attempts are blocked."})
        except Exception:
            return self.respond(500, {"error": "Local operation failed. Check job history before retrying; paid tasks never auto-retry."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    os.umask(0o077)
    jobs = Jobs(ROOT / ".oryn-generation", ROOT / "RuntimeAssets/Avocado.glb", os.environ.get("ORYN_MESHY_API_KEY", ""))
    server = Server(args.port, jobs)
    def receipts():
        while True:
            time.sleep(5)
            jobs.refresh_receipts()
    threading.Thread(target=receipts, daemon=True).start()
    print(f"Oryn generation console: {server.origin}", flush=True)
    print("Local only. API key stays in memory. Paid jobs require per-job approval. Ctrl+C stops.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
