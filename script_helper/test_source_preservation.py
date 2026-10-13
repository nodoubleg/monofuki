#!/usr/bin/env python3
"""Regression checks for upstream preservation and refusing ambiguous overlays."""
import re
import unittest
from assemble_sources import check_preservation, check_references, records, renamed, restore_arrows
from fetch_build_dependencies import fetch


class PreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fetch('upstream-Regular').read_text()
        cls.renamed = renamed(cls.base, 'Regular')

    def test_name_only_change_preserves_every_record(self):
        self.assertEqual(check_preservation(self.base, self.renamed, 'Regular'), 1247)

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


if __name__ == '__main__':
    unittest.main()
