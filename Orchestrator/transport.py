"""USB transport. Receipts distinguish file transfer from actual headset import."""
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

ADB = "/Applications/Unity/Hub/Editor/6000.6.3f1-arm64/PlaybackEngines/AndroidPlayer/SDK/platform-tools/adb"
INBOX = "/sdcard/Android/data/com.oryn.milestoneone/files/GenerationInbox"


class DeliveryError(Exception):
    pass


class AdbTransport:
    def __init__(self, adb=ADB, run=subprocess.run, sleep=time.sleep):
        self.adb, self.run, self.sleep = adb, run, sleep

    def command(self, *args):
        try:
            result = self.run([self.adb, *args], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            raise DeliveryError("ADB unavailable/timed out. Connect and authorize the Quest; model remains saved on Mac.") from None
        if result.returncode:
            raise DeliveryError("Quest command failed. Connect one authorized Quest; model remains saved on Mac.")
        return result.stdout

    def deliver(self, model_path, job, progress):
        rows = [line.split() for line in self.command("devices").splitlines()[1:] if line.strip()]
        devices = [row[0] for row in rows if len(row) >= 2 and row[1] == "device"]
        if len(devices) != 1:
            raise DeliveryError("Connect exactly one authorized Quest, then click Send to Quest. No regeneration needed.")
        serial = devices[0]
        delivery_id = uuid.uuid4().hex
        manifest = {"id": delivery_id, "job_id": job["id"], "sha256": hashlib.sha256(Path(model_path).read_bytes()).hexdigest(),
            "demo": job["demo"]}
        manifest_path = Path(model_path).parent / (delivery_id + ".json")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        progress("transferring", 100, delivery_id=delivery_id)
        self.command("-s", serial, "shell", "mkdir", "-p", INBOX)
        self.command("-s", serial, "push", str(model_path), f"{INBOX}/{delivery_id}.glb.partial")
        self.command("-s", serial, "shell", "mv", f"{INBOX}/{delivery_id}.glb.partial", f"{INBOX}/{delivery_id}.glb")
        self.command("-s", serial, "push", str(manifest_path), f"{INBOX}/{delivery_id}.json.partial")
        # Publishing the manifest last makes delivery atomic from the client's view.
        self.command("-s", serial, "shell", "mv", f"{INBOX}/{delivery_id}.json.partial", f"{INBOX}/{delivery_id}.json")
        progress("waiting_for_headset", 100, delivery_id=delivery_id)
        for _ in range(15):
            self.sleep(2)
            try:
                raw = self.command("-s", serial, "shell", "cat", f"{INBOX}/{delivery_id}.ack")
                ack = json.loads(raw)
            except (DeliveryError, ValueError):
                continue
            if ack.get("id") != delivery_id:
                continue
            if ack.get("status") == "loaded":
                progress("loaded_on_quest", 100, delivery_id=delivery_id)
                return
            raise DeliveryError("Quest import failed: " + str(ack.get("error", "unknown error"))[:200])
        # Keep waiting receipt distinguishable from success; the UI refreshes receipts.
        return serial, delivery_id

    def receipt(self, serial, delivery_id):
        try:
            value = json.loads(self.command("-s", serial, "shell", "cat", f"{INBOX}/{delivery_id}.ack"))
            return value if value.get("id") == delivery_id else None
        except (DeliveryError, ValueError):
            return None
