from copy import deepcopy
import tempfile
from pathlib import Path
import unittest
import numpy as np
from unittest.mock import Mock
from Research.native_objects import spatial_requirements as spatial
from Research.native_objects import requirements_experiment as pipeline
from Research.native_objects.test_assembly_connections import fixture,part,port,mate
from Research.native_objects.test_construction_solid import operation


def contract(roles,op,subject='e1',target='e0',reference='',axis=''):
    reqs=[{'id':'exists_'+str(i),'obligation':'required','kind':'entity','subject':'e'+str(i),
        'target':'','predicate':'exists','value':'','mode':'structure','basis':'inferred','source':'s0'} for i in range(len(roles))]
    reqs.append({'id':'spatial','obligation':'required','kind':'relation','subject':subject,'target':target,
        'predicate':'other','value':'Frozen synthetic spatial requirement','mode':'structure','basis':'explicit','source':'s0'})
    raw={'requirements':reqs,'exclusions':[],'spatial':[{'id':'spatial','operator':op,'reference':reference,'axis':axis}]}
    return spatial.validate(raw,'A synthetic assembly.',roles)


def bindings(c,p,refs):
    group=spatial.groups(c,p)
    out=[{'id':r['id'],'kind':'components','refs':['part:'+x for x in sorted(group[r['subject']])],'note':''}
         for r in c['inventory']['requirements'] if r['predicate']=='exists']
    return out+[{'id':'spatial','kind':'constraint','refs':refs,'note':''}]


def radial(ends=False):
    p=fixture();p['parts']=[part('hub','',operation('box',[.4,.08,.4]))];p['ports']=[];p['mates']=[]
    for i,face in enumerate(('+x','+z','-x','-z')):
        ident='arm'+str(i);a=part(ident,'hub',operation('box',[.2,.04,.04]));a['role']='members';p['parts'].append(a)
        p['ports'] += [port('hub'+str(i),'hub','face',face),port('inner'+str(i),ident,'face','-x')]
        m=mate();m.update(id='join'+str(i),a='hub'+str(i),b='inner'+str(i));p['mates'].append(m)
        if ends:
            end='end'+str(i);a=part(end,ident,operation('box',[.04,.05,.05]));a['role']='ends';p['parts'].append(a)
            p['ports'] += [port('outer'+str(i),ident,'face','+x'),port('cap'+str(i),end,'face','-x')]
            m=mate();m.update(id='endjoin'+str(i),a='outer'+str(i),b='cap'+str(i));p['mates'].append(m)
    return p


