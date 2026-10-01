from copy import deepcopy
import json
import unittest
from Research.native_objects import compact_construction as compact
from Research.native_objects.test_intent_requirements import inventory


class PlannerContextTests(unittest.TestCase):
    def test_exact_quotes_and_locked_requirements_round_trip_without_mutation(self):
        contract=inventory();context={'original_request':contract['source_request'],
            'requirements':contract['inventory'],'requirement_hash':contract['inventory_sha256'],
            'locked_assembly':json.dumps({'parts':[['host','host','']], 'mates':[]},indent=2),
            'spatial_rules':[{'id':'inside','operator':'on_top','reference':'','axis':''}]}
        before=deepcopy(context);packed=compact.planner_context(context);restored=compact.restore_planner_context(packed)
        self.assertEqual(restored['requirements'],context['requirements']);self.assertEqual(packed['spatial_rules'],context['spatial_rules'])
        self.assertEqual(restored['locked_assembly'],json.loads(context['locked_assembly']))
        self.assertEqual(len(packed['source_quotes']),1);self.assertEqual(context,before)
        self.assertEqual(compact.intent.digest(restored['requirements']),context['requirement_hash'])

    def test_corrupted_hash_or_quote_reference_is_rejected(self):
        c=inventory();context={'requirements':c['inventory'],'requirement_hash':'changed'}
        with self.assertRaises(ValueError):compact.planner_context(context)
        context['requirement_hash']=c['inventory_sha256'];packed=compact.planner_context(context)
        packed['requirements']['requirements'][0]['quote_ref']=99
        with self.assertRaises(ValueError):compact.restore_planner_context(packed)

    def test_exclusions_and_empty_design_quotes_remain_distinct(self):
        c=inventory();raw=c['inventory'];raw['requirements'][0].update(quote='',obligation='design_choice')
        raw['exclusions']=[{'id':'x','subject':'object','domain':'motion','quote':'Keep it static — exactly.'}]
        context={'requirements':raw,'requirement_hash':compact.intent.digest(raw)}
        packed=compact.planner_context(context)
        self.assertEqual(compact.restore_planner_context(packed),context)
        self.assertIn('',packed['source_quotes']);self.assertIn('Keep it static — exactly.',packed['source_quotes'])

    def test_saved_repair_payload_round_trips_and_becomes_smaller(self):
        from pathlib import Path
        p=Path('Builds/NativeObjects/spatial-run-009/generic-drone-plan-1/request.json')
        if not p.exists():self.skipTest('Local live repair request unavailable')
        context=json.loads(json.loads(p.read_text())['body']['input'][1]['content']);packed=compact.planner_context(context)
        original=deepcopy(context);original['locked_assembly']=json.loads(original['locked_assembly'])
        self.assertEqual(compact.restore_planner_context(packed),original)
        self.assertLess(len(json.dumps(packed)),len(json.dumps(context))*.85)
