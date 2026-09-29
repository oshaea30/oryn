"""Bounded USB command transport; transfer success is never execution success."""
import json
from pathlib import Path
import re
import tempfile
import time
from transport import AdbTransport, DeliveryError
from cognition import CommandError, valid_hex, validate_snapshot

ROOT = '/sdcard/Android/data/com.oryn.milestoneone/files/CommandBridge'


class CommandTransport:
    def __init__(self, adb=None, *, root=ROOT, validator=validate_snapshot):
        self.adb = adb or AdbTransport()
        self.root, self.validator = root, validator

    def command(self, *args):
        try:
            return self.adb.command(*args)
        except DeliveryError:
            raise CommandError('Quest USB connection unavailable. Connect and authorize one Quest with ORYN open.') from None

    def snapshot(self):
        rows = [line.split() for line in self.command('devices').splitlines()[1:] if line.strip()]
        devices = [r[0] for r in rows if len(r) >= 2 and r[1] == 'device']
        if len(devices) != 1 or not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', devices[0]):
            raise CommandError('Connect exactly one authorized Quest.')
        serial = devices[0]
        raw = self.command('-s', serial, 'shell', 'head', '-c', '65537', self.root + '/state.json')
        try:
            if len(raw.encode()) > 65536:
                raise ValueError()
            state = self.validator(json.loads(raw))
        except (ValueError, TypeError):
            raise CommandError('Command bridge unavailable. Install the command-enabled build and open ORYN.') from None
        return serial, state

    def send(self, serial, command):
        ident = command['id']
        if not valid_hex(ident, 32):
            raise CommandError('Invalid command ID.')
        with tempfile.TemporaryDirectory(prefix='oryn-command-') as folder:
            path = Path(folder) / 'command.json'
            path.write_text(json.dumps(command), encoding='utf-8')
            self.command('-s', serial, 'push', str(path), self.root + '/' + ident + '.partial')
            self.command('-s', serial, 'shell', 'mv', self.root + '/' + ident + '.partial', self.root + '/' + ident + '.command')

    def receipt(self, serial, ident):
        if not valid_hex(ident, 32):
            raise CommandError('Invalid receipt ID.')
        try:
            raw = self.command('-s', serial, 'shell', 'head', '-c', '4097', self.root + '/' + ident + '.ack')
            value = json.loads(raw) if len(raw.encode()) <= 4096 else {}
            if value.get('id') == ident and value.get('status') in ('executed', 'rejected', 'uncertain'):
                return {'status': value['status'], 'message': str(value.get('message', ''))[:200]}
        except (CommandError, ValueError, TypeError, AttributeError):
            pass
        return {'status': 'waiting', 'message': 'Waiting for Quest receipt. Do not resend. Open ORYN to apply or reject the expiring command.'}
