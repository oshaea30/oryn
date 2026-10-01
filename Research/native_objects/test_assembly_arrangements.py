from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import numpy as np
from Research.native_objects import assembly_arrangements as arrangement
from Research.native_objects import requirements_experiment as pipeline
from Research.native_objects.test_assembly_connections import fixture,part,port,mate
from Research.native_objects.test_construction_solid import operation


def raw_inventory(pattern='linear',direction='+y',count=3):
    requirements=[{'id':'exists_'+str(i),'obligation':'required','kind':'entity','subject':'e'+str(i),
        'target':'','predicate':'exists','value':'','mode':'structure','basis':'inferred','source':'s0'} for i in range(2)]
    requirements += [dict(requirements[1],id='number',predicate='count',value=str(count),kind='constraint'),
        dict(requirements[1],id='layout',predicate='other',value='Synthetic declared layout',kind='constraint',target='e0' if pattern=='radial' else ''),
        dict(requirements[1],id='facing',predicate='other',value='Synthetic declared axes',kind='constraint')]
    return {'requirements':requirements,'exclusions':[],'spatial':[],
        'assemblies':[{'id':'array','members':['e1'],
            'placement':{'id':'layout','pattern':pattern,'axis':'y' if pattern=='radial' else 'x' if pattern=='linear' else '',
                         'reference':'e0' if pattern=='radial' else ''},
            'orientation':{'id':'facing','direction':direction}}]}


def contract(pattern='linear',direction='+y',count=3):
    return arrangement.validate(raw_inventory(pattern,direction,count),'A synthetic repeated assembly.',['holder','members'])


def proposal(pattern='linear',count=3):
    p=fixture();p['parts']=[part('holder','',operation('box',[.9,.08,.9]))];p['ports']=[];p['mates']=[]
    positions=([[.25*float(np.cos(i*2*np.pi/count)),0,.25*float(np.sin(i*2*np.pi/count))] for i in range(count)] if pattern=='radial'
               else [[(i-(count-1)/2)*.2,0,0] for i in range(count)])
    for i,position in enumerate(positions):
        p['parts'][0]['forms'].append(operation('cylinder',[.08,.1,.08],position,op='subtract'))
        ident='member'+str(i);child=part(ident,'holder',operation('cylinder',[.04,.12,.04]));child['role']='members';p['parts'].append(child)
        p['ports'] += [port('bore'+str(i),'holder','bore_axis',form=i+1,span=[.15,.85]),port('axis'+str(i),ident,'outer_axis')]
        m=mate('coaxial');m.update(id='joint'+str(i),a='bore'+str(i),b='axis'+str(i),minimum_overlap=.04,minimum_clearance=.005);p['mates'].append(m)
    return p


def bindings(c,p):
    groups=arrangement.spatial.groups(c,p)
    out=[{'id':r['id'],'kind':'components','refs':['part:'+v for v in sorted(groups[r['subject']])],'note':''}
         for r in c['inventory']['requirements'] if r['predicate'] in ('exists','count')]
    axes=['port:'+v['id'] for v in p['ports'] if v['kind']=='outer_axis']
    if c['assemblies']:
        a=c['assemblies'][0]
        out += [{'id':'layout','kind':'constraint','refs':axes+(['part:holder'] if a['placement']['pattern']=='radial' else []),'note':''},
                {'id':'facing','kind':'constraint','refs':axes,'note':''}]
    return out


