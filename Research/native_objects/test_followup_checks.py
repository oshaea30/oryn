from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from Research.native_objects import assembly_arrangements as arrangements
from Research.native_objects import compact_requirements as codec
from Research.native_objects import repair_feedback as repair
from Research.native_objects import requirements_experiment as pipeline
from Research.native_objects.test_assembly_arrangements import raw_inventory,contract as array_contract,proposal,bindings as array_bindings
from Research.native_objects.test_spatial_requirements import contract,bindings
from Research.native_objects.test_assembly_connections import fixture
from Research.native_objects.test_construction_solid import operation

ROOT=Path(__file__).parent


class CompactRequirementsTests(unittest.TestCase):
    def test_saved_outputs_restore_exactly_without_mutation(self):
        for case in ('cooling-fan-row','two-driver-speaker'):
            raw=json.loads((ROOT/'results/assembly-010'/f'{case}-extract/inventory.json').read_text());original=deepcopy(raw)
            compact=codec.encode(raw);self.assertEqual(codec.decode(compact),raw);self.assertEqual(raw,original)
            self.assertLess(len(json.dumps(compact)),len(json.dumps(raw))*.7)
            spec=next(c for c in json.loads((ROOT/'arrangement_cases_010.json').read_text()) if c['id']==case)
            self.assertEqual(arrangements.validate(raw,spec['request'],spec['roles']),arrangements.validate(codec.decode(compact),spec['request'],spec['roles']))

    def test_all_columns_including_obligations_are_lossless(self):
        raw=raw_inventory()
        for i,obligation in enumerate(('optional','design_choice','evidence_required')):
            raw['requirements'].append(dict(raw['requirements'][0],id='extra'+str(i),obligation=obligation,
                basis='design_choice' if obligation=='design_choice' else 'explicit',source='' if obligation=='design_choice' else 's0',
                kind='constraint',subject='object',predicate='other',value='a retained qualifier',mode='physical_verification' if obligation=='evidence_required' else 'structure'))
        raw['exclusions']=[{'id':'exclude','subject':'object','domain':'motion','source':'s0'}]
        self.assertEqual(codec.decode(codec.encode(raw)),raw)

    def test_48_record_capacity_and_49_rejection(self):
        raw=raw_inventory();first=raw['requirements'][0]
        while len(raw['requirements'])<48:raw['requirements'].append(dict(first,id='req'+str(len(raw['requirements'])),kind='visual',predicate='appearance',value='detail',mode='appearance'))
        decoded=codec.decode(codec.encode(raw));arrangements.validate(decoded,'A synthetic repeated assembly.',['holder','members'])
        raw['requirements'].append(dict(first,id='overflow'))
        with self.assertRaises(ValueError):codec.encode(raw)
        with self.assertRaises(ValueError):arrangements.validate(raw,'A synthetic repeated assembly.',['holder','members'])

    def test_bad_width_type_and_unknown_fields_rejected(self):
        compact=codec.encode(raw_inventory())
        for row in (compact['requirements'][0][:-1],compact['requirements'][0]+['extra'],[None]*10,{},'not a row'):
            bad=deepcopy(compact);bad['requirements'][0]=row
            with self.assertRaises(ValueError):codec.decode(bad)
        with self.assertRaises(ValueError):codec.decode({**compact,'extra':[]})

    def test_transport_does_not_authorize_invalid_semantics(self):
        for field,value in (('subject','invented'),('mode','magic'),('source','absent'),('obligation','unsupported')):
            raw=raw_inventory();raw['requirements'][0][field]=value
            with self.assertRaises(ValueError):arrangements.validate(codec.decode(codec.encode(raw)),'A synthetic repeated assembly.',['holder','members'])


class SurfaceTests(unittest.TestCase):
    def measure(self,p,side='+z',mutate=None):
        c=contract(['host','child'],'on_surface',axis=side);b=bindings(c,p,['mate:connection'])
        self.assertTrue(pipeline.spatial.coverage(c,p,b)['geometry_allowed'])
        _,report,compiled=pipeline.geometry.build(p,['host','child'],'surface',pipeline.geometry.freeze(p,['host','child']))
        if mutate:mutate(compiled)
        return pipeline.spatial.measurements(c,p,b,compiled)[0],report

    def proposal(self,side):
        p=fixture();p['ports'][0]['face']=side;p['ports'][1]['face']=('-' if side[0]=='+' else '+')+side[1]
        return p

    def test_all_sides_with_rotated_root_and_reversed_mate(self):
        for side in ('+x','-x','+y','-y','+z','-z'):
            p=self.proposal(side);p['parts'][0].update(position=[.2,-.1,.3],rotation=[20,40,30])
            p['mates'][0]['a'],p['mates'][0]['b']=p['mates'][0]['b'],p['mates'][0]['a']
            check,report=self.measure(p,side)
            self.assertTrue(report['declared_relations_passed']);self.assertTrue(check['passed'],check)

    def test_wrong_side_and_gap_fail(self):
        self.assertFalse(self.measure(self.proposal('-z'))[0]['passed'])
        p=self.proposal('+z');p['mates'][0]['offset']=.005
        self.assertFalse(self.measure(p)[0]['passed'])

    def test_buried_and_inset_contact_cannot_prove_exterior(self):
        p=self.proposal('+z');p['parts'][0]['forms'].append(operation('box',[.4,.1,.1],[0,0,.2]))
        self.assertFalse(self.measure(p)[0]['passed'])
        p=self.proposal('+z');p['parts'][0]['forms'].append(operation('box',[.04,.1,.1],[.18,0,.2]))
        check,report=self.measure(p)
        self.assertTrue(next(c['passed'] for c in report['checks'] if c['kind']=='port_geometry' and c['relation']['port']=='host_port'))
        self.assertFalse(check['passed']);self.assertGreater(check['measurement']['pairs'][0]['surface_extent_error_m'],.0005)

    def test_wrong_mate_or_missing_subject_fails_coverage(self):
        c=contract(['host','child'],'on_surface',axis='+z');p=fixture(True)
        self.assertFalse(pipeline.spatial.coverage(c,p,bindings(c,p,['mate:connection']))['geometry_allowed'])
        p=self.proposal('+z');extra=deepcopy(p['parts'][1]);extra['id']='unbound_child';p['parts'].append(extra)
        self.assertFalse(pipeline.spatial.coverage(c,p,bindings(c,p,['mate:connection']))['geometry_allowed'])

    def test_schema_and_validation_require_signed_axis(self):
        for axis in ('','z','front'):
            with self.assertRaises(ValueError):contract(['host','child'],'on_surface',axis=axis)
        variants=pipeline.spatial.schema('An object.',['host','child'])['properties']['spatial']['items']['anyOf']
        self.assertTrue(any(b['properties']['operator']['enum']==['on_surface'] and '+z' in b['properties']['axis']['enum'] for b in variants))


