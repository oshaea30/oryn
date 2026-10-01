from copy import deepcopy
import json
from pathlib import Path
import unittest
from Research.native_objects import feedback_transport as codec
from Research.native_objects import repair_experiment as e

class FeedbackTransportTests(unittest.TestCase):
    def test_all_saved_fan_facts_and_failures_round_trip(self):
        source=e.previous.prepare_replay();value={'failed_geometry_checks':[{'kind':'example','passed':False}],'preserve':{'baseline_sha256':source['preservation']['sha256'],'facts':source['preservation']['passed_facts']}}
        packed=codec.encode(value)
        self.assertEqual(codec.decode(packed),value)
        self.assertEqual(codec.audit(value,packed)['fact_count'],55)
        self.assertEqual(packed['failed_geometry_checks'],value['failed_geometry_checks'])
    def test_mixed_nested_records_keep_order_and_scalar_types(self):
        facts=[{'kind':'a','relation':{'a':'one','b':'two','offset':0.0}}, {'kind':'a','relation':{'a':'three','b':'four','offset':1}}, {'kind':'b','passed':True}, {'kind':'a','relation':{'part':'last'}}]
        value={'preserve':{'facts':facts},'other':[1,2,3]};snapshot=deepcopy(value)
        self.assertEqual(codec.decode(codec.encode(value)),value);self.assertEqual(value,snapshot)
        self.assertEqual(len(codec.encode(value)['preserve']['fact_tables']),3)
    def test_invalid_columns_rows_and_changed_fact_rejected(self):
        value={'preserve':{'facts':[{'kind':'a','relation':{'a':'x','b':'y'}}]}};packed=codec.encode(value)
        for change in ('duplicate','missing','conflict'):
            bad=deepcopy(packed);table=bad['preserve']['fact_tables'][0]
            if change=='duplicate':table['columns']=['relation.a','relation.a']
            elif change=='missing':table['rows'][0].pop()
            else:table['columns']=['relation','relation.a']
            with self.assertRaises(ValueError):codec.decode(bad)
        bad=deepcopy(packed);bad['preserve']['fact_tables'][0]['rows'][0][1]='different'
        with self.assertRaises(ValueError):codec.audit(value,bad)
    def test_empty_facts_remain_empty(self):
        value={'preserve':{'facts':[]}};self.assertEqual(codec.decode(codec.encode(value)),value)

if __name__=='__main__':unittest.main()
