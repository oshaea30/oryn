import json
from pathlib import Path
import unittest
from Research.native_objects.cube_bridge import prepare,digest_bytes

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.raw=(Path(__file__).parent/'results/planning-001.json').read_bytes()
        self.source=json.loads(self.raw);self.result=prepare(self.source,digest_bytes(self.raw))
    def test_exact_and_over_capacity_are_blocked_without_surgery(self):
        cases={c['case_id']:c for c in self.result['cases']}
        self.assertEqual(cases['exact-product']['status'],'blocked_evidence')
        self.assertEqual(cases['generic-speaker']['status'],'unsupported_part_count')
        self.assertEqual(len(cases['generic-speaker']['part_names']),9)
    def test_names_and_global_concept_are_preserved(self):
        for source,case in zip(self.source['items'],self.result['cases']):
            self.assertEqual(case['part_names'],[c['name'] for c in source['candidate']['plan']['components']])
            self.assertEqual(case['whole_shape_prompt'],source['candidate']['plan']['object'])
            self.assertFalse(case['production_generation_allowed'])
    def test_two_different_objects_are_eligible(self):
        self.assertEqual([c['case_id'] for c in self.result['cases'] if c['status']=='eligible_research_only'],['generic-drone','creative-concept'])
    def test_eligibility_does_not_override_retrieval(self):
        self.source['items'][0]['candidate']['plan']['retrieval']='general_references'
        self.assertEqual(prepare(self.source,'test')['cases'][0]['status'],'blocked_evidence')
    def test_budget_and_no_retry(self):
        self.assertLessEqual(self.result['budget']['max_gpu_usd_hour']*self.result['budget']['max_hours']+100*.1/720*2,3.5)
        self.assertEqual(self.result['policy']['retries'],0)
if __name__=='__main__':unittest.main()
