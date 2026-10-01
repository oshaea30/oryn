import copy
import unittest
from Research.native_objects import construction_solid as solid
from Research.native_objects.test_construction import fixture,form


def proposal():
    p=fixture();p['passages']=[]
    for part in p['parts']:
        part['color']=[.4,.5,.6]
        for f in part['forms']:f.update(operation='add',radius=0,repeat=[1,1,1],step=[0,0,0])
    return p


def operation(kind,size,offset=None,op='add'):
    f=form(kind,size);f.update(offset=offset or [0,0,0],operation=op,radius=0,repeat=[1,1,1],step=[0,0,0]);return f


class SolidTests(unittest.TestCase):
    def test_cut_required_for_passage(self):
        p=proposal();p['passages']=[{'part':'outer','start':[0,-.6,0],'end':[0,-.4,0],'radius':.03,'purpose':'Synthetic through-wall test'}]
        pkg,report=solid.build(p,['A','B'],'fixture')
        self.assertFalse(next(c for c in report['checks'] if c['kind']=='passage')['passed'])
        p['parts'][0]['forms'].append(operation('cylinder',[.08,.3,.08],[0,-.5,0],'subtract'))
        _,report=solid.build(p,['A','B'],'fixture')
        self.assertTrue(next(c for c in report['checks'] if c['kind']=='passage')['passed'])

    def test_probe_in_empty_air_is_not_evidence(self):
        p=proposal();p['passages']=[{'part':'outer','start':[2,0,0],'end':[2,1,0],'radius':.03,'purpose':'Irrelevant air'}]
        _,report=solid.build(p,['A','B'],'fixture')
        self.assertFalse(next(c for c in report['checks'] if c['kind']=='passage')['passed'])

    def test_true_containment_rejects_solid_host_and_intersection(self):
        p=proposal();_,report=solid.build(p,['A','B'],'fixture');self.assertTrue(report['declared_relations_passed'])
        p['parts'][0]['forms'][0]['kind']='box';p['parts'][0]['forms'][0]['wall']=0
        _,report=solid.build(p,['A','B'],'fixture');self.assertFalse(report['declared_relations_passed'])

    def test_disconnected_islands_detected(self):
        p=proposal();p['parts'][1]['forms'].append(operation('box',[.05,.05,.05],[.25,0,0]))
        _,report=solid.build(p,['A','B'],'fixture')
        self.assertFalse(next(c for c in report['checks'] if c['kind']=='connected_component' and c['relation']['part']=='inner')['passed'])

    def test_excessive_repetition_and_invalid_color_rejected(self):
        p=proposal();p['parts'][0]['forms'][0]['repeat']=[16,16,16]
        with self.assertRaises(ValueError):solid.validate(p,['A','B'])
        p=proposal();p['parts'][0]['color'][0]=float('nan')
        with self.assertRaises(ValueError):solid.validate(p,['A','B'])

    def test_loft_is_closed_and_positive_volume(self):
        f=operation('loft',[1,1,1]);f['sections']=[[0,0,0,.1,.2],[.03,.2,0,.06,.13]]
        obj=solid.primitive(f,24)
        self.assertEqual(obj.status(),solid.md.Error.NoError);self.assertGreater(obj.volume(),0)
        self.assertEqual(len(obj.decompose()),1)

    def test_subtraction_preserves_bounds_and_reduces_volume(self):
        p=proposal();before=solid.solids(p,['A','B'])['outer']
        p['parts'][0]['forms'].append(operation('cylinder',[.08,.3,.08],[0,-.5,0],'subtract'))
        after=solid.solids(p,['A','B'])['outer'];self.assertLess(after.volume(),before.volume())
        self.assertEqual(after.bounding_box(),before.bounding_box())

if __name__=='__main__':unittest.main()
