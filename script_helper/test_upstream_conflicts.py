#!/usr/bin/env python3
"""Ownership review tests using actual upstream glyphs and synthetic candidate edits."""
import copy
import json
import tempfile
import unittest
import shutil
from unittest.mock import patch
from pathlib import Path
from assemble_sources import records, encoding, add_symbols, renamed
from fetch_build_dependencies import fetch, MANIFEST
from glyph_overrides import digest
from upstream_conflicts import ownership_items, resolve, json_hash, make_report, checked_apply
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


class ApplyTests(unittest.TestCase):
    """Run real report/assembly/apply against isolated live and temporary locks."""
    @classmethod
    def setUpClass(cls):
        import assemble_sources as assembly
        cls.project = assembly.ROOT
        cls.recipe = json.loads((cls.project / 'src/overlays.json').read_text())
        cls.catalog = json.loads((cls.project / cls.recipe['symbols']).read_text())
        cls.symbols = assembly.make_symbols(cls.catalog)
        cls.cached = {style: fetch('upstream-' + style) for style in assembly.STYLES}

    def setUp(self):
        import assemble_sources as assembly
        import fetch_build_dependencies as dependencies
        import upstream_conflicts as conflicts
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.live = self.root / 'script_helper/build_dependencies.json'
        files = ['src/overlays.json', 'src/upstream-decisions.json', self.recipe['symbols'],
                 'script_helper/build_dependencies.json', 'script_helper/add_braille.py', *MANIFEST['vendored_files']]
        for name in files:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.project / name, destination)
        cache = self.root / '.font-build'; cache.mkdir()
        for style, source in self.cached.items():
            shutil.copyfile(source, cache / MANIFEST['assets']['upstream-' + style]['filename'])
        for module in (assembly, dependencies, conflicts):
            self.enterContext(patch.object(module, 'ROOT', self.root))
        # Donor conversion is tested elsewhere. Cache its real records while
        # exercising the actual SFD assembler, overrides, report and file writes.
        for module in (assembly, conflicts):
            self.enterContext(patch.object(module, 'make_symbols', return_value=self.symbols))
        old = self.cached['Regular'].read_text()
        a, b = records(old)['A'], records(old)['B']
        self.b = b
        authored = f'StartChar: A\nEncoding: 65 65 {encoding(a)[2]}\nWidth: 575\nRefer: {encoding(b)[2]} 66 N 1 0 0 1 0 0 2\nEndChar\n'
        source = self.root / 'src/overrides/Regular/A.glyph'
        source.parent.mkdir(parents=True); source.write_text(authored)
        entry = {'style': 'Regular', 'glyph_name': 'A', 'codepoint': '0041', 'operation': 'replace',
                 'source': str(source.relative_to(self.root)), 'source_sha256': digest(authored),
                 'expected_upstream_revision': MANIFEST['upstream']['revision'], 'expected_base_sha256': digest(a),
                 'dependencies': [{'source_gid': encoding(b)[2], 'glyph_name': 'B', 'expected_source_sha256': digest(b)}]}
        recipe = copy.deepcopy(self.recipe); recipe['authored_overrides'] = [entry]
        (self.root / 'src/overlays.json').write_text(json.dumps(recipe))
        self.before = cache / 'before-lock.json'; self.before.write_text(self.live.read_text())
        self.candidate = copy.deepcopy(MANIFEST); self.candidate['upstream']['revision'] = REV
        for style in assembly.STYLES:
            self.candidate['assets']['upstream-' + style]['revision'] = REV
        changed = old.replace(a, a.replace('Width: 575', 'Width: 574'))
        spec = self.candidate['assets']['upstream-Regular']
        spec['filename'] = 'candidate-Regular.sfd'; spec['sha256'] = digest(changed)
        (cache / spec['filename']).write_text(changed)
        self.candidate_path = cache / 'candidate-lock.json'
        self.candidate_path.write_text(json.dumps(self.candidate))
        self.assembled = cache / 'current'
        assembly.assemble(self.assembled, recipe=recipe, decisions=[], manifest=MANIFEST)
        self.review = cache / 'review'
        self.report = make_report(self.before, self.candidate_path, self.assembled, self.review)
        self.item = next(i for i in self.report['items'] if i['kind'] == 'authored')
        revised = copy.deepcopy(entry)
        revised['expected_upstream_revision'] = REV
        revised['expected_base_sha256'] = self.item['candidate_base']['sha256']
        new_source = source.with_name('A-revised.glyph')
        new_source.write_text(authored.replace('Width: 575', 'Width: 577'))
        revised['source'] = str(new_source.relative_to(self.root))
        revised['source_sha256'] = digest(new_source.read_text())
        self.override = revised
        self.targets = [self.live, self.root / 'src/overlays.json', self.root / 'src/upstream-decisions.json']

    def apply(self, action='revise-overlay', write=True):
        choice = {'id': self.item['id'], 'action': action}
        if action == 'revise-overlay': choice['override'] = self.override
        path = self.review / 'choices.json'
        path.write_text(json.dumps({'report_id': self.report['id'], 'choices': [choice]}))
        checked_apply(self.review / 'report.json', path, write=write)

    def assert_rejected_without_writes(self, message):
        before = {p: p.read_bytes() for p in self.targets}
        with self.assertRaisesRegex(ValueError, message): self.apply()
        self.assertEqual({p: p.read_bytes() for p in self.targets}, before)

    def test_temporary_locks_still_guard_live_lock(self):
        self.assertIn(str(self.live.resolve()), [s['path'] for s in self.report['snapshots']])
        self.live.write_text(self.live.read_text() + '\n')
        self.assert_rejected_without_writes('Stale review input')

    def test_report_missing_live_target_is_rejected(self):
        self.report['snapshots'] = [s for s in self.report['snapshots'] if s['path'] != str(self.live.resolve())]
        self.report['id'] = json_hash({k: v for k, v in self.report.items() if k != 'id'})
        (self.review / 'report.json').write_text(json.dumps(self.report))
        self.assert_rejected_without_writes('snapshot every live apply target')

    def test_revision_guards_are_never_refreshed(self):
        for key, wrong, message in [('expected_base_sha256', '0' * 64, 'base glyph drift'),
                                    ('expected_upstream_revision', '0' * 40, 'upstream revision drift'),
                                    ('operation', 'add', 'addition now collides')]:
            with self.subTest(field=key):
                good = self.override[key]; self.override[key] = wrong
                self.assert_rejected_without_writes(message)
                self.override[key] = good

    def test_revision_dependency_fingerprint_is_checked(self):
        self.override['dependencies'][0]['expected_source_sha256'] = '0' * 64
        self.assert_rejected_without_writes('dependency drift: B')

    def test_live_edit_during_assembly_is_not_overwritten(self):
        import upstream_conflicts as conflicts
        actual_assemble = conflicts.assemble
        before = {p: p.read_bytes() for p in self.targets}
        changed_lock = self.live.read_text() + '\n'
        def assemble_then_edit(*args, **kwargs):
            actual_assemble(*args, **kwargs)
            self.live.write_text(changed_lock)
        with patch.object(conflicts, 'assemble', side_effect=assemble_then_edit):
            with self.assertRaisesRegex(ValueError, 'Stale review input'): self.apply()
        self.assertEqual(self.live.read_text(), changed_lock)
        for path in self.targets:
            if path != self.live: self.assertEqual(path.read_bytes(), before[path])

    def test_valid_revision_applies_exact_guards_and_rerun_is_accepted(self):
        import assemble_sources as assembly
        self.apply()
        recipe = json.loads((self.root / 'src/overlays.json').read_text())
        self.assertEqual(recipe['authored_overrides'], [self.override])
        self.assertEqual(json.loads(self.live.read_text()), self.candidate)
        decisions = json.loads((self.root / 'src/upstream-decisions.json').read_text())['decisions']
        assembly.assemble(self.assembled, recipe=recipe, decisions=decisions, manifest=self.candidate)
        again = make_report(self.candidate_path, self.candidate_path, self.assembled, self.review / 'again')
        self.assertTrue(all(not i['requires_decision'] for i in again['items']))

    def test_explicit_keep_rebases_reviewed_base(self):
        self.apply(action='keep-overlay')
        entry = json.loads((self.root / 'src/overlays.json').read_text())['authored_overrides'][0]
        self.assertEqual(entry['expected_base_sha256'], self.item['candidate_base']['sha256'])
        self.assertEqual(entry['dependencies'][0]['expected_source_sha256'], digest(self.b))


if __name__ == '__main__': unittest.main()
