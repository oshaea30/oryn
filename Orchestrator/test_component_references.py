import io
import unittest
from unittest.mock import Mock
from component_references import ComponentReferences, Paragraphs


class ReferenceTests(unittest.TestCase):
    def test_extracts_visible_paragraphs_not_scripts(self):
        p=Paragraphs();p.feed('<p>Valve <b>cover</b> clearance <script>secret</script></p><li>V8 engines</li>')
        self.assertEqual(p.rows,['Valve cover clearance','V8 engines'])

    def test_fixed_reference_cached_without_claiming_exact_match(self):
        opener=Mock();opener.open.side_effect=lambda *a,**k:io.BytesIO(b'<p>Valve cover and valvetrain clearance.</p>')
        provider=ComponentReferences(opener,Mock())
        first=provider.retrieve('V8 engine cover');second=provider.retrieve('engine cover')
        self.assertEqual(first,second);opener.open.assert_called_once()
        self.assertEqual(opener.open.call_args.args[0].full_url,ComponentReferences.URL)
        self.assertIsNone(first[0]['object_match']);self.assertIsNone(first[0]['revision_match'])

    def test_other_queries_use_injected_search(self):
        fallback=Mock();p=ComponentReferences(Mock(),fallback)
        p.retrieve('drone propeller');fallback.retrieve.assert_called_once_with('drone propeller')

    def test_empty_or_oversized_reference_rejected(self):
        for body in (b'<p>No component information</p>',b'x'*524289):
            opener=Mock();opener.open.side_effect=lambda *a,body=body,**k:io.BytesIO(body)
            with self.assertRaises(ValueError):ComponentReferences(opener,Mock()).retrieve('engine cover')
