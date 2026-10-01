from copy import deepcopy
import unittest
from Research.native_objects import requirement_meaning as meaning


class BoundRequirementsTests(unittest.TestCase):
    request='Show two components. Keep the lever static.'
    roles=['Housing','Lever']

    def inventory(self):
        return {'requirements':[{'id':'r'+str(i),'obligation':'required','kind':'entity','subject':'e'+str(i),
            'target':'','predicate':'exists','value':'','mode':'structure','basis':'inferred','source':'s0'} for i in range(2)],
            'exclusions':[{'id':'x1','subject':'e1','domain':'motion','source':'s1'}]}

    def test_scoped_reference_uses_fixed_catalog_and_original_source(self):
        raw=self.inventory();unchanged=deepcopy(raw)
        contract=meaning.validate_bound_source_output(raw,self.request,self.roles)
        self.assertEqual(raw,unchanged)
        self.assertEqual(contract['inventory']['entities'],[{'id':'e0','role':'Housing'},{'id':'e1','role':'Lever'}])
        self.assertEqual(contract['inventory']['exclusions'][0]['subject'],'e1')
        self.assertEqual(contract['inventory']['exclusions'][0]['quote'],'Keep the lever static.')
        self.assertTrue(meaning.preflight(contract)['planning_allowed'])

    def test_invented_entity_reference_or_entity_list_rejected(self):
        for mutate in (lambda r:r['exclusions'][0].update(subject='supports'),
                       lambda r:r['requirements'][0].update(subject='housing'),
                       lambda r:r.update(entities=meaning.entity_catalog(self.roles))):
            raw=self.inventory();mutate(raw)
            with self.assertRaises(ValueError):meaning.validate_bound_source_output(raw,self.request,self.roles)

    def test_schema_limits_all_references_but_preserves_behavior_targets(self):
        schema=meaning.bound_source_schema(self.request,self.roles)
        self.assertEqual(set(schema['required']),{'requirements','exclusions'})
        for variant in schema['properties']['requirements']['items']['anyOf']:
            self.assertEqual(variant['properties']['subject']['enum'],['e0','e1','object'])
            expected=[''] if variant['properties']['predicate']['enum']==['capability'] else ['e0','e1','']
            self.assertEqual(variant['properties']['target']['enum'],expected)
        self.assertEqual(schema['properties']['exclusions']['items']['properties']['subject']['enum'],['e0','e1','object'])

    def test_invalid_catalog_and_missing_role_requirement_rejected(self):
        for roles in ([],['A','A'],[''],[None]):
            with self.assertRaises(ValueError):meaning.entity_catalog(roles)
        raw=self.inventory();raw['requirements'].pop()
        with self.assertRaises(ValueError):meaning.validate_bound_source_output(raw,self.request,self.roles)

    def test_unavailable_action_and_relation_remain_blocking(self):
        raw=self.inventory();raw['exclusions']=[]
        raw['requirements'] += [dict(raw['requirements'][0],id='r2',kind='behavior',subject='e1',predicate='other',mode='behavior',target='e0',value='stay attached while swinging',source='s1')]
        gate=meaning.preflight(meaning.validate_bound_source_output(raw,self.request,self.roles))
        self.assertFalse(gate['planning_allowed']);self.assertEqual(gate['blocking'][0]['id'],'r2')


class BoundPayloadTests(unittest.TestCase):
    def test_live_payload_is_one_case_and_has_no_expected_answers(self):
        from unittest.mock import patch
        from pathlib import Path
        from Research.native_objects import entity_confirmation as run
        case=run.CASES[0]
        with patch.object(run.previous,'dispatch',return_value=({},{})) as sender:
            run.request(case,Path('/unused'),None,'fake')
        body=sender.call_args.args[2]
        import json
        content=json.loads(body['input'][1]['content'])
        self.assertEqual(set(content),{'request','entities','source_units'})
        self.assertEqual(content['entities'],meaning.entity_catalog(case['roles']))
        self.assertEqual(body['text']['format']['schema'],meaning.bound_source_schema(case['request'],case['roles']))
        self.assertEqual(sender.call_args.kwargs['batch'],run.BATCH)
        self.assertEqual(run.BATCH.cases,tuple(c['id'] for c in run.previous.CASES))
        self.assertEqual(body['max_output_tokens'],3072)
