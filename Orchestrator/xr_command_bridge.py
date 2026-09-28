"""Development test adapter for the existing USB protocol; never imports providers."""
import json
import hashlib
import re
import subprocess
import sys
import time
from cognition import CommandError, valid_hex, validate_snapshot
from command_transport import CommandTransport
from transport import AdbTransport
import test_guide_transport


def bounded_run(*args, **kwargs):
    kwargs['timeout'] = 5
    return subprocess.run(*args, **kwargs)


def check_forward(transport, serial):
    rows = [line.split() for line in transport.command('forward', '--list').splitlines()]
    matches = [row for row in rows if len(row) == 3 and row[1] == 'tcp:8720']
    if matches != [[serial, 'tcp:8720', 'tcp:8720']]:
        raise CommandError('Operator USB forwarding must target the same Quest as the command bridge.')


def handle(request, transport):
    if not isinstance(request, dict):
        raise CommandError('Invalid inspection request.')
    operation = request.get('operation')
    if operation == 'snapshot':
        serial, state = transport.snapshot()
        check_forward(transport, serial)
        return {'serial': serial, 'state': state}
    serial, ident = request.get('serial'), request.get('id')
    if not isinstance(serial, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', serial) or (operation != 'resolve' and not valid_hex(ident, 32)):
        raise CommandError('Invalid device or command ID.')
    if operation == 'receipt':
        return transport.receipt(serial, ident)
    if operation == 'guide':
        return test_guide_transport.publish(request, transport)
    if operation == 'guide_receipt':
        return test_guide_transport.receipt(request, transport)
    if operation not in ('apply', 'resolve') or (operation == 'apply' and request.get('action') not in ('explode', 'reassemble', 'select', 'isolate')):
        raise CommandError('Unsupported inspection operation.')
    expected = request.get('expected')
    validate_snapshot(expected)
    current_serial, current = transport.snapshot()
    check_forward(transport, current_serial)
    if (serial != current_serial or current['session'] != expected['session'] or
            current['contextToken'] != expected['contextToken'] or current['context'] != expected['context']):
        raise CommandError('Workspace changed before dispatch; no command sent.')
    if not current['context']['ready']:
        raise CommandError('Headset not ready; no command sent.')
    if operation == 'resolve':
        number = request.get('number')
        parts = [p for p in current['context']['parts'] if p['number'] == number]
        if type(number) is not int or not 1 <= number <= 39 or len(parts) != 1 or parts[0]['error']:
            raise CommandError('Fixture part is missing, ambiguous or unavailable.')
        part, asset = parts[0], current['context']['assetSha256']
        record_path = '/sdcard/Android/data/com.oryn.milestoneone/files/Knowledge/Records/' + asset + '/' + part['partId'] + '.json'
        raw = transport.command('-s', serial, 'shell', 'head', '-c', '1048577', record_path)
        try:
            if len(raw.encode()) > 1048576:
                raise ValueError()
            record = json.loads(raw)
            geometry = record['geometryPath']
            name = record['geometryName']
            expected_id = hashlib.sha256((asset + '/renderer-path-v1/' + geometry).encode()).hexdigest()
            if (record['schema'] != 1 or record['assetSha256'] != asset or record['partId'] != part['partId'] or
                    expected_id != part['partId'] or not re.fullmatch(r'renderer-path-v1(?:/[0-9]+)+', geometry) or
                    not re.fullmatch(r'island_[0-9]{3}', name)):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise CommandError('Part record cannot establish a verified geometry binding.') from None
        # No annotations are returned or used as component identity.
        return {'partId': part['partId'], 'number': number, 'geometryName': name}
    target = request.get('partId', '')
    if request['action'] in ('select', 'isolate'):
        if not valid_hex(target, 64) or not any(p['partId'] == target and not p['error'] for p in current['context']['parts']):
            raise CommandError('Explicit available part ID required; no command sent.')
    elif target != '':
        raise CommandError('Whole-assembly command must not target a part.')
    command = {'schema': 1, 'id': ident, 'session': current['session'],
               'contextToken': current['contextToken'], 'expires': int(time.time()) + 30,
               'action': request['action'], 'partId': target}
    # Exactly one transfer attempt. Unity also validates focus, held state, context,
    # expiry and durable receipt IDs immediately before executing the action.
    try:
        transport.send(serial, command)
    except Exception:
        return {'status': 'uncertain'}
    return {'status': 'waiting'}


def main():
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise CommandError('Inspection request too large.')
        result = handle(json.loads(raw), CommandTransport(AdbTransport(run=bounded_run)))
    except CommandError as error:
        result = {'error': str(error)}
    except Exception:
        result = {'error': 'USB inspection adapter unavailable; no automatic retry.'}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
