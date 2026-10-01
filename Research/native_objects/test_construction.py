import copy
import math
import unittest
from Research.native_objects.construction import build,relations,validate,transform,inverse,point_triangle_distance,mesh


def form(kind='box',size=None):
    return {'kind':kind,'size':size or [.2,.2,.2],'wall':.05 if kind in ('box_shell','tube') else 0,
            'offset':[0,0,0],'rotation':[0,0,0],'sections':[]}


def fixture():
    return {'assumptions':['Synthetic contract fixture; not model intelligence.'],'limitations':['No engineering claim.'],
        'parts':[{'id':'outer','role':'A','parent':'','position':[0,0,0],'rotation':[0,0,0],'forms':[form('box_shell',[1,1,1])]},
                 {'id':'inner','role':'B','parent':'outer','position':[0,0,0],'rotation':[0,0,0],'forms':[form()]}],
        'mounts':[], 'containments':[{'outer':'outer','inner':'inner','clearance':.01}], 'clearances':[], 'symmetries':[]}


class ConstructionTests(unittest.TestCase):
    def test_containment_rejects_wall_crossing(self):
        p=fixture();self.assertTrue(relations(p,build(p,['A','B'],'test'))['declared_relations_passed'])
        p['parts'][1]['position'][0]=.4
        self.assertFalse(relations(p,build(p,['A','B'],'test'))['declared_relations_passed'])

    def test_rotated_translated_cavity(self):
        p=fixture()
        for part in p['parts']:part['position']=[1,2,3];part['rotation']=[23,41,67]
        self.assertTrue(relations(p,build(p,['A','B'],'test'))['declared_relations_passed'])

    def test_anchor_alignment_and_actual_surface(self):
        p=fixture();p['containments']=[];p['parts'][1]['position']=[0,-.35,0]
        p['mounts']=[{'a':'outer','b':'inner','point_a':[0,-.45,0],'point_b':[0,-.1,0]}]
        self.assertTrue(relations(p,build(p,['A','B'],'test'))['declared_relations_passed'])
        p['mounts'][0].update(point_a=[0,-.35,0],point_b=[0,0,0])
        self.assertFalse(relations(p,build(p,['A','B'],'test'))['declared_relations_passed'])
        p['mounts'][0].update(point_a=[0,-.45,0],point_b=[0,-.1,0]);p['parts'][1]['position'][0]=.01
        self.assertFalse(relations(p,build(p,['A','B'],'test'))['declared_relations_passed'])

    def test_nonfinite_duplicate_missing_role_cycles_and_code_rejected(self):
        for mutate in [lambda p:p['parts'][1]['position'].__setitem__(0,float('nan')),
                       lambda p:p['parts'][1].update(id='outer'),lambda p:p['parts'][1].update(role='C'),
                       lambda p:p['parts'][0].update(parent='inner'),lambda p:p.update(code='print(1)'),
                       lambda p:p['parts'][0]['forms'][0].update(wall=.6),lambda p:p.update(containments=[])]:
            p=fixture();mutate(p)
            with self.assertRaises(ValueError):validate(p,['A','B'])

    def test_symmetry_and_conservative_gap(self):
        p=fixture();p['parts'][0]['forms']=[form()]
        p['parts'][0]['position']=[-.2,0,0];p['parts'][1]['position']=[.2,0,0]
        p['containments']=[];p['mounts']=[{'a':'outer','b':'inner','point_a':[.1,0,0],'point_b':[-.1,0,0]}]
        p['symmetries']=[{'a':'outer','b':'inner','axis':'x'}];p['clearances']=[{'a':'outer','b':'inner','minimum':.2}]
        report=relations(p,build(p,['A','B'],'test'))
        self.assertFalse(report['checks'][0]['passed'])
        self.assertTrue(report['checks'][1]['passed']);self.assertTrue(report['checks'][2]['passed'])
        p['parts'][1]['position']=[.19,0,0]
        report=relations(p,build(p,['A','B'],'test'))
        self.assertFalse(report['checks'][1]['passed']);self.assertFalse(report['checks'][2]['passed'])

    def test_general_forms_bounds_and_indices(self):
        for kind in ('box','box_shell','ellipsoid','cylinder','tube','loft'):
            f=form(kind,[.4,.6,.8])
            if kind=='loft':f.update(size=[1,1,1],sections=[[0,-.3,0,.2,.4],[0,.3,0,.2,.4]])
            for resolution in (12,24):
                v,t=mesh(f,resolution)
                self.assertTrue(all(0<=i<len(v) for i in t));self.assertEqual(len(t)%3,0)
                for axis,extent in enumerate((.2,.3,.4)):
                    self.assertAlmostEqual(max(p[axis] for p in v),extent)
                    self.assertAlmostEqual(min(p[axis] for p in v),-extent)

    def test_transform_inverse_and_triangle_distance(self):
        p=[.1,.2,.3];r=[31,-27,101];offset=[1,2,3]
        for x,y in zip(p,inverse(transform(p,offset,r),offset,r)):self.assertAlmostEqual(x,y)
        self.assertAlmostEqual(point_triangle_distance([.2,.2,2],[0,0,0],[1,0,0],[0,1,0]),2)
        self.assertAlmostEqual(point_triangle_distance([2,0,0],[0,0,0],[1,0,0],[0,1,0]),1)

    def test_resolution_keeps_binding_and_frame(self):
        p=fixture();p['parts'][1]['forms']=[form('ellipsoid')]
        a,b=[build(p,['A','B'],'test',r) for r in (12,24)]
        for x,y in zip(a['parts'],b['parts']):
            for key in ('id','parent','semantic_role'):self.assertEqual(x[key],y[key])
        self.assertNotEqual(len(a['parts'][1]['vertices']),len(b['parts'][1]['vertices']))
        self.assertTrue(relations(p,b)['declared_relations_passed'])


if __name__=='__main__':unittest.main()
