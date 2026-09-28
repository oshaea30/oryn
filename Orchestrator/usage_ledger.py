"""Durable quote/reservation ledger. BEGIN IMMEDIATE serializes admission across processes.

No credentials, prompts, part labels or raw provider responses are stored here.
Uncertain reservations carry forward across UTC days until operator reconciliation.
"""
from contextlib import contextmanager
from pathlib import Path
import os
import re
import sqlite3
import time
from cognition import CommandError
from spending import DAILY_LIMIT, utc_day

DEFAULT_PATH = Path(__file__).resolve().parent.parent / '.oryn-usage' / 'usage.sqlite3'
INVESTIGATION_LIMIT = 50_000_000


class UsageLedger:
    def __init__(self, path=DEFAULT_PATH, clock=time.time):
        self.path = Path(path).resolve()
        self.clock = clock
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # SQLite owns all subsequent writes. A private file is created without overwriting anything.
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600); os.close(fd)
        with self.connection() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise CommandError('Unsupported ledger schema; paid calls blocked.')
            # Additive: existing command-service v1 connections remain compatible.
            db.execute('CREATE TABLE IF NOT EXISTS investigation_usage (request_id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL)')
            db.commit()
            if version == 1:
                if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise CommandError('Ledger integrity check failed; paid calls blocked.')
                if db.execute('SELECT * FROM control WHERE id=1').fetchone() is None:
                    raise CommandError('Ledger control record missing; paid calls blocked.')
                db.execute('SELECT request_id,charged_nanos,actual_cost_nanos FROM usage LIMIT 0')
                return
            db.executescript('''
                CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY CHECK(id=1), halted INTEGER NOT NULL, last_clock INTEGER NOT NULL);
                INSERT OR IGNORE INTO control VALUES (1,0,0);
                CREATE TABLE IF NOT EXISTS usage (
                    request_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, provider TEXT NOT NULL,
                    profile TEXT NOT NULL, model TEXT NOT NULL, effort TEXT NOT NULL,
                    operation TEXT NOT NULL, fingerprint TEXT NOT NULL, price_version TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL, max_output_tokens INTEGER NOT NULL,
                    reserved_nanos INTEGER NOT NULL CHECK(reserved_nanos>0), ceiling_nanos INTEGER NOT NULL,
                    created INTEGER NOT NULL, expires INTEGER NOT NULL, admission_day TEXT,
                    status TEXT NOT NULL CHECK(status IN ('quoted','reserved','completed','uncertain')),
                    charged_nanos INTEGER NOT NULL DEFAULT 0, actual_input_tokens INTEGER,
                    actual_output_tokens INTEGER, calculated_cost_nanos INTEGER, actual_cost_nanos INTEGER,
                    tool_cost_nanos INTEGER NOT NULL DEFAULT 0, finished INTEGER, outcome TEXT);
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def connection(self):
        db = None
        try:
            # mode=rw prevents a missing ledger from being silently recreated during a live process.
            db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=5)
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA synchronous=FULL')
            yield db
        except sqlite3.Error:
            raise CommandError('Usage ledger unavailable. Paid requests are blocked; no automatic retry.') from None
        finally:
            if db is not None: db.close()

    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def _clock(self, db):
        now = int(self.clock())
        control = db.execute('SELECT * FROM control WHERE id=1').fetchone()
        if control['halted'] or now < control['last_clock']:
            raise CommandError('Ledger halted or clock moved backward. Paid requests need operator review.')
        db.execute('UPDATE control SET last_clock=? WHERE id=1', (now,))
        return now

    def create_quote(self, quote):
        with self.transaction() as db:
            self._clock(db)
            if db.execute('SELECT 1 FROM usage WHERE request_id=?', (quote['request_id'],)).fetchone():
                raise CommandError('Request ID already exists; quotes cannot be replaced.')
            fields = ['request_id','actor_id','provider','profile','model','effort','operation','fingerprint','price_version',
                      'input_tokens','max_output_tokens','reserved_nanos','ceiling_nanos','created','expires']
            db.execute('INSERT INTO usage (' + ','.join(fields) + ',status) VALUES (' + ','.join('?' for _ in fields) + ", 'quoted')",
                       [quote[k] for k in fields])

    @staticmethod
    def _spent(db, day, actor=None):
        sql = "SELECT COALESCE(SUM(charged_nanos),0) FROM usage WHERE (admission_day=? OR status IN ('reserved','uncertain'))"
        args = [day]
        if actor is not None: sql += ' AND actor_id=?'; args.append(actor)
        return db.execute(sql, args).fetchone()[0]

    def reserve(self, ident, actor, fingerprint, approved_nanos, investigation_id=None):
        with self.transaction() as db:
            now = self._clock(db)
            row = db.execute('SELECT * FROM usage WHERE request_id=? AND actor_id=?', (ident, actor)).fetchone()
            if row is None or row['status'] != 'quoted':
                raise CommandError('Request already claimed or unknown. It will not be sent again.')
            if row['fingerprint'] != fingerprint or type(approved_nanos) is not int or row['reserved_nanos'] != approved_nanos:
                raise CommandError('Approval does not match the exact quoted request and amount.')
            if not row['created'] <= now < row['expires']:
                raise CommandError('Quote expired. Prepare and approve a new quote.')
            day = utc_day(now)
            if investigation_id is not None:
                self._bind_investigation(db, ident, investigation_id)
                spent = self._investigation_spent(db, investigation_id)
                if spent + row['reserved_nanos'] > INVESTIGATION_LIMIT:
                    raise CommandError('Cumulative object investigation budget exhausted. Nothing sent.')
            for scope in (None, actor):
                if self._spent(db, day, scope) + row['reserved_nanos'] > DAILY_LIMIT:
                    raise CommandError('Daily $2 budget exhausted, including outstanding reservations. Nothing sent.')
            db.execute("UPDATE usage SET status='reserved',charged_nanos=reserved_nanos,admission_day=? WHERE request_id=?", (day, ident))

    @staticmethod
    def _bind_investigation(db, ident, investigation_id):
        if not isinstance(investigation_id,str) or not re.fullmatch('[a-f0-9]{64}', investigation_id):
            raise CommandError('Stable object investigation identity required.')
        if db.execute('SELECT 1 FROM usage WHERE request_id=?',(ident,)).fetchone() is None:
            raise CommandError('Cannot bind missing usage; investigation blocked.')
        prior=db.execute('SELECT investigation_id FROM investigation_usage WHERE request_id=?',(ident,)).fetchone()
        if prior and prior[0] != investigation_id:
            raise CommandError('Usage belongs to another investigation.')
        db.execute('INSERT OR IGNORE INTO investigation_usage VALUES (?,?)',(ident,investigation_id))

    def bind_investigation(self, ident, investigation_id):
        """Import prior text usage without resetting charges or creating requests."""
        with self.transaction() as db:
            self._bind_investigation(db,ident,investigation_id)

    @staticmethod
    def _investigation_spent(db, investigation_id):
        return db.execute('SELECT COALESCE(SUM(u.charged_nanos),0) FROM usage u JOIN investigation_usage i ON i.request_id=u.request_id WHERE i.investigation_id=?',(investigation_id,)).fetchone()[0]

    def investigation_summary(self, investigation_id):
        with self.connection() as db:
            spent=self._investigation_spent(db,investigation_id)
            return {'limit_nanos':INVESTIGATION_LIMIT,'charged_and_reserved_nanos':spent,
                    'remaining_nanos':max(0,INVESTIGATION_LIMIT-spent),'scope':'asset_lifetime_development',
                    'actual_cost_nanos':None}

    def uncertain(self, ident, halt=False):
        with self.transaction() as db:
            db.execute("UPDATE usage SET status='uncertain',outcome='usage_unconfirmed',finished=? WHERE request_id=? AND status='reserved'", (int(self.clock()), ident))
            if halt: db.execute('UPDATE control SET halted=1 WHERE id=1')

    def settle(self, ident, incoming, outgoing, calculated, outcome):
        with self.transaction() as db:
            row = db.execute('SELECT * FROM usage WHERE request_id=?', (ident,)).fetchone()
            if row is None or row['status'] != 'reserved' or type(calculated) is not int or not 0 <= calculated <= row['reserved_nanos']:
                raise CommandError('Invalid or duplicate usage settlement; reservation preserved.')
            if type(incoming) is not int or type(outgoing) is not int or not 0 <= incoming <= row['input_tokens'] or not 0 <= outgoing <= row['max_output_tokens']:
                raise CommandError('Invalid usage counts; reservation preserved.')
            if outcome not in ('completed','invalid_response'):
                raise CommandError('Invalid ledger outcome.')
            db.execute("UPDATE usage SET status='completed', charged_nanos=?, actual_input_tokens=?,actual_output_tokens=?,calculated_cost_nanos=?,outcome=?,finished=? WHERE request_id=?",
                       (calculated,incoming,outgoing,calculated,outcome,int(self.clock()),ident))

    def get(self, ident):
        with self.connection() as db:
            row = db.execute('SELECT * FROM usage WHERE request_id=?', (ident,)).fetchone()
            return dict(row) if row else None

    def summary(self):
        with self.connection() as db:
            now = int(self.clock()); control = db.execute('SELECT * FROM control WHERE id=1').fetchone()
            spent = self._spent(db, utc_day(now))
            return {'day':utc_day(now),'timezone':'UTC','daily_limit_nanos':DAILY_LIMIT,
                    'charged_and_reserved_nanos':spent,'remaining_nanos':max(0,DAILY_LIMIT-spent),
                    'halted':bool(control['halted']) or now < control['last_clock'],
                    'recent':[dict(row) for row in db.execute('SELECT request_id,provider,model,effort,operation,status,reserved_nanos,calculated_cost_nanos,actual_cost_nanos,created FROM usage ORDER BY created DESC,rowid DESC LIMIT 20')]}
