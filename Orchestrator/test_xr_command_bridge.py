import copy
import hashlib
import json
import time
import unittest
from cognition import CommandError
from xr_command_bridge import handle


class Transport:
    def __init__(self):
        self.state = {'schema': 1, 'session': 'a'*32, 'contextToken': 'b'*32, 'utc': int(time.time()),
                      'context': {'ready': True, 'owner': 1, 'partsMode': False, 'isolated': False,
                                  'assetSha256': 'c'*64, 'selectedPartId': '', 'parts': [
                                      {'partId': 'd'*64, 'number': 1, 'revision': 0, 'label': '', 'status': 'unidentified', 'error': ''}]}}
        self.sent = []
        self.forward = 'quest tcp:8720 tcp:8720\n'
        self.fail = False
        self.geometry = 'renderer-path-v1/0/0'
        self.state['context']['parts'][0]['partId'] = hashlib.sha256(('c'*64+'/renderer-path-v1/'+self.geometry).encode()).hexdigest()
        self.record = {'schema': 1, 'assetSha256': 'c'*64, 'partId': self.state['context']['parts'][0]['partId'],
                       'geometryPath': self.geometry, 'geometryName': 'island_001', 'history': [{'label': 'private annotation'}]}
    def snapshot(self):
        return 'quest', copy.deepcopy(self.state)
    def command(self, *args):
        if args == ('forward', '--list'):
            return self.forward
        assert args[:6] == ('-s', 'quest', 'shell', 'head', '-c', '1048577')
        return json.dumps(self.record)
    def send(self, serial, command):
        self.sent.append((serial, command))
        if self.fail:
            raise RuntimeError('unknown transfer')
    def receipt(self, serial, ident):
        return {'status': 'executed'}


class BridgeTests(unittest.TestCase):
    def test_guide_is_separate_from_actions_and_bound_to_session(self):
        t = Transport(); t.state['testGuideAvailable'] = True
        commands = []
        t.command = lambda *args: commands.append(args) or ''
        request = {'operation':'guide','id':'f'*32,'serial':'quest','session':'a'*32,
                   'sequence':1,'phase':'ready','message':'Grab the drone, then release.'}
        self.assertEqual(handle(request,t)['status'],'waiting')
        self.assertEqual(t.sent,[])
        self.assertEqual(commands[-1][-1],'/sdcard/Android/data/com.oryn.milestoneone/files/CommandBridge/test-status.json')
        for changed in ({'session':'e'*32},{'phase':'explode'},{'sequence':0},{'message':'<b>bad</b>'}):
            with self.assertRaises(CommandError):handle(dict(request,**changed),t)

    def request(self, transport, action='explode'):
        return {'operation': 'apply', 'serial': 'quest', 'id': 'f'*32,
                'action': action, 'expected': copy.deepcopy(transport.state)}

    def test_snapshot_and_matching_forward(self):
        t = Transport()
        self.assertEqual(handle({'operation': 'snapshot'}, t)['serial'], 'quest')
        for forward in ['', 'other tcp:8720 tcp:8720', 'quest tcp:8720 tcp:9999']:
            t.forward = forward
            with self.assertRaises(CommandError):
                handle({'operation': 'snapshot'}, t)

    def test_allowed_actions_use_existing_context_expiry_and_no_part_target(self):
        for action in ('explode', 'reassemble'):
            t = Transport()
            self.assertEqual(handle(self.request(t, action), t)['status'], 'waiting')
            self.assertEqual(len(t.sent), 1)
            command = t.sent[0][1]
            self.assertEqual(command['action'], action)
            self.assertEqual(command['partId'], '')
            self.assertEqual(command['contextToken'], t.state['contextToken'])
            self.assertLessEqual(command['expires']-time.time(), 30)

    def test_bad_actions_or_stale_context_never_transfer(self):
        for change in [lambda r: r.update(action='generate'), lambda r: r.update(action='isolate'),
                       lambda r: r.update(serial='other'), lambda r: r.update(id='bad'),
                       lambda r: r['expected'].update(session='e'*32),
                       lambda r: r['expected'].update(contextToken='e'*32),
                       lambda r: r['expected'].update(utc=0),
                       lambda r: r['expected']['context'].update(owner=2)]:
            t = Transport()
            request = self.request(t)
            change(request)
            with self.assertRaises(CommandError):
                handle(request, t)
            self.assertEqual(t.sent, [])

    def test_readiness_and_changed_forward_block_dispatch(self):
        for change in [lambda t: t.state['context'].update(ready=False), lambda t: setattr(t, 'forward', '')]:
            t = Transport()
            change(t)
            with self.assertRaises(CommandError):
                handle(self.request(t), t)
            self.assertEqual(t.sent, [])

    def test_uncertain_transfer_is_not_retried(self):
        t = Transport()
        t.fail = True
        self.assertEqual(handle(self.request(t), t), {'status': 'uncertain'})
        self.assertEqual(len(t.sent), 1)

    def test_receipt_does_not_write(self):
        t = Transport()
        self.assertEqual(handle({'operation': 'receipt', 'serial': 'quest', 'id': 'f'*32}, t)['status'], 'executed')
        self.assertEqual(t.sent, [])

    def test_part_actions_require_explicit_available_target(self):
        for action in ('select', 'isolate'):
            t = Transport()
            request = self.request(t, action)
            with self.assertRaises(CommandError):
                handle(request, t)
            request['partId'] = t.state['context']['parts'][0]['partId']
            self.assertEqual(handle(request, t)['status'], 'waiting')
            self.assertEqual(t.sent[0][1]['partId'], request['partId'])

    def test_unknown_unavailable_or_extraneous_target_rejected(self):
        for action, target in [('select', 'a'*64), ('isolate', 'bad'), ('reassemble', 'd'*64), ('explode', 'd'*64)]:
            t = Transport()
            request = dict(self.request(t, action), partId=target)
            with self.assertRaises(CommandError):
                handle(request, t)
            self.assertEqual(t.sent, [])
        t = Transport()
        t.state['context']['parts'][0].update(error='unavailable', status='unavailable')
        with self.assertRaises(CommandError):
            handle(dict(self.request(t, 'isolate'), partId=t.state['context']['parts'][0]['partId']), t)

    def test_resolve_checks_record_binding_without_returning_labels(self):
        t = Transport()
        request = dict(self.request(t), operation='resolve', number=1)
        result = handle(request, t)
        self.assertEqual(result, {'number': 1, 'partId': t.record['partId'], 'geometryName': 'island_001'})
        self.assertEqual(t.sent, [])

    def test_resolve_rejects_forged_or_oversized_records(self):
        for change in [lambda r: r.update(assetSha256='d'*64), lambda r: r.update(partId='d'*64),
                       lambda r: r.update(geometryPath='renderer-path-v1/2/0'), lambda r: r.update(geometryName='../other'),
                       lambda r: r.update(schema=2), lambda r: r.update(history=['x'*1048577])]:
            t = Transport()
            change(t.record)
            with self.assertRaises(CommandError):
                handle(dict(self.request(t), operation='resolve', number=1), t)
            self.assertEqual(t.sent, [])

    def test_resolve_rejects_invalid_or_ambiguous_part_number(self):
        for number in [True, '1', 0, 40, 2]:
            t = Transport()
            with self.assertRaises(CommandError):
                handle(dict(self.request(t), operation='resolve', number=number), t)


if __name__ == '__main__':
    unittest.main()
