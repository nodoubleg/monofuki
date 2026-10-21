#!/usr/bin/env python3
"""Negative publication-gate tests; never access GitHub or execute font scripts."""
import copy
import io
import os
import re
import shutil
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import native_evidence as evidence
import native_handoff as handoff
import verify_on_mac as mac

SHA = 'a' * 40
RUN = {'id': 123, 'run_attempt': 2, 'head_sha': SHA, 'workflow_id': 4,
       'html_url': 'https://github.com/nodoubleg/monofuki/actions/runs/123',
       'repository': {'full_name': evidence.REPOSITORY}, 'head_repository': {'full_name': evidence.REPOSITORY},
       'path': evidence.BUILD_WORKFLOW, 'event': 'push', 'head_branch': 'master',
       'pull_requests': [], 'status': 'completed', 'conclusion': 'success'}
WORKFLOW = {'path': evidence.BUILD_WORKFLOW, 'id': 4}


def artifact(family, identity):
    return {'name': f'{family}-{SHA}-attempt-2', 'id': identity, 'expired': False,
            'size_in_bytes': 1234, 'digest': 'sha256:' + 'b'*64,
            'workflow_run': {'id': 123, 'head_sha': SHA, 'head_branch': 'master'}}


class RunGateTests(unittest.TestCase):
    def test_valid_and_idempotent(self):
        a = evidence.validate_run(RUN, WORKFLOW, SHA, SHA, 2)
        self.assertEqual(a, evidence.validate_run(RUN, WORKFLOW, SHA, SHA, 2))
        self.assertEqual(a['run_attempt'], 2)

    def test_reject_bad_source_states(self):
        mutations = [
            {'repository': {'full_name': 'someone/monofuki'}},
            {'head_repository': {'full_name': 'someone/monofuki'}},
            {'event': 'pull_request'}, {'event': 'pull_request_target'},
            {'head_branch': 'feature'}, {'pull_requests': [{'number': 5}]},
            {'status': 'in_progress'}, {'conclusion': 'failure'}, {'conclusion': 'cancelled'},
            {'path': '.github/workflows/other.yml'}, {'workflow_id': 99},
            {'head_sha': 'b'*40}, {'run_attempt': 3},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                evidence.validate_run(dict(RUN, **mutation), WORKFLOW, SHA, SHA, 2)
        with self.assertRaises(ValueError):
            evidence.validate_run(RUN, WORKFLOW, 'c'*40)

    def test_current_attempt_artifacts_only(self):
        items = [artifact('Monofuki', 1), artifact('MonofukiNerdFont', 2)]
        self.assertEqual(set(evidence.select_artifacts(RUN, items)), {'regular', 'nerd'})
        old = artifact('Monofuki', 3); old['name'] = old['name'].replace('attempt-2', 'attempt-1')
        self.assertEqual(evidence.select_artifacts(RUN, items + [old])['regular']['id'], 1)
        for broken in (items[:1], items + [items[0]], [old, items[1]]):
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                evidence.select_artifacts(RUN, broken)
        for mutation in ({'expired': True}, {'digest': None}, {'size_in_bytes': 0},
                         {'workflow_run': {'id': 999, 'head_sha': SHA, 'head_branch': 'master'}}):
            with self.subTest(mutation=mutation), self.assertRaises((ValueError, TypeError)):
                evidence.select_artifacts(RUN, [dict(items[0], **mutation), items[1]])

    def test_owner_and_branch_required_before_download(self):
        env = {'GITHUB_REPOSITORY': evidence.REPOSITORY, 'GITHUB_REF': 'refs/heads/master',
               'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_ACTOR': 'nodoubleg',
               'GITHUB_TRIGGERING_ACTOR': 'nodoubleg', 'GITHUB_SHA': SHA}
        for key, value in [('GITHUB_ACTOR', 'outsider'), ('GITHUB_TRIGGERING_ACTOR', 'outsider'),
                           ('GITHUB_REF', 'refs/heads/other'), ('GITHUB_EVENT_NAME', 'pull_request'),
                           ('GITHUB_REPOSITORY', 'outsider/monofuki')]:
            with self.subTest(key=key), patch.dict(os.environ, dict(env, **{key: value}), clear=True), patch.object(handoff, 'context') as fetch:
                with self.assertRaises(ValueError):
                    handoff.prepare_site(123, 'b'*40, '/unused', SHA, '/unused')
                fetch.assert_not_called()


class ArchiveTests(unittest.TestCase):
    def archive(self, files):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as z:
            for key, value in files:
                z.writestr(key, value)
        data.seek(0)
        return data

    def test_valid_archive_and_fresh_destination(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)/'out'
            evidence.extract_zip(self.archive([('a/b.json', b'{}')]), target)
            self.assertEqual((target/'a/b.json').read_bytes(), b'{}')
            with self.assertRaises(ValueError):
                evidence.extract_zip(self.archive([('x', b'')]), target)

    def test_traversal_duplicate_symlink_and_size(self):
        cases = [[('../escape', b'x')], [('/escape', b'x')], [('a/../../x', b'x')],
                 [('a\\x', b'x')], [('a', b'x'), ('a', b'y')]]
        link = zipfile.ZipInfo('link');link.external_attr = (stat.S_IFLNK | 0o777) << 16
        cases.append([(link, b'/tmp/escape')])
        for files in cases:
            with self.subTest(files=files), tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
                evidence.extract_zip(self.archive(files), Path(d)/'out')
        with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):
            evidence.extract_zip(self.archive([('large', b'x'*100)]), Path(d)/'out', max_bytes=2)

    def test_duplicate_json_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)/'bad.json';f.write_text('{"status":"passed","status":"failed"}')
            with self.assertRaises(ValueError): evidence.read_json(f)

    def test_bundle_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);source=p/'source';source.mkdir();(source/'manifest.json').write_text('{}')
            evidence.bundle_evidence(source,p/'a.zip');evidence.bundle_evidence(source,p/'b.zip')
            self.assertEqual((p/'a.zip').read_bytes(),(p/'b.zip').read_bytes())


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.expected = {'run': {'head_sha': SHA, 'id': 123, 'run_attempt': 2}, 'input_files': {'regular': {'font': 'c'*64}}, 'script_sha256': {'check': 'd'*64}}
        for name in evidence.REPORTS:
            (self.root/name).write_text('{}')
        for kind in ('regular','nerd'):
            for theme in ('light','dark'):(self.root/f'{kind}-{theme}.png').write_bytes(b'png')
        (self.root/'tuned-coretext-proof.png').write_bytes(b'png')
        self.manifest = {'contract':self.expected,'supervisor':'nodoubleg','status':'passed',
                         'steps':[{'name':n,'exit_code':0} for n in evidence.STEPS],
                         'completed_at':'2026-10-21T18:00:00Z',
                         'host':{'system':'Darwin','architecture':'arm64','product_version':'27.0.1','build_version':'test','swift_version':'test'},
                         'output_sha256':evidence.inventory(self.root)}
        self.save()

    def save(self): (self.root/'manifest.json').write_bytes(evidence.canonical(self.manifest))
    def verify(self): return evidence.validate_evidence(self.root,self.expected,'fonts','scripts')

    def test_valid_manifest_reaches_semantic_report_validation(self):
        with patch.object(evidence,'validate_reports') as check:
            self.verify();check.assert_called_once()

    def test_failed_partial_stale_mismatch_and_changed_scripts(self):
        cases = [lambda m:m.update(status='failed'), lambda m:m.update(supervisor='outsider'),
                 lambda m:m['steps'].pop(), lambda m:m['steps'][0].update(exit_code=1),
                 lambda m:m['host'].update(system='Linux'),lambda m:m['host'].pop('product_version'),
                 lambda m:m['contract']['run'].update(run_attempt=1),lambda m:m['contract']['run'].update(head_sha='f'*40),
                 lambda m:m['contract']['input_files']['regular'].update(font='0'*64),
                 lambda m:m['contract']['script_sha256'].update(check='0'*64)]
        original=copy.deepcopy(self.manifest)
        for change in cases:
            self.manifest=copy.deepcopy(original);change(self.manifest);self.save()
            with self.subTest(manifest=self.manifest), patch.object(evidence,'validate_reports') as check, self.assertRaises(ValueError):
                self.verify()
            check.assert_not_called()

    def test_corrupt_missing_extra_and_executable_payload(self):
        for path, data in [('coretext.json',b'corrupt'),('extra.py',b'print(1)')]:
            target=self.root/path;old=target.read_bytes() if target.exists() else None;target.write_bytes(data)
            with patch.object(evidence,'validate_reports'), self.assertRaises(ValueError):self.verify()
            if old is None:target.unlink()
            else:target.write_bytes(old)
        (self.root/'coretext.json').unlink()
        with patch.object(evidence,'validate_reports'),self.assertRaises(ValueError):self.verify()
        (self.root/'coretext.json').write_bytes(b'{}');(self.root/'extra.py').write_text('print(1)')
        self.manifest['output_sha256']=evidence.inventory(self.root);self.manifest['output_sha256'].pop('manifest.json');self.save()
        with patch.object(evidence,'validate_reports'),self.assertRaises(ValueError):self.verify()


class PagesArtifactRetryTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / '.github/workflows/publish-verified-site.yml'
        text = path.read_text()
        self.output = re.search(r'^      pages_artifact_name: (.+)$', text, re.M).group(1)
        upload = text.split('uses: actions/upload-pages-artifact@', 1)[1].split('\n  deploy:', 1)[0]
        self.upload = re.search(r'^          name: (.+)$', upload, re.M).group(1)
        deploy = text.split('uses: actions/deploy-pages@', 1)[1]
        self.deploy = re.search(r'^          artifact_name: (.+)$', deploy, re.M).group(1)

    def evaluate(self, expression, attempt, site_output=None):
        context = {'github.run_id': '12345', 'github.run_attempt': str(attempt),
                   'needs.site.outputs.pages_artifact_name': site_output}
        return re.sub(r'\$\{\{\s*([^{}]+?)\s*\}\}', lambda m: context[m.group(1)], expression)

    def select(self, artifacts, attempt, saved_output):
        name = self.evaluate(self.deploy, attempt, saved_output)
        matches = [a for a in artifacts if a['name'] == name]
        self.assertEqual(len(matches), 1, 'deploy-pages requires exactly one matching artifact')
        return matches[0]['id']

    def test_full_retry_selects_new_site_attempt_unambiguously(self):
        artifacts = []
        for attempt in (1, 2):
            name = self.evaluate(self.upload, attempt)
            output = self.evaluate(self.output, attempt)
            self.assertEqual(output, name)
            artifacts.append({'name': name, 'id': attempt})
        self.assertNotEqual(artifacts[0]['name'], artifacts[1]['name'])
        self.assertEqual(self.select(artifacts, 2, output), 2)

    def test_deploy_only_retry_uses_saved_successful_site_output(self):
        saved_output = self.evaluate(self.output, 1)
        artifacts = [{'name': self.evaluate(self.upload, 1), 'id': 1}]
        self.assertEqual(self.select(artifacts, 2, saved_output), 1)
        self.assertEqual(self.select(artifacts, 3, saved_output), 1)


