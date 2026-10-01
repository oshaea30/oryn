import copy
import unittest
from Research.native_objects import requirement_meaning as m
from Research.native_objects.test_requirement_meaning import raw,REQUEST


def sourced():
    d=raw()
    for r in d['requirements']:r.pop('quote');r['source']='s0'
    return d

class SourceReferenceTests(unittest.TestCase):
    def test_source_is_resolved_from_original_not_model_quote(self):
        c=m.validate_source_output(sourced(),REQUEST,['host','child'])
        self.assertTrue(all(r['quote']==REQUEST for r in c['inventory']['requirements']))
        self.assertTrue(m.preflight(c)['planning_allowed'])
    def test_invented_source_and_direct_quote_are_rejected(self):
        for change in ('unknown','quote'):
            d=sourced()
            if change=='unknown':d['requirements'][0]['source']='Battery'
            else:d['requirements'][0]['quote']=REQUEST
            with self.assertRaises(ValueError):m.validate_source_output(d,REQUEST,['host','child'])
    def test_unaccounted_source_sentence_stops(self):
        with self.assertRaisesRegex(ValueError,'Unaccounted'):m.validate_source_output(sourced(),REQUEST+' Do not animate it.',['host','child'])
    def test_exclusion_accounts_for_waived_sentence(self):
        request=REQUEST+' Do not animate it.';d=sourced();d['exclusions']=[{'id':'waived','subject':'object','domain':'motion','source':'s1'}]
        c=m.validate_source_output(d,request,['host','child']);self.assertEqual(c['inventory']['exclusions'][0]['quote'],'Do not animate it.')
    def test_source_segmentation_preserves_all_nonspace_characters(self):
        request='  Verify 0.5 kg.\n'+('Long phrase '*45)+' Final sentence. '
        units=m.source_units(request)
        self.assertTrue(all(request[u['start']:u['end']]==u['text'] and len(u['text'])<=180 for u in units))
        self.assertEqual(''.join(c for u in units for c in u['text'] if not c.isspace()),''.join(request.split()))
    def test_ambiguous_capability_label_is_rejected(self):
        d=sourced();r=copy.deepcopy(d['requirements'][0]);r.update(id='move',predicate='capability',kind='behavior',mode='behavior',value='animate swinging');d['requirements'].append(r)
        with self.assertRaisesRegex(ValueError,'canonical'):m.validate_source_output(d,REQUEST,['host','child'])
    def test_action_constraint_preserves_target_without_becoming_static_mate(self):
        d=sourced();r=copy.deepcopy(d['requirements'][0]);r.update(id='coupled',predicate='other',kind='behavior',mode='behavior',subject='host',target='child',value='attachment persists during motion');d['requirements'].append(r)
        c=m.validate_source_output(d,REQUEST,['host','child']);self.assertFalse(m.preflight(c)['planning_allowed'])
        self.assertEqual(c['inventory']['requirements'][-1]['target'],'child')
    def test_provenance_binding_tampering_is_rejected(self):
        c=m.validate_source_output(sourced(),REQUEST,['host','child']);c['source_grounding']['bindings']['inside']='missing'
        with self.assertRaises(ValueError):m.preflight(c)
    def test_schema_locks_capability_names_and_targets(self):
        variants=m.source_schema(REQUEST)['properties']['requirements']['items']['anyOf']
        action=variants[1]['properties'];self.assertEqual(action['target']['enum'],['']);self.assertIn('animate',action['value']['enum']);self.assertNotIn('animate swinging',action['value']['enum'])
if __name__=='__main__':unittest.main()
