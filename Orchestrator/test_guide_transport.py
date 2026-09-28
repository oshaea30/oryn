"""Development-only status transport. Display messages cannot execute actions."""
import json
from pathlib import Path
import tempfile
from cognition import CommandError, valid_hex

ROOT = '/sdcard/Android/data/com.oryn.milestoneone/files/CommandBridge'
PHASES = {'ready', 'testing', 'passed', 'failed', 'blocked'}


def publish(request, transport):
    sequence, phase, message = request.get('sequence'), request.get('phase'), request.get('message')
    if (not valid_hex(request.get('session'), 32) or type(sequence) is not int or not 0 < sequence < 100000 or
            phase not in PHASES or not isinstance(message, str) or not 1 <= len(message.strip()) <= 240 or
            any((ord(c) < 32 and c != '\n') or c in '<>' for c in message)):
        raise CommandError('Invalid test display notice.')
    serial, state = transport.snapshot()
    if serial != request['serial'] or state['session'] != request['session'] or state.get('testGuideAvailable') is not True:
        raise CommandError('Test guide unavailable or app session changed. No display or action sent.')
    notice = {'schema': 1, 'id': request['id'], 'session': state['session'], 'sequence': sequence,
              'phase': phase, 'message': message, 'expires': state['utc'] + 15}
    with tempfile.TemporaryDirectory(prefix='oryn-test-guide-') as folder:
        file = Path(folder) / 'notice.json'; file.write_text(json.dumps(notice))
        transport.command('-s', serial, 'push', str(file), ROOT + '/test-status.partial')
        transport.command('-s', serial, 'shell', 'mv', ROOT + '/test-status.partial', ROOT + '/test-status.json')
    return {'status': 'waiting', 'sequence': sequence}


def receipt(request, transport):
    if not valid_hex(request.get('session'), 32):
        raise CommandError('Invalid display session.')
    try:
        raw = transport.command('-s', request['serial'], 'shell', 'head', '-c', '4097', ROOT + '/test-status.ack')
        value = json.loads(raw) if len(raw.encode()) <= 4096 else {}
        if value.get('id') == request['id'] and value.get('session') == request['session']:
            return value
    except (CommandError, ValueError, TypeError):
        pass
    return {'status': 'waiting'}
