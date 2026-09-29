"""Complete Object v1: bounded runtime records and deterministic grounded decisions."""
import math
import re
import time
from cognition import CommandError, valid_hex

ACTIONS = ('show_drone', 'select', 'isolate_component', 'isolate_subsystem', 'demonstrate',
           'play', 'pause', 'slow', 'normal', 'explode', 'reassemble', 'restore')
INTENTS = ACTIONS + ('describe', 'why', 'unknown')
TARGETS = ('none', 'selected', 'previous', 'component', 'subsystem')


def bounded(value, limit=500):
    return isinstance(value, str) and len(value) <= limit and not any(ord(c) < 32 or c in '<>' for c in value)


def identifier(value):
    return isinstance(value, str) and re.fullmatch(r'[a-z0-9_-]{1,80}', value) is not None


def validate_state(state, now=None):
    now = time.time() if now is None else now
    try:
        assert type(state['schema']) is int and state['schema'] == 1
        assert valid_hex(state['session'], 32) and valid_hex(state['contextToken'], 32) and valid_hex(state['referenceToken'], 32)
        assert type(state['utc']) is int and -3 <= now - state['utc'] <= 10
        assert all(type(state[k]) is bool for k in ('ready', 'running', 'isolated', 'partsMode'))
        assert all(type(state[k]) in (int, float) and math.isfinite(state[k]) for k in ('speed', 'spread'))
        assert 0.05 <= state['speed'] <= 2 and 0 <= state['spread'] <= 2
        assert isinstance(state['selected'], str)
        obj = state.get('subject')
        # JsonUtility emits null serializable objects as empty objects on some Unity versions.
        if not obj or not obj.get('id'):
            assert not state['selected']
            state['subject'] = None
            return state
        assert identifier(obj['id']) and bounded(obj['revision'], 80) and obj['revision']
        assert isinstance(obj['instance'], str) and obj['instance'].isdigit() and int(obj['instance']) > 0
        assert bounded(obj['title'], 120) and bounded(obj['explanation'], 1000)
        assert obj['scope'] == 'authored_family_demonstration'
        assert isinstance(obj['actions'], list) and len(obj['actions']) <= len(ACTIONS)
        assert len(set(obj['actions'])) == len(obj['actions']) and set(obj['actions']) <= set(ACTIONS) - {'show_drone'}
        assert isinstance(obj['components'], list) and 1 <= len(obj['components']) <= 64
        ids, geometry = set(), set()
        for c in obj['components']:
            assert identifier(c['id']) and c['id'] not in ids
            assert identifier(c['geometryId']) and c['geometryId'] not in geometry
            assert identifier(c['subsystem']) and bounded(c['name'], 80) and bounded(c['explanation'], 1000)
            assert c['parentId'] == '' or c['parentId'] in ids
            assert c['driverId'] == '' or c['driverId'] in ids
            assert bounded(c['provenance'], 120) and c['provenance']
            assert c['evidence'] in ('unsupported', 'reference-supported', 'verified')
            assert isinstance(c['referenceIds'], list) and len(c['referenceIds']) <= 16
            assert all(bounded(x, 120) and x for x in c['referenceIds'])
            assert c['evidence'] == 'unsupported' or c['referenceIds']
            ids.add(c['id']); geometry.add(c['geometryId'])
        assert not state['selected'] or state['selected'] in ids
    except (AssertionError, KeyError, TypeError, ValueError, AttributeError):
        raise CommandError('Object context is missing, stale or invalid. Open the updated ORYN build.') from None
    return state


def binding(state):
    obj = state.get('subject') or {}
    return [state['session'], obj.get('id'), obj.get('revision'), obj.get('instance'), state['selected'], state['referenceToken']]


def validate_intent(value):
    if not isinstance(value, dict) or set(value) != {'intent', 'target', 'id'}:
        raise CommandError('Invalid interpretation; no action taken.')
    kind, target, ident = value['intent'], value['target'], value['id']
    if kind not in INTENTS or target not in TARGETS or not isinstance(ident, str):
        raise CommandError('Unsupported interpretation; no action taken.')
    if (target in ('component', 'subsystem')) != bool(ident) or (ident and not identifier(ident)):
        raise CommandError('Invalid interpretation target.')
    if kind in ('show_drone', 'play', 'pause', 'slow', 'normal', 'explode', 'reassemble', 'restore', 'unknown') and target != 'none':
        raise CommandError('Unexpected action target.')
    if kind in ('select', 'isolate_component') and target not in ('selected', 'previous', 'component'):
        raise CommandError('Component target required.')
    if kind == 'isolate_subsystem' and target not in ('subsystem', 'previous'):
        raise CommandError('Subsystem target required.')
    return value