class ArrangementTests(unittest.TestCase):
    def measure(self,c,p,mutate=None):
        b=bindings(c,p);self.assertTrue(arrangement.coverage(c,p,b)['geometry_allowed'])
        roles=['holder','members'];_,report,compiled=arrangement.geometry.build(p,roles,'synthetic',arrangement.geometry.freeze(p,roles))
        if mutate:mutate(compiled)
        return arrangement.measurements(c,p,b,compiled),report

    def test_repeated_entity_cannot_omit_decision(self):
        raw=raw_inventory();raw['assemblies']=[]
        with self.assertRaisesRegex(ValueError,'lack arrangement'):arrangement.validate(raw,'A synthetic repeated assembly.',['holder','members'])

    def test_two_member_directions_cannot_share_one_requirement(self):
        raw=raw_inventory();raw['assemblies'][0]['orientation']['id']='layout'
        with self.assertRaises(ValueError):arrangement.validate(raw,'A synthetic repeated assembly.',['holder','members'])

    def test_duplicate_and_unknown_members_and_invalid_endpoints_reject(self):
        for members in (['e1','e1'],['invented'],[]):
            raw=raw_inventory();raw['assemblies'][0]['members']=members
            with self.assertRaises(ValueError):arrangement.validate(raw,'A synthetic repeated assembly.',['holder','members'])
        raw=raw_inventory();raw['requirements'][-1]['target']='e0'
        with self.assertRaisesRegex(ValueError,'endpoints'):arrangement.validate(raw,'A synthetic repeated assembly.',['holder','members'])

    def test_unrecognized_arrangement_is_preserved_and_blocks(self):
        c=contract('unsupported');self.assertFalse(arrangement.preflight(c)['planning_allowed'])
        self.assertEqual(arrangement.preflight(c)['blocking'][0]['id'],'layout')
        c=contract(direction='unsupported');self.assertFalse(arrangement.preflight(c)['planning_allowed'])

    def test_evidence_and_effect_cannot_be_authorized(self):
        for update in ({'obligation':'evidence_required','mode':'physical_verification'}, {'predicate':'capability','value':'animate','mode':'behavior'}):
            raw=raw_inventory();raw['requirements'][-1].update(update)
            with self.assertRaises(ValueError):arrangement.validate(raw,'A synthetic repeated assembly.',['holder','members'])

    def test_count_deletion_cannot_allow_unplanned_repetition(self):
        raw=raw_inventory();raw['assemblies']=[];raw['requirements']=raw['requirements'][:2]
        c=arrangement.validate(raw,'A synthetic repeated assembly.',['holder','members']);p=proposal()
        gate=arrangement.coverage(c,p,bindings(c,p));self.assertFalse(gate['geometry_allowed'])
        self.assertTrue(any('lacks a frozen' in e['reason'] for e in gate['errors']))

    def test_frame_rotation_and_translation_preserve_radial_and_linear(self):
        for pattern in ('radial','linear'):
            c=contract(pattern);p=proposal(pattern);p['parts'][0].update(rotation=[24,49,33],position=[.8,-.4,.1])
            checks,report=self.measure(c,p)
            self.assertTrue(report['declared_relations_passed']);self.assertTrue(all(v['passed'] for v in checks),checks)

    def test_sideways_or_reversed_axis_fails_signed_facing(self):
        c=contract();p=proposal()
        for rotation in ([90,0,0],[180,0,0]):
            checks,_=self.measure(c,p,lambda q:q['parts'][2].update(rotation=rotation))
            self.assertFalse(checks[1]['passed']);self.assertFalse(next(v['passed'] for v in checks[1]['measurement']['members'] if v['part']=='member1'))
            self.assertEqual(checks[1]['assembly_id'],'array');self.assertEqual(checks[1]['requirement_id'],'facing')
        checks,_=self.measure(contract(direction='parallel'),p,lambda q:q['parts'][2].update(rotation=[180,0,0]))
        self.assertTrue(checks[1]['passed'])

    def test_all_parallel_but_sideways_fails_declared_object_up(self):
        c=contract();p=proposal()
        def turn(q):
            for part in q['parts'][1:]:part['rotation']=[0,0,90]
        self.assertFalse(self.measure(c,p,turn)[0][1]['passed'])

    def test_linear_rejects_off_axis_unequal_spacing_and_duplicates(self):
        c=contract();p=proposal()
        for position in ([0,.02,0],[.04,0,0],[-.2,0,0]):
            checks,_=self.measure(c,p,lambda q:q['parts'][2].update(position=position))
            self.assertFalse(checks[0]['passed'],position)

    def test_radial_rejects_unequal_radius_height_and_bearings(self):
        c=contract('radial',count=4);p=proposal('radial',4)
        for position in ([.35,0,0],[.25,.03,0],[.15,0,.2],[0,0,0]):
            self.assertFalse(self.measure(c,p,lambda q:q['parts'][1].update(position=position))[0][0]['passed'],position)

    def test_circle_phase_and_linear_offset_are_free(self):
        c=contract('radial',count=4);p=proposal('radial',4)
        for f in p['parts'][0]['forms'][1:]:
            x,y,z=f['offset'];f['offset']=[float((x-z)/np.sqrt(2)),y,float((x+z)/np.sqrt(2))]
        self.assertTrue(self.measure(c,p)[0][0]['passed'])
        c=contract();p=proposal()
        for f in p['parts'][0]['forms'][1:]:f['offset'][2]+=.1
        self.assertTrue(self.measure(c,p)[0][0]['passed'])

    def test_unknown_duplicate_unrelated_and_missing_ports_stop_before_geometry(self):
        c=contract();p=proposal()
        for refs in (['port:axis0'],['port:axis0','port:axis0','port:axis2'],['port:bore0','port:axis1','port:axis2'],['port:axis0','port:axis1','port:absent']):
            b=bindings(c,p);b[-1]['refs']=refs;gate=arrangement.coverage(c,p,b)
            self.assertFalse(gate['geometry_allowed'])
        b=bindings(c,p)[:-1];raw=pipeline.compact.pack(p,c,b)
        with tempfile.TemporaryDirectory() as folder:
            builder=Mock(side_effect=AssertionError('Do not build'))
            result,_=pipeline.evaluate_candidate(raw,c,Path(folder),'test',builder=builder)
            self.assertEqual(result['status'],'coverage_failed');builder.assert_not_called()

    def test_placement_and_facing_cannot_select_different_features(self):
        c=contract();p=proposal();p['ports'].append(port('extra','member0','outer_axis'))
        # Existing mate use is necessary even in a malicious direct coverage call.
        p['mates'].append(dict(p['mates'][0],id='extra_joint',b='extra'))
        b=bindings(c,p);b[-1]['refs']=['port:extra','port:axis1','port:axis2'];b[-2]['refs']=['port:axis0','port:axis1','port:axis2']
        self.assertTrue(any('same per-member' in e['reason'] for e in arrangement.coverage(c,p,b)['errors']))

    def test_contract_and_policy_are_immutable(self):
        c=contract();original=deepcopy(c);p=proposal();b=bindings(c,p)
        arrangement.coverage(c,p,b);self.assertEqual(c,original)
        for key in ('assemblies_sha256','arrangement_policy_sha256'):
            changed=deepcopy(c);changed[key]='tampered'
            with self.assertRaises(ValueError):arrangement.preflight(changed)

    def test_buried_axis_or_disconnected_solid_does_not_pass_full_pipeline(self):
        c=contract();p=proposal();p['parts'][1]['forms'].append(operation('cylinder',[.07,.12,.07]))
        checks,report=self.measure(c,p);self.assertFalse(all(c['passed'] for c in checks));self.assertFalse(report['declared_relations_passed'])
        p=proposal();p['parts'][1]['forms'].append(operation('box',[.03,.03,.03],[0,.25,0]))
        checks,report=self.measure(c,p);self.assertTrue(all(c['passed'] for c in checks));self.assertFalse(report['declared_relations_passed'])
        self.assertTrue(any(v['kind']=='connected_component' and not v['passed'] for v in report['checks']))

    def test_report_keeps_group_failure_and_binding_lock_rejects_repair(self):
        c=contract();p=proposal();p['parts'][0]['forms'][2]['offset'][0]+=.04
        raw=pipeline.compact.pack(p,c,bindings(c,p))
        with tempfile.TemporaryDirectory() as folder:
            result,lock=pipeline.evaluate_candidate(raw,c,Path(folder),'test',renderer=lambda _:None)
            self.assertEqual(result['status'],'geometry_failed')
            report=json.loads((Path(folder)/'report.json').read_text());self.assertEqual(report['checks']['assembly_arrangements']['status'],'fail')
            self.assertFalse(report['layers']['object']['structural_checks_passed'])
            frozen=json.loads((Path(folder)/'arrangement-bindings.json').read_text());changed=deepcopy(raw);changed['bindings'][-1].update(kind='unsupported',refs=[],note='Changed')
            builder=Mock(side_effect=AssertionError('Do not build'))
            result,_=pipeline.evaluate_candidate(changed,c,Path(folder),'test',locked=lock,locked_bindings=frozen,builder=builder)
            self.assertEqual(result['status'],'coverage_failed');builder.assert_not_called()

    def test_radial_members_reuse_existing_geometry_orientation_rule(self):
        from Research.native_objects.test_spatial_requirements import radial
        raw=raw_inventory('radial',count=4);raw['requirements'][-1]['target']='e0'
        raw['spatial']=[{'id':'facing','operator':'radial_outward','axis':'y','reference':''}]
        raw['assemblies'][0]['orientation']['direction']='spatial'
        c=arrangement.validate(raw,'A synthetic repeated assembly.',['hub','members']);p=radial()
        b=[{'id':'exists_0','kind':'components','refs':['part:hub'],'note':''}]
        arms=['part:arm'+str(i) for i in range(4)]
        b += [{'id':rid,'kind':'components','refs':arms,'note':''} for rid in ('exists_1','number')]
        b += [{'id':'layout','kind':'constraint','refs':['port:inner'+str(i) for i in range(4)]+['part:hub'],'note':''},
              {'id':'facing','kind':'constraint','refs':['part:hub']+arms,'note':''}]
        self.assertTrue(arrangement.coverage(c,p,b)['geometry_allowed'])
        _,_,compiled=arrangement.geometry.build(p,['hub','members'],'test',arrangement.geometry.freeze(p,['hub','members']))
        self.assertTrue(all(c['passed'] for c in arrangement.measurements(c,p,b,compiled)))
        p['parts'][1]['forms'][0]['size']=[.04,.04,.2]
        _,_,compiled=arrangement.geometry.build(p,['hub','members'],'test',arrangement.geometry.freeze(p,['hub','members']))
        self.assertFalse(arrangement.measurements(c,p,b,compiled)[1]['passed'])
        wrong=deepcopy(raw);wrong['assemblies'][0]['placement']['axis']='x'
        with self.assertRaises(ValueError):arrangement.validate(wrong,'A synthetic repeated assembly.',['hub','members'])

    def test_saved_drone_geometry_exposes_wrong_axes_without_editing_it(self):
        source=Path(__file__).parent/'results/spatial-009/generic-drone-plan-0'
        previous=json.loads((source.parent/'generic-drone-extract/contract.json').read_text())
        raw_plan=json.loads((source/'compact-plan.json').read_text());p=pipeline.compact.expand(raw_plan,previous)
        compiled=json.loads((source/'compiled.json').read_text());before=deepcopy(compiled)
        # A synthetic negative-control constraint, never supplied as a repair to the model.
        roles=[e['role'] for e in previous['inventory']['entities']];raw=raw_inventory('radial',count=4)
        req0=raw['requirements'][0];raw['requirements']=[dict(req0,id='exist_'+str(i),subject='e'+str(i)) for i in range(len(roles))]+[
            dict(req0,id='number',subject='e2',kind='constraint',predicate='count',value='4'),
            dict(req0,id='layout',subject='e2',target='e0',kind='constraint',predicate='other',value='Synthetic negative-control radial layout'),
            dict(req0,id='facing',subject='e2',kind='constraint',predicate='other',value='Synthetic negative-control upright axes')]
        raw['assemblies'][0]['members']=['e2'];c=arrangement.validate(raw,'A synthetic repeated assembly.',roles)
        motors={x['id'] for x in p['parts'] if x['role']=='Four motors'}
        refs=['port:'+next(x['id'] for x in p['ports'] if x['part']==motor and x['kind'] in ('outer_axis','bore_axis')) for motor in sorted(motors)]
        center=next(x['id'] for x in p['parts'] if x['role']=='Central frame')
        b=[{'id':'layout','kind':'constraint','refs':refs+['part:'+center],'note':''},{'id':'facing','kind':'constraint','refs':refs,'note':''}]
        check=arrangement.measurements(c,p,b,compiled)[1]
        self.assertFalse(check['passed']);self.assertEqual(sum(not m['passed'] for m in check['measurement']['members']),2)
        self.assertEqual(compiled,before)

    def test_extraction_pipeline_preserves_decisions_without_an_extra_model(self):
        raw=raw_inventory();c=contract();p=proposal();calls=[]
        item={'case_id':'new-family','request':'A synthetic repeated assembly.','candidate':{'plan':{
            'fidelity':'generic_design','retrieval':'none','next_step':'propose_geometry','components':[{'name':'holder'},{'name':'members'}]}}}
        def model(case,stage,attempt,context,folder):
            calls.append(stage)
            if stage=='extract':return raw,{}
            self.assertEqual(context['assemblies'],c['assemblies']);self.assertEqual(context['arrangement_policy'],arrangement.POLICY)
            return pipeline.compact.pack(p,c,bindings(c,p)),{}
        with tempfile.TemporaryDirectory() as folder:
            states=pipeline.execute([item],Path(folder),model,case_ids=('new-family',),renderer=lambda _:None)
        self.assertEqual(calls,['extract','plan']);self.assertEqual(states['new-family']['status'],'structural_candidate')

if __name__=='__main__':unittest.main()
