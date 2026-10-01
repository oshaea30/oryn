import copy
import unittest
import numpy as np
from Research.native_objects import assembly_connections as assembly
from Research.native_objects.test_construction_solid import operation


def part(ident,parent,form):
    return {'id':ident,'role':ident,'parent':parent,'position':[0,0,0],'rotation':[0,0,0],
            'color':[.5,.6,.7],'forms':[form]}


def port(ident,component,kind,face='+y',form=0,span=None):
    return {'id':ident,'part':component,'kind':kind,'face':face,'form':form,'span':span or [0,1]}


def mate(kind='face'):
    return {'id':'connection','a':'host_port','b':'child_port','kind':kind,'offset':0,
            'twist':0,'minimum_clearance':.02 if kind=='coaxial' else 0,
            'minimum_overlap':.1 if kind=='coaxial' else 0}


def fixture(axis=False):
    host=operation('tube' if axis else 'box',[.2,.2,.2] if axis else [.4,.1,.4])
    if axis:host['wall']=.02
    child=operation('cylinder' if axis else 'box',[.1,.15,.1] if axis else [.1,.2,.1])
    return {'assumptions':[],'limitations':[],'parts':[part('host','',host),part('child','host',child)],
            'mounts':[],'containments':[],'clearances':[],'symmetries':[],'passages':[],
            'ports':[port('host_port','host','bore_axis' if axis else 'face'),
                     port('child_port','child','outer_axis' if axis else 'face','+y' if axis else '-y')],
            'mates':[mate('coaxial' if axis else 'face')]}


class ConnectionTests(unittest.TestCase):
    def build(self,p,locked=None):return assembly.build(p,['host','child'],'synthetic',locked or assembly.freeze(p,['host','child']))
    def test_face_contact_is_solved_instead_of_trusting_child_pose(self):
        p=fixture();p['parts'][1]['position']=[2,3,1];p['parts'][1]['rotation']=[20,60,80]
        pkg,report,compiled=self.build(p)
        self.assertTrue(report['declared_relations_passed'],report)
        np.testing.assert_allclose(compiled['parts'][1]['position'],[0,.15,0],atol=1e-8)
        self.assertEqual(pkg['schema'],'oryn-native-experiment-v1')
        self.assertEqual(p['parts'][1]['position'],[2,3,1])
    def test_root_rotation_and_reversed_mate_are_supported(self):
        p=fixture();p['parts'][0]['rotation']=[25,90,12];p['parts'][0]['position']=[.2,.4,-.1]
        p['mates'][0]['a'],p['mates'][0]['b']='child_port','host_port'
        _,report,_=self.build(p);self.assertTrue(report['declared_relations_passed'],report)
    def test_coaxial_fit_has_measured_gap_and_overlap(self):
        p=fixture(True);p['mates'][0]['offset']=.01
        _,report,_=self.build(p);self.assertTrue(report['declared_relations_passed'],report)
        measurement=next(c['measurement'] for c in report['checks'] if c['kind']=='executable_mate')
        self.assertAlmostEqual(measurement['radial_clearance_m'],.03)
        self.assertAlmostEqual(measurement['axial_overlap_m'],.15)
    def test_shaft_too_large_is_rejected(self):
        p=fixture(True);p['parts'][1]['forms'][0]['size']=[.18,.15,.18]
        _,report,_=self.build(p)
        self.assertFalse(report['declared_relations_passed'])
        self.assertTrue(any(c['kind']=='assembly_interference' and not c['passed'] for c in report['checks']))
    def test_axis_with_no_engagement_fails(self):
        p=fixture(True);p['mates'][0]['offset']=.5
        _,report,_=self.build(p);self.assertFalse(report['declared_relations_passed'])
    def test_removed_face_is_not_a_valid_port(self):
        p=fixture();p['parts'][0]['forms'].append(operation('cylinder',[.2,.3,.2],op='subtract'))
        _,report,_=self.build(p)
        self.assertFalse(next(c['passed'] for c in report['checks'] if c['kind']=='port_geometry' and c['relation']['port']=='host_port'))
    def test_buried_face_is_not_a_valid_port(self):
        p=fixture();p['parts'][0]['forms'].append(operation('box',[.4,.1,.4],[0,.06,0]))
        _,report,_=self.build(p)
        self.assertFalse(next(c['passed'] for c in report['checks'] if c['kind']=='port_geometry' and c['relation']['port']=='host_port'))
    def test_blocked_bore_is_detected(self):
        p=fixture(True);p['parts'][0]['forms'].append(operation('box',[.2,.03,.2]))
        _,report,_=self.build(p)
        self.assertFalse(next(c['passed'] for c in report['checks'] if c['kind']=='port_geometry' and c['relation']['port']=='host_port'))
    def test_cut_bore_has_real_surface_evidence(self):
        p=fixture(True);p['parts'][0]['forms']=[operation('box',[.25,.2,.25]),operation('cylinder',[.16,.3,.16],op='subtract')]
        p['ports'][0]['form']=1;p['ports'][0]['span']=[.2,.8]
        _,report,_=self.build(p);self.assertTrue(report['declared_relations_passed'],report)
        p['ports'][0]['span']=[0,.1]
        _,report,_=self.build(p);self.assertFalse(report['declared_relations_passed'])
    def test_overconstrained_cycle_reports_failure(self):
        p=fixture();other=copy.deepcopy(p['mates'][0]);other.update(id='conflict',offset=.03);p['mates'].append(other)
        _,report,_=self.build(p)
        self.assertFalse(next(c['passed'] for c in report['checks'] if c['kind']=='executable_mate' and c['relation']['id']=='conflict'))
    def test_locked_constraints_cannot_be_weakened_or_removed(self):
        p=fixture(True);locked=assembly.freeze(p,['host','child'])
        p['mates'][0]['minimum_clearance']=0
        with self.assertRaisesRegex(ValueError,'locked'):self.build(p,locked)
        p=fixture(True);p['mates']=[]
        with self.assertRaises(ValueError):self.build(p,locked)
    def test_geometry_repair_preserves_requirements(self):
        p=fixture(True);locked=assembly.freeze(p,['host','child']);p['parts'][1]['forms'][0]['size']=[.08,.15,.08]
        _,report,_=self.build(p,locked);self.assertTrue(report['declared_relations_passed'],report)
    def test_all_pair_collision_catches_extra_protrusion(self):
        p=fixture();p['parts'][1]['forms'].append(operation('box',[.04,.2,.04],[.04,-.13,0]))
        _,report,_=self.build(p)
        self.assertTrue(any(c['kind']=='assembly_interference' and not c['passed'] for c in report['checks']))
    def test_bad_port_reference_and_nonfinite_mate_rejected(self):
        p=fixture();p['ports'][0]['form']=12
        with self.assertRaises(ValueError):self.build(p)
        p=fixture();p['mates'][0]['offset']=float('nan')
        with self.assertRaises(ValueError):self.build(p)
    def test_roundtrip_rotations(self):
        for angles in ([30,20,-40],[40,90,60],[15,-90,32],[0,0,180]):
            original=np.asarray(assembly.base.matrix(angles));actual=assembly.base.matrix(assembly._euler(original))
            np.testing.assert_allclose(actual,original,atol=1e-7)

if __name__=='__main__':unittest.main()
