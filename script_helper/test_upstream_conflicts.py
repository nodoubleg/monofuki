#!/usr/bin/env python3
"""Ownership review tests using actual upstream glyphs and synthetic candidate edits."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from assemble_sources import records, encoding, add_symbols, renamed
from fetch_build_dependencies import fetch, MANIFEST
from glyph_overrides import digest
from upstream_conflicts import ownership_items, resolve, json_hash
from upstream_decisions import binding, accepted_action, replace_identity

REV = 'a' * 40


class ConflictTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = fetch('upstream-Regular').read_text()
        cls.a = records(cls.base)['A']

    def item(self, old, new, current, recipe, symbols=None, accepted=None, root=None):
        return ownership_items('Regular', old, new, current, recipe, symbols or {}, REV, accepted or [], root or Path.cwd())

    def recipe(self, root, name='A', dependencies=None):
        source = self.a.replace('Width: 575', 'Width: 576')
        path = root / 'src/overrides/Regular/A.glyph'
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(source)
        return {'authored_overrides': [{'style': 'Regular', 'glyph_name': name, 'codepoint': '0041', 'operation': 'replace',
                'source': str(path.relative_to(root)), 'source_sha256': digest(source),
                'expected_base_sha256': digest(self.a), 'expected_upstream_revision': MANIFEST['upstream']['revision'],
                'dependencies': dependencies or []}]}

    def report(self, recipe, items):
        report = {'recipe': recipe, 'items': items, 'accepted': [], 'snapshots': [],
                  'candidate_lock': {'upstream': {'revision': REV}}}
        report['id'] = json_hash(report)
        return report

    def test_new_upstream_glyph_fills_donor_gap_and_requires_choice(self):
        donor = 'StartChar: uni2427\nEncoding: 9255 9255 9000\nWidth: 575\nEndChar\n'
        candidate = add_symbols(self.base, {0x2427: donor.replace('Width: 575', 'Width: 574')})
        current = add_symbols(self.base, {0x2427: donor})
        item = self.item(self.base, candidate, current, {'authored_overrides': []}, {0x2427: donor})[0]
        self.assertTrue(item['requires_decision']); self.assertIsNone(item['old'])
        report = self.report({'authored_overrides': []}, [item])
        with self.assertRaisesRegex(ValueError, 'Unresolved'):
            resolve(report, {'report_id': report['id'], 'choices': []})
        for action in ('keep-overlay', 'adopt-upstream'):
            _, decisions = resolve(report, {'report_id': report['id'], 'choices': [{'id': item['id'], 'action': action}]})
            self.assertEqual(accepted_action(decisions, item['binding']), action)
            again = self.item(candidate, candidate, current, {'authored_overrides': []}, {0x2427: donor}, decisions)[0]
            self.assertFalse(again['requires_decision'])
            stale = dict(item['binding'], candidate_sha256='0'*64)
            with self.assertRaisesRegex(ValueError, 'stale'):
                accepted_action(decisions, stale)
            preserved = replace_identity(donor, item['candidate']['record'])
            self.assertEqual(encoding(preserved), tuple(item['candidate']['encoding']))

    def test_changed_override_requires_explicit_keep_or_adopt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); recipe=self.recipe(root)
            candidate = self.base.replace(self.a, self.a.replace('Width: 575', 'Width: 574'))
            item=self.item(self.base,candidate,renamed(self.base,'Regular'),recipe,root=root)[0]
            self.assertTrue(item['requires_decision'])
            report=self.report(recipe,[item])
            kept,_=resolve(report,{'report_id':report['id'],'choices':[{'id':item['id'],'action':'keep-overlay'}]})
            self.assertEqual(kept['authored_overrides'][0]['expected_base_sha256'],item['candidate']['sha256'])
            adopted,_=resolve(report,{'report_id':report['id'],'choices':[{'id':item['id'],'action':'adopt-upstream'}]})
            self.assertEqual(adopted['authored_overrides'],[])

    def test_unchanged_override_needs_no_repeated_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);recipe=self.recipe(root)
            item=self.item(self.base,self.base,renamed(self.base,'Regular'),recipe,root=root)[0]
            self.assertFalse(item['requires_decision'])
            report=self.report(recipe,[item])
            updated,_=resolve(report,{'report_id':report['id'],'choices':[]})
            self.assertEqual(updated['authored_overrides'][0]['expected_upstream_revision'],REV)

    def test_changed_or_removed_component_requires_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);dep=records(self.base)['B']
            recipe=self.recipe(root,dependencies=[{'source_gid':encoding(dep)[2],'glyph_name':'B','expected_source_sha256':digest(dep)}])
            for candidate in (self.base.replace(dep,dep.replace('Width: 575','Width: 574')), self.base.replace(dep,'').replace('BeginChars: 65588 1247','BeginChars: 65588 1246')):
                # Build a count-correct synthetic source after removing the component.
                if dep not in candidate and 'StartChar: B\n' not in candidate:
                    import re
                    candidate=re.sub(r'^(BeginChars: \d+) \d+$',r'\1 1246',candidate,flags=re.M)
                item=self.item(self.base,candidate,self.base,recipe,root=root)[0]
                self.assertTrue(item['requires_decision']);self.assertTrue(item['dependency_changes'])
                if item['dependency_changes'][0]['candidate_sha256'] is None:
                    report=self.report(recipe,[item])
                    with self.assertRaisesRegex(ValueError,'removed'):
                        resolve(report,{'report_id':report['id'],'choices':[{'id':item['id'],'action':'keep-overlay'}]})

    def test_authored_replacement_of_donor_uses_effective_base(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            donor='StartChar: uni2427\nEncoding: 9255 9255 9000\nWidth: 575\nEndChar\n'
            effective=add_symbols(self.base,{0x2427:donor})
            base_record=records(effective)['uni2427']
            changed=base_record.replace('Width: 575','Width: 576')
            path=root/'src/overrides/Regular/uni2427.glyph';path.parent.mkdir(parents=True);path.write_text(changed)
            entry={'style':'Regular','glyph_name':'uni2427','codepoint':'2427','operation':'replace',
                   'source':str(path.relative_to(root)),'source_sha256':digest(changed),'expected_base_sha256':digest(base_record),
                   'expected_upstream_revision':MANIFEST['upstream']['revision'],'dependencies':[]}
            recipe={'authored_overrides':[entry]}
            items=ownership_items('Regular',self.base,self.base,effective.replace(base_record,changed),recipe,{0x2427:donor},REV,[],root,effective)
            self.assertEqual(len(items),1);self.assertFalse(items[0]['requires_decision'])
            self.assertIsNone(items[0]['candidate']);self.assertIsNotNone(items[0]['candidate_base'])
            report=self.report(recipe,items)
            updated,_=resolve(report,{'report_id':report['id'],'choices':[]})
            self.assertEqual(updated['authored_overrides'][0]['operation'],'replace')
            self.assertEqual(updated['authored_overrides'][0]['expected_base_sha256'],digest(base_record))

    def test_stale_report_and_changed_snapshot_rejected(self):
        report=self.report({'authored_overrides':[]},[])
        with self.assertRaisesRegex(ValueError,'fingerprint'):
            resolve(report,{'report_id':'0'*64,'choices':[]})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input';path.write_text('before')
            report['snapshots']=[{'path':str(path),'sha256':digest('before')}]
            report['id']=json_hash({k:v for k,v in report.items() if k!='id'})
            path.write_text('after')
            with self.assertRaisesRegex(ValueError,'Stale review input'):
                resolve(report,{'report_id':report['id'],'choices':[]})


if __name__ == '__main__': unittest.main()