class SpatialTests(unittest.TestCase):
    def check(self,c,p,refs,mutate=None):
        b=bindings(c,p,refs);self.assertTrue(spatial.coverage(c,p,b)['geometry_allowed'])
        roles=sorted({part['role'] for part in p['parts']})
        _,report,compiled=spatial.geometry.build(p,roles,'spatial-test',spatial.geometry.freeze(p,roles))
        if mutate:mutate(compiled)
        return spatial.measurements(c,p,b,compiled),report

    def test_on_top_measures_pose_not_attachment_label(self):
        c=contract(['host','child'],'on_top');p=fixture()
        checks,report=self.check(c,p,['mate:connection']);self.assertTrue(checks[0]['passed']);self.assertTrue(report['declared_relations_passed'])
        p['ports'][0]['face']='+x';p['ports'][1]['face']='-x'
        checks,report=self.check(c,p,['mate:connection']);self.assertTrue(report['declared_relations_passed']);self.assertFalse(checks[0]['passed'])

    def test_root_rotation_and_reversed_mate_preserve_object_up(self):
        c=contract(['host','child'],'on_top');p=fixture();p['parts'][0]['rotation']=[20,40,30]
        p['mates'][0]['a'],p['mates'][0]['b']=p['mates'][0]['b'],p['mates'][0]['a']
        self.assertTrue(self.check(c,p,['mate:connection'])[0][0]['passed'])

    def test_visible_gap_cannot_pass_on_top_contact(self):
        c=contract(['host','child'],'on_top');p=fixture();p['mates'][0]['offset']=.005
        self.assertFalse(self.check(c,p,['mate:connection'])[0][0]['passed'])

    def test_buried_feature_is_not_spatial_proof(self):
        c=contract(['host','child'],'on_top');p=fixture();p['parts'][0]['forms'].append(operation('box',[.4,.1,.4],[0,.06,0]))
        self.assertFalse(self.check(c,p,['mate:connection'])[0][0]['passed'])

    def test_axis_alignment_needs_real_axis_mate(self):
        c=contract(['host','child'],'axis_aligned');p=fixture(True)
        self.assertTrue(self.check(c,p,['mate:connection'])[0][0]['passed'])
        face=fixture();self.assertFalse(spatial.coverage(c,face,bindings(c,face,['mate:connection']))['geometry_allowed'])

    def test_axis_misalignment_in_solved_output_fails(self):
        c=contract(['host','child'],'axis_aligned');p=fixture(True)
        self.assertFalse(self.check(c,p,['mate:connection'],lambda q:q['parts'][1].update(position=[.03,0,0]))[0][0]['passed'])

    def test_parallel_axes_check_actual_world_frames(self):
        c=contract(['host','child'],'parallel_axes');p=fixture(True);refs=['port:host_port','port:child_port']
        self.assertTrue(self.check(c,p,refs)[0][0]['passed'])
        self.assertFalse(self.check(c,p,refs,lambda q:q['parts'][1].update(rotation=[45,0,0]))[0][0]['passed'])

    def test_parallel_cannot_use_duplicate_or_missing_part_axes(self):
        c=contract(['host','child'],'parallel_axes');p=fixture(True)
        for refs in (['port:host_port'],['port:host_port','port:host_port'],['part:host','part:child']):
            self.assertFalse(spatial.coverage(c,p,bindings(c,p,refs))['geometry_allowed'])

    def test_radial_layout_checks_member_geometry_and_plane(self):
        c=contract(['hub','members'],'radial_outward',axis='y');p=radial();refs=['part:'+x['id'] for x in p['parts']]
        checks,report=self.check(c,p,refs);self.assertTrue(report['declared_relations_passed']);self.assertTrue(checks[0]['passed'],checks)
        p['parts'][1]['forms'][0]['size']=[.04,.04,.2]
        checks,report=self.check(c,p,refs);self.assertTrue(report['declared_relations_passed']);self.assertFalse(checks[0]['passed'])

    def test_radial_is_rotation_invariant_and_rejects_plane_drift(self):
        c=contract(['hub','members'],'radial_outward',axis='y');p=radial();refs=['part:'+x['id'] for x in p['parts']]
        p['parts'][0]['rotation']=[25,40,12]
        self.assertTrue(self.check(c,p,refs)[0][0]['passed'])
        p['parts'][0]['rotation']=[0,0,0]
        self.assertFalse(self.check(c,p,refs,lambda q:q['parts'][1]['position'].__setitem__(1,.1))[0][0]['passed'])

    def test_outward_end_and_wrong_end_are_distinct(self):
        c=contract(['hub','members','ends'],'outer_end',subject='e2',target='e1',reference='e0');p=radial(True);refs=['mate:endjoin'+str(i) for i in range(4)]
        checks,report=self.check(c,p,refs);self.assertTrue(report['declared_relations_passed']);self.assertTrue(checks[0]['passed'],checks)
        p['ports'][-2]['face']='-x'
        self.assertFalse(self.check(c,p,refs)[0][0]['passed'])

    def test_one_to_one_cannot_reuse_one_target(self):
        c=contract(['hub','members','ends'],'outer_end',subject='e2',target='e1',reference='e0');p=radial(True)
        p['mates'][-1]['a']='outer0'
        gate=spatial.coverage(c,p,bindings(c,p,['mate:endjoin'+str(i) for i in range(4)]))
        self.assertFalse(gate['geometry_allowed']);self.assertIn('bijection',gate['errors'][0]['reason'])

    def test_missing_binding_and_unrelated_refs_block_before_builder(self):
        c=contract(['host','child'],'on_top');p=fixture();b=bindings(c,p,['mate:connection'])[:-1]
        raw=pipeline.compact.pack(p,c,b);builder=Mock(side_effect=AssertionError('must not execute'))
        with tempfile.TemporaryDirectory() as folder:
            result,_=pipeline.evaluate_candidate(raw,c,Path(folder),'test',builder=builder)
        self.assertEqual(result['status'],'coverage_failed');builder.assert_not_called()
        self.assertFalse(spatial.coverage(c,p,bindings(c,p,['mate:unknown']))['geometry_allowed'])

    def test_unsupported_stays_explicit_and_required_blocks(self):
        c=contract(['host','child'],'on_top');p=fixture();b=bindings(c,p,[]);b[-1].update(kind='unsupported',note='Cannot realize contact')
        gate=spatial.coverage(c,p,b);self.assertTrue(gate['coverage_complete']);self.assertFalse(gate['geometry_allowed'])

    def test_contract_rule_and_policy_changes_rejected(self):
        c=contract(['host','child'],'on_top');c['spatial_rules'][0]['operator']='axis_aligned'
        with self.assertRaises(ValueError):spatial.preflight(c)
        c=contract(['host','child'],'on_top');c['spatial_policy_sha256']='changed'
        with self.assertRaises(ValueError):spatial.preflight(c)

    def test_spatial_cannot_authorize_behavior_or_evidence(self):
        for fields in ({'mode':'behavior'}, {'obligation':'evidence_required'}, {'predicate':'capability','value':'animate','mode':'behavior','target':''}):
            c=contract(['host','child'],'on_top');c['inventory']['requirements'][-1].update(fields);c['inventory_sha256']=spatial.intent.digest(c['inventory'])
            with self.assertRaises(ValueError):spatial.preflight(c)

    def test_unmapped_structural_requirement_still_blocks(self):
        c=contract(['host','child'],'on_top');r=deepcopy(c['inventory']['requirements'][-1]);r['id']='unmapped';c['inventory']['requirements'].append(r)
        c['inventory_sha256']=spatial.intent.digest(c['inventory']);c['source_grounding']['bindings']['unmapped']='s0';c['source_grounding_sha256']=spatial.intent.digest(c['source_grounding'])
        self.assertFalse(spatial.preflight(c)['planning_allowed'])
        self.assertEqual(spatial.preflight(c)['blocking'][0]['id'],'unmapped')

    def test_coverage_does_not_change_canonical_contract(self):
        c=contract(['host','child'],'on_top');original=deepcopy(c);p=fixture()
        spatial.coverage(c,p,bindings(c,p,['mate:connection']));self.assertEqual(c,original)

    def test_post_geometry_failure_changes_pipeline_status(self):
        c=contract(['host','child'],'on_top');p=fixture();p['ports'][0]['face']='+x';p['ports'][1]['face']='-x'
        raw=pipeline.compact.pack(p,c,bindings(c,p,['mate:connection']))
        with tempfile.TemporaryDirectory() as folder:
            result,_=pipeline.evaluate_candidate(raw,c,Path(folder),'test',renderer=lambda _:None)
        self.assertTrue(result['geometry_executed']);self.assertEqual(result['status'],'geometry_failed')
        self.assertTrue(any(x['kind']=='spatial_requirement' for x in result['feedback']['failed_geometry_checks']))

if __name__=='__main__':unittest.main()