class DispatchRecoveryTests(unittest.TestCase):
    def test_confirmed_existing_run_is_not_redispatched(self):
        with tempfile.TemporaryDirectory() as d, patch.object(mac,'find_publication',return_value={'id':5,'html_url':'https://github.com/test','status':'completed'}), patch.object(mac.subprocess,'run') as call:
            mac.dispatch_verified(Path(d),RUN,'b'*40)
            mac.dispatch_verified(Path(d),RUN,'b'*40)
            call.assert_not_called()

    def test_uncertain_dispatch_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as d, patch.object(mac,'find_publication',return_value=None), patch.object(mac.subprocess,'run') as call, patch.object(mac.time,'sleep'):
            with self.assertRaises(ValueError): mac.dispatch_verified(Path(d),RUN,'b'*40)
            self.assertEqual(call.call_count,1)
            with self.assertRaises(ValueError): mac.dispatch_verified(Path(d),RUN,'b'*40)
            self.assertEqual(call.call_count,1)


@unittest.skipUnless(os.environ.get('MONOFUKI_NATIVE_FIXTURE'), 'Native report fixtures are supplied for Mac/staging review')
class ActualNativeReportTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(os.environ['MONOFUKI_NATIVE_FIXTURE'])
        self.manifest=evidence.read_json(self.root/'evidence/manifest.json')

    def verify(self):
        evidence.validate_reports(self.root/'evidence',self.root/'fonts',self.root/'source/script_helper',self.manifest['host'])

    def test_actual_reports(self):self.verify()

    def test_partial_and_failed_report_coverage(self):
        original=evidence.read_json
        cases=[('coretext.json',lambda d:d['records'].pop()),
               ('tuned-coretext-proof.json',lambda d:d['fonts'].pop()),
               ('tuned-coretext-proof.json',lambda d:d['fonts'][0].update(sha256='0'*64)),
               ('tuned-coretext-proof.json',lambda d:d['fonts'][0]['modes'][0]['run_advance_widths_font_units'].__setitem__(0,574)),
               ('small-n-coretext.json',lambda d:d['results'].pop()),
               ('small-n-coretext.json',lambda d:d['results'][0].update(ink_pixels=0)),
               ('export-visibility.json',lambda d:d['results'][0].update(lost=1)),
               ('export-visibility.json',lambda d:d['results'][0].update(mapped=1)),
               ('emoji-coretext.json',lambda d:d['results'].pop()),
               ('emoji-coretext.json',lambda d:d['results'][0].update(requested_font='Fallback'))]
        for name,change in cases:
            def load(path):
                result=original(path)
                if Path(path).name==name:change(result)
                return result
            with self.subTest(name=name),patch.object(evidence,'read_json',side_effect=load),self.assertRaises(ValueError):self.verify()


if __name__ == '__main__':
    unittest.main()
