"""Offline contract tests; scripted responses are not intelligence evaluations."""
from copy import deepcopy
import unittest
from behavior_decision import BehaviorError, BehaviorPlanner, build_request, validate_response


def package():
    return {'schema': 'oryn-native-experiment-v1', 'id': 'unfamiliar-object',
            'units': 'source_units', 'origins': {'geometry': 'model_generated', 'semantics': 'unknown'},
            'parts': [{'id': 'piece-a', 'vertices': [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                       'triangles': [0, 1, 2], 'semantic_role': None, 'motion': None}], 'frames': []}


def proposal(decision='uncertain'):
    return {'decision': decision, 'reason': 'Scripted contract-test response.',
            'component_ids': ['piece-a'] if decision == 'animate' else [],
            'proposed_behavior': 'Rotate this component.' if decision == 'animate' else '',
            'missing_evidence': ['Identify the component and validate its joint.']}


class BehaviorDecisionTests(unittest.TestCase):
    def setUp(self):
        self.p = package()
        self.request = build_request(self.p, 'Show how this works.')

    def validate(self, raw):
        return validate_response(raw, self.request, self.request)

    def test_no_connection_never_guesses_or_calls_a_provider(self):
        with self.assertRaisesRegex(BehaviorError, 'No behavior model connected'):
            BehaviorPlanner().decide(self.p, 'Show how this works.', current_context=lambda: (self.p, '', None))

    def test_all_decisions_are_candidates_and_never_execute(self):
        for decision in ['animate', 'no_animation', 'uncertain']:
            record = self.validate(proposal(decision))
            self.assertEqual(record['status'], 'candidate')
            self.assertFalse(record['execution_allowed'])
            self.assertFalse(record['independently_verified'])
        self.assertEqual(self.validate(proposal('animate'))['execution_status'], 'requires_motion_validation')

    def test_static_decision_is_scoped_to_request_and_selection(self):
        request = build_request(self.p, 'Let me inspect this.', 'piece-a')
        record = validate_response(proposal('no_animation'), request, request)
        self.assertEqual(record['request'], 'Let me inspect this.')
        self.assertEqual(record['selected_component_id'], 'piece-a')

    def test_unknown_and_duplicate_component_ids_are_rejected(self):
        for ids in [['invented'], ['piece-a', 'piece-a'], [None], 'piece-a']:
            raw = proposal('animate');raw['component_ids'] = ids
            with self.assertRaises(BehaviorError): self.validate(raw)

    def test_uncertainty_requires_missing_evidence(self):
        raw = proposal();raw['missing_evidence'] = []
        with self.assertRaises(BehaviorError): self.validate(raw)

    def test_animation_needs_components_and_description(self):
        for field, value in [('component_ids', []), ('proposed_behavior', ' ')]:
            raw = proposal('animate');raw[field] = value
            with self.assertRaises(BehaviorError): self.validate(raw)

    def test_no_animation_cannot_smuggle_motion_or_commands(self):
        for field, value in [('component_ids', ['piece-a']), ('proposed_behavior', 'Spin'), ('command', 'play')]:
            raw = proposal('no_animation');raw[field] = value
            with self.assertRaises(BehaviorError): self.validate(raw)

    def test_changed_geometry_request_or_selection_discards_result(self):
        changed = deepcopy(self.p);changed['parts'][0]['vertices'][0][0] = .1
        for p, q, selected in [(changed, 'Show how this works.', None),
                               (self.p, 'Keep it still.', None),
                               (self.p, 'Show how this works.', 'piece-a')]:
            with self.assertRaisesRegex(BehaviorError, 'changed'):
                validate_response(proposal(), self.request, build_request(p, q, selected))

    def test_model_gets_a_snapshot_and_cannot_mutate_object(self):
        original = deepcopy(self.p);calls = []
        def model(request):
            calls.append(request);request['context']['components'][0]['semantic_role'] = 'invented'
            return proposal()
        result = BehaviorPlanner(model).decide(self.p, 'Show how this works.',
                    current_context=lambda: (self.p, 'Show how this works.', None))
        self.assertEqual(len(calls), 1);self.assertEqual(self.p, original)
        self.assertEqual(result['context_token'], self.request['context_token'])

    def test_model_failure_has_no_retry(self):
        calls = []
        def failed(request):
            calls.append(request);raise RuntimeError('Do not expose provider error details.')
        with self.assertRaisesRegex(BehaviorError, 'no decision or automatic retry'):
            BehaviorPlanner(failed).decide(self.p, 'Show how this works.', current_context=lambda: None)
        self.assertEqual(len(calls), 1)

    def test_stale_result_is_rejected_after_model_returns(self):
        def model(request):
            self.p['parts'][0]['motion'] = {'kind': 'fixed'}
            return proposal('animate')
        with self.assertRaisesRegex(BehaviorError, 'changed'):
            BehaviorPlanner(model).decide(self.p, 'Show how this works.',
                        current_context=lambda: (self.p, 'Show how this works.', None))

    def test_unknown_semantics_preserved_and_raw_mesh_not_sent(self):
        context = self.request['context'];component = context['components'][0]
        self.assertIsNone(component['semantic_role']);self.assertIsNone(component['declared_motion'])
        self.assertNotIn('vertices', component);self.assertNotIn('triangles', component)
        self.assertEqual(context['origins']['semantics'], 'unknown')

    def test_invalid_selection_or_geometry_is_rejected_before_call(self):
        with self.assertRaises(BehaviorError): build_request(self.p, 'Inspect.', 'missing')
        self.p['parts'][0]['vertices'][0][0] = float('nan')
        with self.assertRaises(BehaviorError): build_request(self.p, 'Inspect.')

    def test_unbounded_or_malformed_model_response_is_rejected(self):
        for raw in [None, {}, {**proposal(), 'decision': []}, {**proposal(), 'reason': 'x' * 1001},
                    {**proposal(), 'missing_evidence': [None]}]:
            with self.assertRaises(BehaviorError): self.validate(raw)

    def test_request_change_on_same_object_changes_token(self):
        self.assertNotEqual(build_request(self.p, 'Inspect.')['context_token'],
                            build_request(self.p, 'Show how this works.')['context_token'])


if __name__ == '__main__': unittest.main()
