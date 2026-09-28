"""Local-only ORYN command console. Run: python3 Orchestrator/command_app.py"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import time
import uuid
from cognition import CommandError, decide, offline_intent, valid_hex, action_context, snapshot_summary
from cognitive_providers import validate_config
from command_transport import CommandTransport
from paid_gateway import PaidGateway
from spending import policy


class Commands:
    def __init__(self, transport=None, gateway=None):
        self.transport = transport or CommandTransport()
        self.config = {}
        self.requests = {}
        self.lock = threading.Lock()
        self.gateway = gateway if gateway is not None else PaidGateway()
        self.config_revisions = {}

    def configure(self, data):
        with self.lock:
            provider = data.get('provider')
            if data.get('clear') is True and provider in ('openai', 'gemini'):
                self.config.pop(provider, None)
                self.config_revisions.pop(provider, None)
                return {'message': 'Provider credentials removed from service memory.'}
            profile = data.get('profile', 'routine')
            chosen = policy(provider, profile, self.gateway.clock())
            key = data.get('key') or self.config.get(provider, ('', ''))[1]
            validate_config(provider, chosen['model'], key)
            self.config[provider] = (profile, key)
            self.config_revisions[provider] = uuid.uuid4().hex
            return {'message': 'Configured in process memory only. No API request was made.'}

    def prepare_quote(self, data):
        question, provider = data.get('question'), data.get('provider')
        if not isinstance(question, str) or not 1 <= len(question) <= 500 or not question.strip():
            raise CommandError('Enter a question of 1–500 characters.')
        if data.get('approveCount') is not True:
            raise CommandError('Approve sending the request for provider token counting first.')
        with self.lock:
            if provider not in self.config:
                raise CommandError('Configure an approved provider/profile first.')
            profile, key = self.config[provider]
            if data.get('profile') != profile:
                raise CommandError('Profile changed. Save the selected profile configuration first.')
            serial, state = self.transport.snapshot()
            if not state['context']['parts']:
                raise CommandError('Load/select an assembly before capturing an interpretation snapshot.')
            quote = self.gateway.prepare(provider,profile,key,question,state,serial,self.config_revisions[provider])
            return dict(quote, snapshot=snapshot_summary(state), contextFingerprint=action_context(state,serial))

    def status(self):
        with self.lock:
            configured = {p: value[0] for p, value in self.config.items()}
        try:
            serial, state = self.transport.snapshot()
            return {'state': state, 'configured': configured, 'contextFingerprint': action_context(state,serial)}
        except CommandError as error:
            return {'state': None, 'stateError': str(error), 'configured': configured}

    def ask(self, data):
        ident, question, provider = data.get('id'), data.get('question'), data.get('provider')
        if not valid_hex(ident, 32) or not isinstance(question, str) or not 1 <= len(question) <= 500 or not question.strip():
            raise CommandError('Enter a question of 1–500 characters.')
        if provider not in ('offline', 'openai', 'gemini'):
            raise CommandError('Unknown provider.')
        # Never queue a second paid request while the first is running.
        if not self.lock.acquire(blocking=False):
            raise CommandError('Another request is running. Wait; no new call was made.')
        try:
            if ident in self.requests:
                return self.requests[ident]['public']
            if len(self.requests) >= 500:
                raise CommandError('Session request limit reached. Restart the command service.')
            if provider != 'offline' and (data.get('approvePaid') is not True or provider not in self.config):
                raise CommandError('Configure this provider and approve this single paid request first.')
            if provider == 'offline':
                serial, state = self.transport.snapshot()
            else:
                serial, state = self.gateway.interpretation_snapshot(ident)
            record = {'serial': serial, 'state': state, 'created': time.time(), 'sent': False,
                      'public': {'id': ident, 'provider': provider, 'answer': 'Request started; result unavailable.', 'action': None}}
            # Reserve ID before external I/O. Same ID, including after timeout, is not billed again.
            self.requests[ident] = record
            try:
                model = 'exact-phrase test (not AI)'
                if provider == 'offline':
                    intent = offline_intent(question)
                else:
                    profile, key = self.config[provider]
                    if data.get('profile') != profile:
                        raise CommandError('Profile changed; prepare another quote.')
                    intent, model = self.gateway.run(data,provider,profile,key,question,state,serial,self.config_revisions[provider])
                decision = decide(state, intent)
                record['decision'] = decision
                record['public'] = dict(decision, id=ident, provider=provider, model=model,
                                        contextFingerprint=action_context(state,serial), snapshot=snapshot_summary(state))
            except Exception as error:
                message = str(error) if isinstance(error, CommandError) else 'Request failed. No automatic retry or action was performed.'
                record['public'] = {'id': ident, 'provider': provider, 'answer': message, 'action': None}
            return record['public']
        finally:
            self.lock.release()

    def apply(self, data):
        ident = data.get('id')
        if not valid_hex(ident, 32):
            raise CommandError('Invalid request ID.')
        with self.lock:
            record = self.requests.get(ident)
            if record is None or not record.get('decision', {}).get('action'):
                raise CommandError('No validated action proposal exists for this request.')
            if record['sent']:
                return dict(self.transport.receipt(record['serial'], ident), id=ident)
            serial, current = self.transport.snapshot()
            original = record['state']
            if action_context(current,serial) != action_context(original,record['serial']):
                raise CommandError('Object, selection, saved records or assembly state changed. Ask again before applying.')
            if time.time() - record['created'] > 120:
                raise CommandError('Action proposal expired. Ask again.')
            if not current['context']['ready']:
                raise CommandError('Headset busy or unfocused. Release objects/open ORYN, then confirm this proposal again before it expires. No new paid interpretation is needed.')
            decision = record['decision']
            command = {'schema': 1, 'id': ident, 'session': current['session'], 'contextToken': current['contextToken'],
                       'expires': int(time.time()) + 30, 'action': decision['action'], 'partId': decision['partId']}
            # Mark before transfer: uncertain transport must not trigger a second execution attempt.
            record['sent'] = True
            try:
                self.transport.send(serial, command)
            except Exception:
                return {'id': ident, 'status': 'uncertain', 'message': 'Transfer could not be confirmed. Check receipt/headset; this request will not be resent.'}
            return {'id': ident, 'status': 'waiting', 'message': 'Command transferred. Waiting for the Quest execution receipt.'}

    def receipt(self, ident):
        if not valid_hex(ident, 32):
            raise CommandError('Invalid request ID.')
        with self.lock:
            record = self.requests.get(ident)
            if not record or not record['sent']:
                raise CommandError('No command has been sent for this request.')
            return dict(self.transport.receipt(record['serial'], ident), id=ident)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, port=8767, commands=None):
        self.commands = commands or Commands()
        self.token = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, value, status=200, mime='application/json'):
        encoded = json.dumps(value).encode() if mime == 'application/json' else value
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(encoded)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(encoded)

    def allowed(self, write=False):
        host = '127.0.0.1:' + str(self.server.server_port)
        if self.headers.get('Host') != host:
            return False
        if write and (self.headers.get('Origin') != 'http://' + host or
                      not secrets.compare_digest(self.headers.get('X-Oryn-Token', ''), self.server.token)):
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return self.respond({'error': 'Forbidden'}, 403)
        try:
            assets = {'/': ('command.html', 'text/html; charset=utf-8'),
                      '/command.js': ('command.js', 'text/javascript'), '/command.css': ('command.css', 'text/css')}
            if self.path in assets:
                name, mime = assets[self.path]
                return self.respond(Path(__file__).with_name(name).read_bytes(), mime=mime)
            if self.path == '/api/session':
                return self.respond({'token': self.server.token, 'commandContract': 2})
            if self.path == '/api/state':
                return self.respond(self.server.commands.status())
            if self.path == '/api/budget':
                return self.respond(self.server.commands.gateway.ledger.summary())
            if self.path.startswith('/api/receipt/'):
                return self.respond(self.server.commands.receipt(self.path[len('/api/receipt/'):]))
            return self.respond({'error': 'Not found'}, 404)
        except CommandError as error:
            return self.respond({'error': str(error)}, 409)
        except Exception:
            return self.respond({'error': 'Local command service unavailable.'}, 500)

    def do_POST(self):
        if not self.allowed(write=True):
            return self.respond({'error': 'Forbidden'}, 403)
        self.connection.settimeout(5)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192 or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type') != 'application/json':
                return self.respond({'error': 'Invalid request'}, 400)
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError()
            handlers = {'/api/configure': self.server.commands.configure, '/api/ask': self.server.commands.ask,
                        '/api/apply': self.server.commands.apply, '/api/quote': self.server.commands.prepare_quote}
            if self.path not in handlers:
                return self.respond({'error': 'Not found'}, 404)
            return self.respond(handlers[self.path](data))
        except CommandError as error:
            return self.respond({'error': str(error)}, 409)
        except (ValueError, TypeError):
            return self.respond({'error': 'Invalid request'}, 400)
        except Exception:
            return self.respond({'error': 'Request unavailable; no automatic retry.'}, 500)


if __name__ == '__main__':
    server = Server()
    print('ORYN command console: http://127.0.0.1:8767/ (offline by default)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
