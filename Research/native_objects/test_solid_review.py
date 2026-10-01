import unittest
from Research.native_objects.solid_experiment import validate_review,operation_id,SCORES

class ReviewTests(unittest.TestCase):
    def review(self):return {'decision':'pass','scores':{k:2 for k in SCORES},'issues':[],'summary':'Synthetic checker fixture only.'}
    def test_no_pass_when_numeric_checks_fail(self):
        with self.assertRaises(ValueError):validate_review(self.review(),{'a'},False)
    def test_no_pass_with_partial_score_or_blocker(self):
        r=self.review();r['scores']['interfaces']=1
        with self.assertRaises(ValueError):validate_review(r,{'a'},True)
        r=self.review();r['issues']=[{'part_ids':['a'],'observation':'Missing connection','severity':'blocking'}]
        with self.assertRaises(ValueError):validate_review(r,{'a'},True)
    def test_invented_id_and_invalid_score_rejected(self):
        r=self.review();r['decision']='revise';r['issues']=[{'part_ids':['invented'],'observation':'Claim','severity':'blocking'}]
        with self.assertRaises(ValueError):validate_review(r,{'a'},True)
        r=self.review();r['scores']['concept']=True
        with self.assertRaises(ValueError):validate_review(r,{'a'},True)
    def test_feedback_is_candidate_not_verified_result(self):
        r=self.review();r['decision']='unassessable';r['scores']['interfaces']=0
        self.assertEqual(validate_review(r,{'a'},False)['decision'],'unassessable')
    def test_operation_identity_is_stable_and_stage_bound(self):
        self.assertEqual(operation_id('generic-drone',0,'construct'),operation_id('generic-drone',0,'construct'))
        self.assertNotEqual(operation_id('generic-drone',0,'construct'),operation_id('generic-drone',1,'construct'))
        self.assertNotEqual(operation_id('generic-drone',0,'construct'),operation_id('generic-drone',0,'review'))
if __name__=='__main__':unittest.main()
