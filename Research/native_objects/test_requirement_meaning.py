import copy
import tempfile
from pathlib import Path
import unittest
from Research.native_objects import requirement_meaning as meaning
from Research.native_objects import requirements_experiment as runner
from Research.native_objects.test_intent_requirements import inventory, proposal, bindings, req, REQUEST


def raw(extra=None,exclusions=None):
    d=inventory(extra)['inventory']
    for r in d['requirements']:
        r['basis']='explicit';r['mode']='appearance' if r['predicate']=='appearance' or r['value']=='emission' else 'behavior' if r['predicate']=='capability' else 'structure'
    d['exclusions']=exclusions or [];return d


def contract(d):return meaning.validate(d,REQUEST,['host','child'])

class MeaningTests(unittest.TestCase):
    def test_appearance_does_not_demand_physical_verification(self):
        c=contract(raw([req('pose','appearance',value='visually hanging',kind='visual')]))
        self.assertTrue(meaning.preflight(c)['planning_allowed'])
        gate=meaning.coverage(c,proposal(),bindings()+[{'id':'pose','kind':'components','refs':['part:child'],'note':''}])
        self.assertTrue(gate['geometry_allowed']);self.assertTrue(gate['residual_checks'])
    def test_inside_cannot_be_reclassified_as_appearance(self):
        d=raw();d['requirements'][-1]['mode']='appearance'
        with self.assertRaises(ValueError):contract(d)
    def test_glow_is_not_implemented_by_a_color(self):
        c=contract(raw([req('light','capability',value='emission',kind='visual')]))
        self.assertFalse(meaning.preflight(c)['planning_allowed'])
    def test_unsupported_behavior_stops_before_planner(self):
        d=raw([req('move','capability',value='animate',kind='behavior')])
        calls=[]
        def model(case,stage,attempt,context,folder):calls.append(stage);return d,{}
        items=[{'case_id':c,'request':REQUEST,'candidate':{'plan':{'fidelity':'generic_design','retrieval':'none','next_step':'propose_geometry','components':[{'name':'host'},{'name':'child'}]}}} for c in runner.CASES]
        with tempfile.TemporaryDirectory() as folder:states=runner.execute(items,Path(folder),model)
        self.assertEqual(calls,['extract']*4)
        self.assertTrue(all(s['status']=='unsupported_before_planning' and not s['geometry_executed'] for s in states.values()))
    def test_excluded_motion_does_not_erase_inspection(self):
        d=raw([req('look','capability',value='inspect',kind='behavior')],[{'id':'no_motion','subject':'object','domain':'motion','quote':REQUEST}])
        self.assertTrue(meaning.preflight(contract(d))['planning_allowed'])
    def test_positive_motion_conflicts_with_exclusion(self):
        d=raw([req('move','capability',value='animate',kind='behavior')],[{'id':'no_motion','subject':'object','domain':'motion','quote':REQUEST}])
        with self.assertRaises(ValueError):contract(d)
    def test_verified_claim_requires_evidence(self):
        d=raw([req('load','other',value='verified load',kind='constraint')]);d['requirements'][-1]['mode']='physical_verification'
        with self.assertRaises(ValueError):contract(d)
        d['requirements'][-1]['obligation']='evidence_required';c=contract(d)
        self.assertFalse(meaning.preflight(c)['planning_allowed'])
    def test_optional_verification_does_not_become_required(self):
        d=raw([req('load','other',value='verified load',kind='constraint',obligation='optional')]);d['requirements'][-1]['mode']='physical_verification'
        self.assertTrue(meaning.preflight(contract(d))['planning_allowed'])
        self.assertEqual(len(meaning.preflight(contract(d))['unsupported']),1)
    def test_inferred_unsupported_relationship_stays_explicit(self):
        d=raw([req('axes','other',value='parallel functional axes',kind='constraint')]);d['requirements'][-1]['basis']='inferred';c=contract(d)
        gate=meaning.preflight(c);self.assertFalse(gate['planning_allowed']);self.assertEqual(gate['blocking'][0]['basis'],'inferred')
    def test_interpretation_and_waivers_are_frozen(self):
        for change in ('mode','exclusion'):
            c=contract(raw())
            if change=='mode':c['inventory']['requirements'][0]['mode']='appearance'
            else:c['inventory']['exclusions'].append({'id':'new'})
            with self.assertRaises(ValueError):meaning.preflight(c)
    def test_exclusion_requires_quoted_source_and_unique_id(self):
        for e in ({'id':'inside','subject':'object','domain':'motion','quote':REQUEST},{'id':'no_motion','subject':'object','domain':'motion','quote':'Invented'}):
            with self.assertRaises(ValueError):contract(raw(exclusions=[e]))
    def test_plain_geometry_cannot_claim_verified_identity(self):
        d=raw([req('exact','exact_identity',value='specified product',kind='visual',obligation='evidence_required')]);d['requirements'][-1]['mode']='identity';c=contract(d)
        gate=meaning.coverage(c,proposal(),bindings()+[{'id':'exact','kind':'components','refs':['part:child'],'note':''}])
        self.assertFalse(gate['geometry_allowed'])
if __name__=='__main__':unittest.main()
