"""Persistent application-owned conversation, target resolution and automatic execution.

Only the application calls its interpreter/transport. No development-agent dependency.
"""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import threading
import time
from cognition import CommandError, valid_hex
from command_transport import CommandTransport
from complete_object import binding, decide, validate_state
from experience_interpreter import ExperienceInterpreter
from spending import digest


class Conversation:
    def __init__(self, path, interpreter_factory, transport=None, clock=time.time):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.factory, self.clock = interpreter_factory, clock
        self.transport = transport or CommandTransport(root='/sdcard/Android/data/com.oryn.milestoneone/files/ExperienceBridge', validator=validate_state)
        self.lock = threading.Lock()
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS turns (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, status TEXT NOT NULL, record TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS memory (id INTEGER PRIMARY KEY CHECK(id=1), record TEXT NOT NULL)')
            # A process restart cannot prove whether a call/transfer happened. Never repeat it.
            rows = db.execute("SELECT id,record FROM turns WHERE status='working'").fetchall()
            for ident, raw in rows:
                record = json.loads(raw)
                record['public'].update(status='uncertain', answer='Service restarted during this request. It will not be retried automatically.')
                db.execute('UPDATE turns SET status=?,record=? WHERE id=?', ('uncertain', json.dumps(record), ident))
        self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db: yield db
        finally: db.close()

    def save(self, ident, status, record):
        record['public']['status'] = status
        with self.db() as db:
            db.execute('UPDATE turns SET status=?,record=? WHERE id=?', (status, json.dumps(record), ident))

    def remember(self, state, decision):
        if not decision.get('subject'): return
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO memory VALUES (1,?)', (json.dumps({'binding': binding(state), 'subject': decision['subject']}),))

    def memory(self, state):
        with self.db() as db: row = db.execute('SELECT record FROM memory WHERE id=1').fetchone()
        value = json.loads(row[0]) if row else None
        return value if value and value['binding'] == binding(state) else None

    def _receipt(self, ident, record):
        if record['public']['status'] != 'pending': return record['public']
        receipt = self.transport.receipt(record['serial'], ident)
        status = receipt['status']
        if status == 'waiting':
            if self.clock() > record['expires'] + 10:
                record['public']['answer'] = 'Execution receipt unavailable. Check the headset; this request will not be resent.'
                self.save(ident, 'uncertain', record)
            return record['public']
        record['public']['receipt'] = receipt
        record['public']['timing']['receipt_ms'] = round((self.clock() - record['started']) * 1000)
        if status == 'executed':
            try:
                serial, state = self.transport.snapshot()
                before = record['state']
                expected = record['decision']['component'] if (record['decision']['action'] in ('select', 'isolate_component') or (record['decision']['action'] == 'demonstrate' and record['decision']['component'])) else (
                    '' if record['decision']['action'] in ('explode', 'reassemble', 'restore', 'isolate_subsystem') else before['selected'])
                # A late receipt cannot bind earlier references to a newly selected object/part.
                if serial == record['serial'] and binding(state)[:4] == binding(before)[:4] and state['selected'] == expected:
                    self.remember(state, record['decision'])
            except CommandError: pass
        else:
            record['public']['answer'] = receipt['message']
        self.save(ident, 'completed' if status == 'executed' else status, record)
        return record['public']

    def get(self, ident):
        if not valid_hex(ident, 32): raise CommandError('Invalid request ID.')
        with self.db() as db: row = db.execute('SELECT record FROM turns WHERE id=?', (ident,)).fetchone()
        if not row: raise CommandError('Request not found. It has not been resubmitted.')
        if not self.lock.acquire(blocking=False): return json.loads(row[0])['public']
        try:
            with self.db() as db: row = db.execute('SELECT record FROM turns WHERE id=?', (ident,)).fetchone()
            return self._receipt(ident, json.loads(row[0]))
        finally: self.lock.release()

    def ask(self, data):
        if not isinstance(data, dict) or set(data) != {'id', 'question'}:
            raise CommandError('A request ID and question are required.')
        ident, question = data['id'], data['question']
        if not valid_hex(ident, 32) or not isinstance(question, str) or not 1 <= len(question.strip()) <= 500:
            raise CommandError('Enter a question of 1–500 characters.')
        fingerprint = digest(question)
        if not self.lock.acquire(blocking=False): raise CommandError('ORYN is still handling the previous request.')
        try:
            with self.db() as db:
                old = db.execute('SELECT fingerprint,record FROM turns WHERE id=?', (ident,)).fetchone()
                pending = db.execute("SELECT id,record FROM turns WHERE status='pending'").fetchall()
            if old:
                if old[0] != fingerprint: raise CommandError('This request ID belongs to different text.')
                return self._receipt(ident, json.loads(old[1]))
            for pending_id, raw in pending:
                if self._receipt(pending_id, json.loads(raw))['status'] == 'pending':
                    raise CommandError('Waiting for the previous Quest action. No new interpretation was sent.')
            started = self.clock()
            serial, state = self.transport.snapshot()
            memory = self.memory(state)
            # Persist before provider I/O, including token counting.
            record = {'serial': serial, 'state': state, 'started': started,
                      'public': {'id': ident, 'status': 'working', 'answer': 'ORYN is interpreting your request.', 'action': None, 'timing': {}}}
            with self.db() as db:
                db.execute('INSERT INTO turns VALUES (?,?,?,?)', (ident, fingerprint, 'working', json.dumps(record)))
            try:
                intent = self.factory().interpret(ident, question, state, memory)
                decision = decide(state, intent, memory)
                record['public']['timing']['interpretation_ms'] = round((self.clock() - started) * 1000)
                current_serial, current = self.transport.snapshot()
                if current_serial != serial or current['session'] != state['session'] or current['contextToken'] != state['contextToken']:
                    raise CommandError('The object or selection changed while I was interpreting. Ask again about the current selection.')
                record['decision'] = decision
                record['public'].update({k: v for k, v in decision.items() if k != 'subject'})
                if decision['action']:
                    if not current['ready']: raise CommandError('Release the object and open ORYN before requesting movement. Nothing was queued.')
                    record['expires'] = int(self.clock()) + 30
                    command = {'schema': 1, 'id': ident, 'session': current['session'], 'contextToken': current['contextToken'],
                               'expires': record['expires'], 'action': decision['action'], 'component': decision['component'], 'subsystem': decision['subsystem']}
                    # Pending is durable before transfer; even transfer uncertainty is never resent.
                    self.save(ident, 'pending', record)
                    try: self.transport.send(serial, command)
                    except Exception:
                        record['public']['answer'] = 'Transfer is unconfirmed. Checking for a Quest receipt; this request will not be resent.'
                    record['public']['timing']['dispatch_ms'] = round((self.clock() - started) * 1000)
                    self.save(ident, 'pending', record)
                else:
                    self.remember(state, decision)
                    self.save(ident, 'completed', record)
            except Exception as error:
                record['public'].update(answer=str(error) if isinstance(error, CommandError) else 'Request unavailable. No automatic retry.', action=None)
                self.save(ident, 'failed', record)
            return record['public']
        finally: self.lock.release()


def for_jobs(jobs):
    def interpreter():
        service = jobs.research
        if service is None or not service.key or service.budget_error:
            raise CommandError('Connect OpenAI through the existing object settings. No interpretation was sent.')
        return ExperienceInterpreter(service.ledger, service.key)
    return Conversation(jobs.root / 'conversation.sqlite3', interpreter)