class RepairFeedbackTests(unittest.TestCase):
    def saved_report(self,attempt):
        path=ROOT/'results/assembly-010'
        report=json.loads((path/f'cooling-fan-row-plan-{attempt}/relations.json').read_text())
        report['checks']=[c for c in report['checks'] if c['kind']!='assembly_arrangement']+json.loads((path/f'diagnostic-replay/cooling-fan-row-plan-{attempt}/arrangement-checks.json').read_text())
        return report

    def test_real_failed_fan_repair_regressions_are_named(self):
        baseline=self.saved_report(0);snapshot=repair.snapshot(baseline);bad=self.saved_report(1)
        self.assertTrue(repair.regressions(snapshot,baseline)['passed'])
        result=repair.regressions(snapshot,bad);self.assertFalse(result['passed'])
        ids=[r['identity'] for r in result['regressions']]
        self.assertEqual(sum(v['kind']=='connected_component' for v in ids),3)
        self.assertEqual(sum(v['kind']=='executable_mate' for v in ids),3)
        self.assertEqual(sum(v.get('facet')=='member_relation' and v.get('aspect')=='orientation' for v in ids),6)
        feedback=repair.feedback(baseline,snapshot)
        self.assertTrue(any(v.get('facet')=='member_relation' and v['aspect']=='orientation' for v in feedback['preserve']['facts']))

    def test_removed_check_fails_and_baseline_is_hash_locked(self):
        report=self.saved_report(0);snapshot=repair.snapshot(report)
        changed=deepcopy(report);changed['checks']=[c for c in changed['checks'] if c['kind']!='connected_component']
        result=repair.regressions(snapshot,changed)
        self.assertTrue(any(v['reason']=='measurement_missing' for v in result['regressions']))
        snapshot['passed_facts'].pop()
        with self.assertRaises(ValueError):repair.regressions(snapshot,report)

    def test_equal_numbers_do_not_regress_or_mutate_reports(self):
        report={'checks':[{'kind':'mate','relation':{'id':'join','offset':0},'passed':True}]};original=deepcopy(report);snapshot=repair.snapshot(report)
        altered=deepcopy(report);altered['checks'][0]['relation']['offset']=0.0
        self.assertTrue(repair.regressions(snapshot,altered)['passed']);self.assertEqual(report,original)

    def test_real_pipeline_accepts_changed_geometry_preserving_predicates(self):
        c=array_contract();p=proposal();raw=pipeline.compact.pack(p,c,array_bindings(c,p))
        with tempfile.TemporaryDirectory() as temp:
            initial=Path(temp)/'initial';initial.mkdir()
            result,locked=pipeline.evaluate_candidate(raw,c,initial,'synthetic',renderer=lambda _:None,preserve_passes=True)
            self.assertEqual(result['status'],'structural_candidate')
            baseline=json.loads((initial/'repair-baseline.json').read_text())
            p['parts'][1]['forms'][0]['size'][1]=.13
            updated=pipeline.compact.pack(p,c,array_bindings(c,p));folder=Path(temp)/'repair';folder.mkdir()
            result,_=pipeline.evaluate_candidate(updated,c,folder,'synthetic',locked,renderer=lambda _:None,preservation=baseline,preserve_passes=True)
            self.assertEqual(result['status'],'structural_candidate');self.assertTrue(result['repair_preservation']['passed'])

    def test_missing_prior_measurement_blocks_even_if_remaining_pass(self):
        c=array_contract();p=proposal();raw=pipeline.compact.pack(p,c,array_bindings(c,p))
        with tempfile.TemporaryDirectory() as temp:
            initial=Path(temp)/'initial';initial.mkdir()
            _,locked=pipeline.evaluate_candidate(raw,c,initial,'synthetic',renderer=lambda _:None,preserve_passes=True)
            baseline=json.loads((initial/'repair-baseline.json').read_text())
            def builder(*args):
                pkg,report,compiled=pipeline.geometry.build(*args)
                report['checks']=[v for v in report['checks'] if v['kind']!='connected_component']
                return pkg,report,compiled
            folder=Path(temp)/'repair';folder.mkdir()
            result,_=pipeline.evaluate_candidate(raw,c,folder,'synthetic',locked,builder=builder,renderer=lambda _:None,preservation=baseline,preserve_passes=True)
            self.assertEqual(result['status'],'geometry_failed');self.assertFalse(result['repair_preservation']['passed'])
            self.assertFalse(json.loads((folder/'report.json').read_text())['structural_checks_passed'])

if __name__=='__main__':unittest.main()
