from copy import deepcopy
import json
from pathlib import Path
import unittest
from Research.native_objects import typed_requirements as codec
from Research.native_objects.test_assembly_arrangements import raw_inventory

class TypedRequirementsTests(unittest.TestCase):
    def test_every_schema_constraint_survives_key_renaming(self):
        request='Show me a static object.';roles=['Center','Members']
        original=codec.rows.arrangements.schema(request,roles);short=codec.schema(request,roles)
        for a,b in zip(original['properties']['requirements']['items']['anyOf'],short['properties']['requirements']['items']['anyOf']):
            for key,value in a['properties'].items():self.assertEqual(b['properties'][codec.REQUIREMENT_KEYS[key]],value)
            self.assertEqual(a['additionalProperties'],b['additionalProperties'])
            self.assertEqual({codec.REQUIREMENT_KEYS[x] for x in a['required']},set(b['required']))
        source=original['properties']['exclusions']['items'];target=short['properties']['exclusions']['items']
        for key,value in source['properties'].items():self.assertEqual(target['properties'][codec.EXCLUSION_KEYS[key]],value)
        self.assertIn('motion',target['properties']['d']['enum']);self.assertNotIn('animate',target['properties']['d']['enum'])
        self.assertEqual(short['properties']['spatial'],original['properties']['spatial'])
        self.assertEqual(short['properties']['assemblies'],original['properties']['assemblies'])

    def test_saved_valid_inventories_roundtrip_and_shrink_without_mutation(self):
        for case in ('cooling-fan-row','two-driver-speaker'):
            raw=json.loads((Path(__file__).parent/'results/assembly-010'/f'{case}-extract/inventory.json').read_text());original=deepcopy(raw)
            short=codec.encode(raw)
            self.assertEqual(codec.decode(short),raw);self.assertEqual(raw,original)
            self.assertLess(len(json.dumps(short)),len(json.dumps(raw)))

    def test_unknown_missing_extra_or_nonstring_fields_fail(self):
        short=codec.encode(raw_inventory())
        for replacement in ({},list(short['requirements'][0].values()),dict(short['requirements'][0],i=3),dict(short['requirements'][0],extra='')):
            bad=deepcopy(short);bad['requirements'][0]=replacement
            with self.assertRaises(ValueError):codec.decode(bad)

    def test_invalid_value_is_not_normalized_into_a_valid_record(self):
        raw=raw_inventory();raw['exclusions']=[{'id':'ex','subject':'object','domain':'animate','source':'s0'}]
        restored=codec.decode(codec.encode(raw));self.assertEqual(restored,raw)
        with self.assertRaisesRegex(ValueError,'exclusion identity'):codec.rows.arrangements.validate(restored,'A synthetic repeated assembly.',['holder','members'])

if __name__=='__main__':unittest.main()
