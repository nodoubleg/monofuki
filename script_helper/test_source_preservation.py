#!/usr/bin/env python3
"""Regression checks for upstream preservation and refusing ambiguous overlays."""
import re
import unittest
import tempfile
from pathlib import Path
from glyph_overrides import apply_overrides, digest
from assemble_sources import check_preservation, check_references, records, renamed, restore_arrows
from fetch_build_dependencies import fetch, MANIFEST


class PreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fetch('upstream-Regular').read_text()
        cls.renamed = renamed(cls.base, 'Regular')
        cls.base_count = len(records(cls.base))

    def test_name_only_change_preserves_every_record(self):
        self.assertEqual(check_preservation(self.base, self.renamed, 'Regular'), self.base_count)

    def test_changed_inherited_advance_is_rejected(self):
        first = next(iter(records(self.renamed).values()))
        changed = first.replace('Width: 575', 'Width: 576')
        self.assertNotEqual(changed, first)
        with self.assertRaisesRegex(ValueError, 'inherited glyph changed'):
            check_preservation(self.base, self.renamed.replace(first, changed, 1), 'Regular')

    def test_changed_source_line_metric_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'line metric'):
            check_preservation(self.base, self.renamed.replace('HheadAscent: 910', 'HheadAscent: 911'), 'Regular')

    def test_dangling_reference_is_rejected(self):
        altered, count = re.subn(r'^Refer: \d+ ', 'Refer: 999999 ', self.base, count=1, flags=re.M)
        self.assertEqual(count, 1)
        with self.assertRaisesRegex(ValueError, 'reference'):
            check_references(altered)

    def test_arrow_collision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'now exists upstream'):
            restore_arrows(self.base, self.base, [0x21E8])


    def authored(self, root, name, record, base_record=None, dependencies=None):
        path = root / 'src/overrides/Regular' / (name + '.glyph')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record)
        from assemble_sources import encoding
        cp = encoding(record)[1]
        return {'style': 'Regular', 'glyph_name': name, 'codepoint': f'{cp:04X}' if cp >= 0 else None,
                'operation': 'replace' if base_record else 'add', 'source': str(path.relative_to(root)),
                'source_sha256': digest(record), 'expected_upstream_revision': MANIFEST['upstream']['revision'],
                'expected_base_sha256': digest(base_record) if base_record else None,
                'dependencies': dependencies or []}

    def apply(self, root, entries, revision=None):
        return apply_overrides(self.renamed, 'Regular', entries,
                               revision or MANIFEST['upstream']['revision'], root)

    def test_guarded_replacement_preserves_other_glyphs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = records(self.base)['A']
            changed = old.replace('Width: 575', 'Width: 576')
            entry = self.authored(root, 'A', changed, old)
            result, overrides, provenance = self.apply(root, [entry])
            self.assertEqual(check_preservation(self.base, result, 'Regular', overrides), self.base_count - 1)
            self.assertEqual(provenance['A']['expected_base_sha256'], digest(old))
            self.assertIn('Width: 576', records(result)['A'])
            with self.assertRaisesRegex(ValueError, 'inherited glyph changed'):
                check_preservation(self.base, result, 'Regular')

    def test_revision_base_and_source_drift_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = records(self.base)['A']
            entry = self.authored(root, 'A', old, old)
            with self.assertRaisesRegex(ValueError, 'revision drift'):
                self.apply(root, [entry], '0' * 40)
            entry['expected_base_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'base glyph drift'):
                self.apply(root, [entry])
            entry['expected_base_sha256'] = digest(old)
            (root / entry['source']).write_text(old.replace('Width: 575', 'Width: 576'))
            with self.assertRaisesRegex(ValueError, 'source fingerprint'):
                self.apply(root, [entry])

    def test_unencoded_component_and_symbolic_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            component = 'StartChar: custom.component\nEncoding: -1 -1 9000\nWidth: 575\nEndChar\n'
            old = records(self.base)['A']
            changed = old.replace('EndChar\n', 'Refer: 9000 -1 N 1 0 0 1 0 0 2\nEndChar\n')
            a = self.authored(root, 'A', changed, old, [{'source_gid': 9000, 'glyph_name': 'custom.component', 'expected_source_sha256': digest(component)}])
            c = self.authored(root, 'custom.component', component)
            result, overrides, _ = self.apply(root, [a, c])
            check_preservation(self.base, result, 'Regular', overrides)
            self.assertEqual(self.apply(root, [c, a])[0], result)
            self.assertEqual(len(records(result)), self.base_count + 1)
            import fontforge
            assembled = root / 'probe.sfd'
            assembled.write_text(result)
            font = fontforge.open(str(assembled))
            try:
                self.assertEqual(font['custom.component'].unicode, -1)
                self.assertEqual(font['A'].references[0][0], 'custom.component')
            finally:
                font.close()
            a['dependencies'][0]['expected_source_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'dependency drift'):
                self.apply(root, [a, c])

    def test_duplicate_override_and_missing_dependency_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = records(self.base)['A']
            entry = self.authored(root, 'A', old, old)
            with self.assertRaisesRegex(ValueError, 'Duplicate authored'):
                self.apply(root, [entry, entry])
            changed = old.replace('EndChar\n', 'Refer: 9000 -1 N 1 0 0 1 0 0 2\nEndChar\n')
            entry = self.authored(root, 'A', changed, old)
            with self.assertRaisesRegex(ValueError, 'dependency manifest'):
                self.apply(root, [entry])

    def test_cycle_rejected(self):
        from assemble_sources import encoding
        old = records(self.base)['A']
        _, cp, gid = encoding(old)
        changed = old.replace('EndChar\n', f'Refer: {gid} {cp} N 1 0 0 1 0 0 2\nEndChar\n')
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            check_references(self.base.replace(old, changed))


    def test_upstream_review_includes_metrics_glyphs_and_dependents(self):
        from review_upstream import compare
        old = records(self.base)['A']
        changed = self.base.replace(old, old.replace('Width: 575', 'Width: 576'))
        changed = changed.replace('HheadAscent: 910', 'HheadAscent: 911')
        report = compare(self.base, changed)
        self.assertEqual([r['glyph_name'] for r in report['changed_glyphs']], ['A'])
        self.assertTrue(report['affected_reference_dependents'])
        self.assertIn('HheadAscent: 911', report['metadata_metrics_layout_diff'])


if __name__ == '__main__':
    unittest.main()
