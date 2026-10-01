import copy
import unittest
from Research.native_objects import intent_requirements as ir
from Research.native_objects import compact_construction as compact
from Research.native_objects import assembly_connections as geometry
from Research.native_objects.test_assembly_connections import fixture

REQUEST='Inspect the insert inside the sleeve, with a luminous finish.'
def req(ident,predicate,subject='child',target='',value='',kind='relation',obligation='required'):
    return {'id':ident,'obligation':obligation,'kind':kind,'subject':subject,'target':target,
            'predicate':predicate,'value':value,'quote':REQUEST}
def inventory(extra=None):
    raw={'entities':[{'id':'host','role':'host'},{'id':'child','role':'child'}],
         'requirements':[req('host_exists','exists','host',kind='entity'),req('child_exists','exists',kind='entity'),req('inside','inside',target='host')]}
    raw['requirements']+=extra or []
    return ir.validate_inventory(raw,REQUEST,['host','child'])
def bindings():return [{'id':'host_exists','kind':'components','refs':['part:host'],'note':''},
                       {'id':'child_exists','kind':'components','refs':['part:child'],'note':''},
                       {'id':'inside','kind':'relations','refs':['containment:0'],'note':''}]
def proposal():
    p=fixture(True);p['containments']=[{'inner':'child','outer':'host','clearance':.01}];return p

class RequirementTests(unittest.TestCase):
    def test_typed_inside_binding_survives_to_geometry(self):
        c,p,b=inventory(),proposal(),bindings();self.assertTrue(ir.coverage(c,p,b)['geometry_allowed'])
        _,report,_=geometry.build(p,['host','child'],'synthetic',geometry.freeze(p,['host','child']))
        self.assertTrue(report['declared_relations_passed'])
    def test_missing_requirement_is_not_covered(self):
        self.assertFalse(ir.coverage(inventory(),proposal(),bindings()[:-1])['coverage_complete'])
    def test_parent_or_mate_does_not_prove_inside(self):
        b=bindings();b[-1]['refs']=['mate:connection'];self.assertFalse(ir.coverage(inventory(),proposal(),b)['geometry_allowed'])
    def test_reversed_containment_is_rejected(self):
        p=proposal();p['containments'][0].update(inner='host',outer='child');self.assertFalse(ir.coverage(inventory(),p,bindings())['geometry_allowed'])
    def test_wrong_part_entity_is_rejected(self):
        b=bindings();b[1]['refs']=['part:host'];self.assertFalse(ir.coverage(inventory(),proposal(),b)['geometry_allowed'])
    def test_unknown_and_duplicate_ids_are_rejected(self):
        for extra in ({'id':'invented','kind':'unsupported','refs':[],'note':'no'},bindings()[0]):
            with self.assertRaises(ValueError):ir.coverage(inventory(),proposal(),bindings()+[extra])
    def test_required_unsupported_is_complete_but_blocks_geometry(self):
        c=inventory([req('light','capability',value='emission',kind='visual')]);b=bindings()+[{'id':'light','kind':'unsupported','refs':[],'note':'No emission renderer'}]
        gate=ir.coverage(c,proposal(),b);self.assertTrue(gate['coverage_complete']);self.assertFalse(gate['geometry_allowed'])
    def test_unsupported_cannot_masquerade_as_supported(self):
        c=inventory([req('light','capability',value='emission',kind='visual')]);b=bindings()+[{'id':'light','kind':'capability','refs':['capability:emission'],'note':''}]
        self.assertFalse(ir.coverage(c,proposal(),b)['coverage_complete'])
    def test_optional_unsupported_is_disclosed_without_blocking(self):
        c=inventory([req('light','capability',value='emission',kind='visual',obligation='optional')]);b=bindings()+[{'id':'light','kind':'unsupported','refs':[],'note':'Not implemented'}]
        gate=ir.coverage(c,proposal(),b);self.assertTrue(gate['geometry_allowed']);self.assertEqual(len(gate['unsupported']),1)
    def test_source_quote_and_contract_immutability(self):
        raw=inventory()['inventory'];raw['requirements'][0]['quote']='invented source'
        with self.assertRaises(ValueError):ir.validate_inventory(raw,REQUEST,['host','child'])
        c=inventory();c['inventory']['requirements'].pop()
        with self.assertRaises(ValueError):ir.coverage(c,proposal(),bindings())
    def test_count_requirement_checks_instances(self):
        c=inventory([req('two','count',value='2',kind='constraint')]);b=bindings()+[{'id':'two','kind':'components','refs':['part:child'],'note':''}]
        self.assertFalse(ir.coverage(c,proposal(),b)['geometry_allowed'])
    def test_evidence_cannot_be_replaced_by_geometry(self):
        c=inventory([req('exact','exact_identity',value='named product',kind='visual',obligation='evidence_required')]);b=bindings()+[{'id':'exact','kind':'components','refs':['part:child'],'note':''}]
        self.assertFalse(ir.coverage(c,proposal(),b)['geometry_allowed'])
    def test_negative_reference_is_invalid(self):
        b=bindings();b[-1]['refs']=['containment:-1'];self.assertFalse(ir.coverage(inventory(),proposal(),b)['coverage_complete'])
    def test_compact_roundtrip_preserves_geometry(self):
        c,p=inventory(),proposal();expanded=compact.expand(compact.pack(p,c,bindings()),c)
        before,_,_=geometry.build(p,['host','child'],'synthetic',geometry.freeze(p,['host','child']))
        after,_,_=geometry.build(expanded,['host','child'],'synthetic',geometry.freeze(expanded,['host','child']))
        self.assertEqual(before['parts'],after['parts'])
    def test_duplicate_detail_is_not_last_write_wins(self):
        c=inventory();small=compact.pack(proposal(),c,bindings());detail=small['shapes'][0]['forms'][0]['detail'];detail.append(copy.deepcopy(detail[0]))
        with self.assertRaises(ValueError):compact.expand(small,c)
if __name__=='__main__':unittest.main()
