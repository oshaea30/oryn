"""Provider boundary: prompt -> progress -> bounded GLB. No Quest dependencies."""
import json
import math
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol

MAX_BYTES = 16 * 1024 * 1024
API = "https://api.meshy.ai/openapi/v2/text-to-3d"
PROFILES = {
    "structure": {"label": "Structure Test", "geometry_credits": 5, "texture_credits": None,
        "description": "Meshy T2 · Smart Topology · 10,000 target triangles · geometry only"},
    "quality": {"label": "Quality Test", "geometry_credits": 20, "texture_credits": 10,
        "description": "Meshy 7.1 · 10,000 target triangles · optional 2K texture"},
}


class GenerationProvider(Protocol):
    """Provider-neutral operations. Progress/task IDs are data, not runtime behavior."""
    def generate_geometry(self, prompt, profile, progress, task_created) -> bytes: ...
    def texture(self, geometry_task_id, profile, progress, task_created) -> bytes: ...
    def balance(self) -> float: ...


class GenerationError(Exception):
    pass


def validate_glb(data):
    if len(data) < 20 or len(data) > MAX_BYTES:
        raise GenerationError("GLB must be between 20 bytes and 16 MB; no model was delivered.")
    if struct.unpack_from("<III", data) != (0x46546C67, 2, len(data)):
        raise GenerationError("Provider returned an invalid or incomplete GLB.")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        # Never forward credentials or follow an arbitrary asset redirect.
        raise GenerationError("Unexpected provider redirect; inspect provider output before retrying.")


class MeshyProvider:
    def __init__(self, key, opener=None, sleep=time.sleep, clock=time.monotonic):
        self.key = key
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.sleep, self.clock = sleep, clock

    def request(self, payload=None, task_id=None, *, balance=False):
        url = "https://api.meshy.ai/openapi/v1/balance" if balance else API
        if task_id:
            if not isinstance(task_id, str) or not all(c.isalnum() or c == '-' for c in task_id) or len(task_id) > 100:
                raise GenerationError("Invalid provider task ID.")
            url += '/' + task_id
        request = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=40) as response:
                raw = response.read(1024 * 1024 + 1)
                if len(raw) > 1024 * 1024:
                    raise GenerationError("Provider response exceeded limit.")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise GenerationError("Unexpected provider response.")
                return result
        except urllib.error.HTTPError as error:
            messages = {401: "API key rejected", 402: "Insufficient API credits", 429: "Provider rate limit reached"}
            error.close()
            raise GenerationError(messages.get(error.code, "Provider HTTP error " + str(error.code)) + "; no automatic paid retry.") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            raise GenerationError("Provider request failed or timed out. Submission may have succeeded: check the provider dashboard before generating again.") from None

    def poll(self, task_id, phase, progress):
        deadline = self.clock() + 20 * 60
        while self.clock() < deadline:
            task = self.request(task_id=task_id)
            status = task.get("status")
            value = task.get("progress", 0)
            value = max(0, min(100, int(value))) if isinstance(value, (int, float)) else 0
            progress(phase, value)
            if status == "SUCCEEDED":
                return task
            if status in ("FAILED", "CANCELED", "EXPIRED"):
                raise GenerationError("Provider task " + status.lower() + "; inspect its dashboard for details. No automatic paid retry.")
            if status not in ("PENDING", "IN_PROGRESS"):
                raise GenerationError("Unknown provider task status; stopped without resubmitting.")
            self.sleep(5)
        raise GenerationError("Generation polling timed out. The provider task may still be running; do not blindly resubmit.")

    def download(self, url):
        parsed = urllib.parse.urlsplit(url or "")
        if parsed.scheme != "https" or parsed.hostname not in ("assets.meshy.ai", "cdn.meshy.ai") or parsed.username or parsed.password or parsed.port not in (None, 443):
            raise GenerationError("Provider asset URL is not on the allowed HTTPS asset hosts.")
        # Asset requests deliberately do NOT carry the API Authorization header.
        try:
            with self.opener.open(urllib.request.Request(url), timeout=90) as response:
                data = response.read(MAX_BYTES + 1)
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GenerationError("Model download failed; provider task IDs were saved for recovery.") from None
        validate_glb(data)
        return data

    def balance(self):
        value = self.request(balance=True).get("balance")
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise GenerationError("Provider returned an invalid balance.")
        return value

    def generate_geometry(self, prompt, profile, progress, task_created):
        if profile not in PROFILES:
            raise GenerationError("Unknown generation profile.")
        progress("submitting_geometry", 0)
        # No POST retries: a timeout can mean the billed task was created already.
        payload = {"mode": "preview", "prompt": prompt, "topology": "triangle",
            "target_polycount": 10000, "target_formats": ["glb"], "moderation": True}
        if profile == "structure":
            payload.update(ai_model="meshy-t2", model_type="smart-topology")
        else:
            payload.update(ai_model="meshy-7.1", model_type="standard", should_remesh=True)
        preview = self.request(payload).get("result")
        if not isinstance(preview, str) or not preview:
            raise GenerationError("No preview task ID returned; check provider dashboard before retrying.")
        task_created("preview_task_id", preview)
        result = self.poll(preview, "generating_geometry", progress)
        progress("downloading_geometry", 100)
        return self.download(result.get("model_urls", {}).get("glb"))

    def texture(self, geometry_task_id, profile, progress, task_created):
        # T2 is not listed among refine models; do not silently switch models or
        # spend credits exploring undocumented cross-model compatibility.
        if profile != "quality":
            raise GenerationError("Texturing is enabled only for Quality Test; T2 refine compatibility is unverified.")
        progress("submitting_texture", 0)
        refined = self.request({"mode": "refine", "preview_task_id": geometry_task_id, "enable_pbr": False,
            "texture_resolution": "2k", "target_formats": ["glb"], "moderation": True}).get("result")
        if not isinstance(refined, str) or not refined:
            raise GenerationError("No texture task ID returned; check provider dashboard before retrying.")
        task_created("refine_task_id", refined)
        result = self.poll(refined, "texturing", progress)
        progress("downloading_texture", 100)
        return self.download(result.get("model_urls", {}).get("glb"))
