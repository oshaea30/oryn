from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from Research.native_objects.experiment import base,evaluate,rotate,from_partcrafter,glb_mesh,sha
from Research.native_objects.run_partcrafter import plan,COMMIT


def fixture():
    p=base('test',{'kind':'synthetic_unit_test'},'metres')
    p['origins']={f:'authored' for f in p['origins']}
    p['parts']=[{'id':'rotor','vertices':[[1,0,0],[1,1,0],[2,0,0]],'triangles':[0,1,2],
        'parent':None,'motion':{'kind':'rotation','axis':[0,0,1],'pivot':[0,0,0],'ratio':1,'phase_degrees':0,'driver':None}}]
    p['frames']=[{'cycle':.25,'parts':{'rotor':[[0,1,0],[-1,1,0],[0,2,0]]}}]
    return p


class EvaluationTests(unittest.TestCase):
    def test_independent_quarter_turn_matches_real_geometry(self):
        r=evaluate(fixture());self.assertTrue(r['structural_checks_passed'])
        self.assertEqual(r['checks']['runtime_motion_agreement']['status'],'pass')
        self.assertFalse(r['native_generation_goal_passed'])
    def test_missing_or_degenerate_geometry_fails(self):
        for verts,tris in [([],[]),([[0,0,0]],[0,0,0]),([[0,0,0],[1,0,0],[2,0,0]],[0,1,2]),([[float('nan'),0,0]],[0,0,0])]:
            p=fixture();p['parts'][0].update(vertices=verts,triangles=tris)
            self.assertEqual(evaluate(p)['checks']['usable_geometry']['status'],'fail')
    def test_out_of_bounds_index_fails(self):
        p=fixture();p['parts'][0]['triangles']=[0,1,4]
        self.assertFalse(evaluate(p)['structural_checks_passed'])
    def test_duplicate_bindings_fail(self):
        p=fixture();p['parts'].append(deepcopy(p['parts'][0]))
        self.assertFalse(evaluate(p)['structural_checks_passed'])
    def test_cycles_and_missing_references_fail(self):
        for field in ['parent','driver']:
            for target in ['rotor','absent']:
                p=fixture();(p['parts'][0]['motion'] if field=='driver' else p['parts'][0])[field]=target
                self.assertFalse(evaluate(p)['structural_checks_passed'])
    def test_bad_axis_or_pivot_fails(self):
        for field,value in [('axis',[0,0,0]),('axis',[0,0,2]),('pivot',[float('inf'),0,0])]:
            p=fixture();p['parts'][0]['motion'][field]=value
            self.assertFalse(evaluate(p)['structural_checks_passed'])
    def test_valid_but_wrong_axis_fails_against_runtime_motion(self):
        p=fixture();p['parts'][0]['motion']['axis']=[0,1,0]
        self.assertEqual(evaluate(p)['checks']['runtime_motion_agreement']['status'],'fail')
    def test_missing_runtime_component_is_not_ignored(self):
        p=fixture();p['frames'][0]['parts']={}
        self.assertFalse(evaluate(p)['structural_checks_passed'])
    def test_motion_missing_does_not_become_fixed_or_pass(self):
        p=fixture();p['parts'][0]['motion']=None;p['frames']=[];p['origins']['motion']='unknown'
        r=evaluate(p)
        self.assertEqual(r['checks']['motion_parameters']['status'],'missing')
        self.assertEqual(r['checks']['runtime_motion_agreement']['status'],'not_assessed')
        self.assertIn('motion',r['missing_output_facets'])
        self.assertFalse(r['native_generation_goal_passed'])
    def test_geometry_never_proves_semantics_or_visual_quality(self):
        r=evaluate(fixture())
        for name in ['semantic_correctness','visual_quality','attachment_fit','motion_clearance','physical_validity','quest_performance']:
            self.assertEqual(r['checks'][name]['status'],'not_assessed')
    def test_manual_repairs_remain_visible(self):
        p=fixture();p['manual_repairs']=[{'action':'moved pivot'}]
        self.assertEqual(evaluate(p)['manual_repair_count'],1)
        self.assertFalse(evaluate(p)['native_generation_goal_passed'])
    def test_evaluation_never_mutates_input(self):
        p=fixture();original=deepcopy(p);evaluate(p);self.assertEqual(p,original)
    def test_runner_plan_has_no_paid_services_or_implicit_part_selection(self):
        with tempfile.TemporaryDirectory() as d:
            image=Path(d)/'input.png';image.write_bytes(b'fixture')
            r=plan(Path(d),image,Path(d)/'output',13,4)
            self.assertEqual(r['revision'],COMMIT);self.assertEqual(r['seed'],4)
            self.assertEqual(r['supplied'],['reference image','part count'])
            self.assertNotIn('--part_suggest',r['command']);self.assertNotIn('--style_transfer',r['command'])
            with self.assertRaises(ValueError):plan(Path(d),image,Path(d)/'output',17,0)
    def test_generated_parts_import_without_inventing_relationships(self):
        from test_mesh_islands import fixture as glb_fixture
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'output').mkdir();path=root/'output/part_00.glb'
            path.write_bytes(glb_fixture(change=lambda doc:doc['nodes'][0].pop('translation')))
            run={'status':'completed','id':'test','num_parts':1,'outputs':{'part_00.glb':sha(path)}}
            (root/'run.json').write_text(json.dumps(run));p=from_partcrafter(root)
            self.assertEqual(p['origins']['geometry'],'model_generated')
            self.assertIsNone(p['parts'][0]['motion']);self.assertIsNone(p['parts'][0]['semantic_role'])
            self.assertEqual(len(p['parts'][0]['triangles']),6)
            path.write_bytes(path.read_bytes()+b'changed')
            with self.assertRaises(ValueError):from_partcrafter(root)

    def test_transformed_generated_part_is_not_silently_misplaced(self):
        from test_mesh_islands import fixture as glb_fixture
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'part.glb';path.write_bytes(glb_fixture())
            with self.assertRaises(ValueError):glb_mesh(path)

    def test_failed_inference_cannot_be_imported(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'run.json').write_text(json.dumps({'status':'failed'}))
            with self.assertRaises(ValueError):from_partcrafter(d)

if __name__=='__main__':unittest.main()