def decide(state, intent, memory=None):
    value = validate_intent(intent)
    kind, target, ident = value['intent'], value['target'], value['id']
    result = {'answer': '', 'action': None, 'component': '', 'subsystem': '', 'references': [], 'evidence': [], 'subject': None}
    if kind == 'unknown':
        result['answer'] = 'I cannot ground that request in this object yet. Try selecting a component and asking what it does.'
        return result
    if kind == 'show_drone':
        return dict(result, action=kind, answer='Opening the authored drone teaching model.')
    obj = state.get('subject')
    if not obj:
        return dict(result, answer='Ask me to show the drone first. This object has no complete-object contract yet.')
    components = {c['id']: c for c in obj['components']}
    if target == 'selected':
        target, ident = 'component', state['selected']
    elif target == 'previous':
        if not memory or memory.get('binding') != binding(state) or not memory.get('subject'):
            return dict(result, answer='The earlier reference is no longer clear. Select the component or name the subsystem.')
        target, ident = memory['subject']['target'], memory['subject']['id']
    if target == 'component' and ident not in components:
        return dict(result, answer='Select a component first, or name one of this model’s components.')
    if target == 'subsystem' and not any(c['subsystem'] == ident for c in components.values()):
        return dict(result, answer='That subsystem is not declared for this object.')
    if kind == 'isolate_subsystem' and target != 'subsystem':
        return dict(result, answer='Name the subsystem to isolate.')
    if kind in ('select', 'isolate_component') and target != 'component':
        return dict(result, answer='Select or name a component first.')
    result['subject'] = None if kind in ('play', 'pause', 'slow', 'normal') else {'target': target, 'id': ident}
    relevant = [components[ident]] if target == 'component' else [c for c in components.values() if target == 'none' or c['subsystem'] == ident]
    result['evidence'] = [{'component': c['id'], 'status': c['evidence'], 'provenance': c['provenance']} for c in relevant]
    result['references'] = sorted({r for c in relevant for r in c['referenceIds']})
    if kind in ('describe', 'why'):
        if target == 'component':
            result['answer'] = components[ident]['explanation']
        elif target == 'subsystem':
            # Show actual declared relationships rather than invent a function from subsystem names.
            ids = {c['id'] for c in relevant}
            relations = [(components[c['driverId']]['name'], c['name']) for c in relevant if c['driverId'] in ids]
            if relations:
                result['answer'] = 'In this authored model, ' + '; '.join(a + ' drives ' + b for a, b in relations) + '. These components belong to the ' + ident.replace('_', ' ') + ' subsystem.'
            else:
                result['answer'] = 'This model groups ' + ', '.join(c['name'] for c in relevant) + ' in ' + ident.replace('_', ' ') + '. No drive relationship is recorded within that group.'
        else:
            result['answer'] = obj['explanation']
        return result
    if kind not in obj['actions']:
        return dict(result, answer='This object does not support that action.')
    # Demonstration of a subsystem is intentionally unavailable until it can be one validated operation.
    if kind == 'demonstrate' and target == 'subsystem':
        return dict(result, answer='Isolate that subsystem, then ask me to play its motion.')
    result['action'] = kind
    if kind in ('select', 'isolate_component', 'demonstrate') and target == 'component': result['component'] = ident
    if kind == 'isolate_subsystem': result['subsystem'] = ident
    result['answer'] = {
        'select': 'Selecting the component.', 'isolate_component': 'Showing that component.',
        'isolate_subsystem': 'Showing the declared subsystem.', 'demonstrate': 'Showing the authored motion; this is not a physical simulation.',
        'play': 'Playing the authored motion.', 'pause': 'Pausing motion.', 'slow': 'Setting motion to 0.15×.',
        'normal': 'Setting motion to 1×.', 'explode': 'Separating the components for inspection.',
        'reassemble': 'Reassembling while preserving playback.', 'restore': 'Restoring the assembly, stopping motion and resetting speed.'}[kind]
    return result
