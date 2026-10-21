#!/usr/bin/env python3
"""Supervised Mac check and explicit submission; no installed runner or fonts.

check RUN_ID --output NEW_DIRECTORY downloads the successful current-master build
and native scripts at its exact source commit. submit DIRECTORY revalidates inputs,
pushes only a data bundle to native-verification, then dispatches Pages publication.
"""
import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

from native_evidence import (EVIDENCE_BRANCH, OWNER, PUBLISH_WORKFLOW, REPOSITORY,
    STEPS, bundle_evidence, canonical, contract, expected_fonts, file_hash,
    inventory, read_json, require, validate_evidence)
from native_handoff import context, download_fonts, download_scripts, gh_api


def command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs).stdout.decode().strip()


def native_checks(workspace, expected, supervisor):
    require(platform.system() == 'Darwin', 'Native verification must run on macOS')
    workspace = Path(workspace).resolve()
    evidence = workspace / 'evidence'
    require(not evidence.exists(), 'Native output must be fresh; use a new directory after failure')
    evidence.mkdir()
    (workspace / '.font-build').mkdir(exist_ok=True)
    logs = workspace / 'logs'
    logs.mkdir(exist_ok=True)
    scripts = workspace / 'source/script_helper'
    paths = expected_fonts(workspace / 'fonts')
    relative = lambda p: str(p.relative_to(workspace))
    regular = sorted(relative(p) for p in paths if p.parent.name == 'regular' and p.suffix == '.otf')
    otfs = sorted(relative(p) for p in paths if p.suffix == '.otf')
    native = sorted(relative(p) for p in paths if p.suffix in ('.otf', '.ttf'))
    ttfs = sorted(relative(p) for p in paths if p.suffix == '.ttf')
    swift = lambda name: ['swift', '-module-cache-path', '.swift-module-cache', f'source/script_helper/{name}']
    steps = [
        ('fallback', swift('render_coretext_previews.swift') + ['fonts/nerd/character-catalog.json', 'fonts/regular/Monofuki-Regular.otf', 'fonts/nerd/MonofukiNerdFont-Regular.otf', 'evidence'], None),
        ('tuned', swift('check_tuned_coretext.swift') + regular, 'tuned-coretext-proof.json'),
        ('small_n', swift('check_small_n_coretext.swift') + native, 'small-n-coretext.json'),
        ('visibility', swift('check_export_visibility.swift') + ttfs, 'export-visibility.json'),
        ('emoji', swift('check_macos_emoji.swift') + ['fonts/nerd/emoji-cases.json'] + otfs + ['--preview-dir', 'evidence/emoji-previews'], 'emoji-coretext.json'),
        ('emoji_validation', [sys.executable, 'source/script_helper/check_emoji_results.py', 'evidence/emoji-coretext.json'], None),
    ]
    completed = []
    for name, args, report in steps:
        print(f'Native check: {name}', flush=True)
        output = evidence / report if report else logs / f'{name}.txt'
        with output.open('wb') as stdout, (logs / f'{name}.stderr.txt').open('wb') as stderr:
            result = subprocess.run(args, cwd=workspace, stdout=stdout, stderr=stderr)
        if result.returncode:
            (workspace / 'failure.json').write_bytes(canonical({'step': name, 'exit_code': result.returncode, 'completed': completed}))
            raise ValueError(f'Native check failed: {name}; no submission is permitted; see {logs}')
        if name == 'tuned':
            shutil.move(workspace / '.font-build/tuned-coretext-proof.png', evidence / 'tuned-coretext-proof.png')
        completed.append({'name': name, 'exit_code': 0})
    manifest = {'contract': expected, 'supervisor': supervisor, 'status': 'passed', 'steps': completed,
                'completed_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'host': {'system': platform.system(), 'architecture': platform.machine(),
                         'product_version': command(['sw_vers', '-productVersion']),
                         'build_version': command(['sw_vers', '-buildVersion']),
                         'swift_version': command(['swift', '--version'])},
                'output_sha256': inventory(evidence)}
    (evidence / 'manifest.json').write_bytes(canonical(manifest))
    validate_evidence(evidence, expected, workspace / 'fonts', scripts)
    bundle_evidence(evidence, workspace / 'native-evidence.zip')
    print(f'PASS all native checks; evidence ready in {workspace}', flush=True)
    return manifest


def check(run_id, output):
    require(platform.system() == 'Darwin', 'Run this command on the connected Mac')
    require(gh_api('user')['login'] == OWNER, 'Use the existing repository-owner GitHub session')
    output = Path(output).resolve()
    require(not output.exists(), 'Choose a new output directory; partial results are never reused')
    run, artifacts = context(run_id)
    output.mkdir(parents=True)
    download_fonts(run, artifacts, output)
    scripts = output / 'source/script_helper'
    download_scripts(run['head_sha'], scripts)
    expected = contract(run, artifacts, output / 'fonts', scripts)
    (output / 'input-contract.json').write_bytes(canonical(expected))
    native_checks(output, expected, OWNER)
    require(context(run_id, run['head_sha'], run['run_attempt']) == (run, artifacts), 'Build changed during native checks; do not submit')


def git_data_commit(workspace, archive):
    """One ordinary fast-forward data-branch push; recover an uncertain prior push."""
    repo = workspace / 'submission.git'
    if not repo.exists():
        command(['git', 'init', '--bare', str(repo)])
    git = lambda *args, **kw: command(['git', '--git-dir', str(repo), *args], **kw)
    remote = f'https://github.com/{REPOSITORY}.git'
    ref = f'refs/heads/{EVIDENCE_BRANCH}'
    found = command(['git', 'ls-remote', '--heads', remote, ref])
    parent = found.split()[0] if found else None
    if parent:
        git('fetch', '--no-tags', remote, ref)
        tree = git('ls-tree', '-r', parent).splitlines()
        require(len(tree) == 1 and tree[0].endswith('\tnative-evidence.zip')
                and tree[0].startswith('100644 blob '), 'Existing evidence branch has unexpected contents')
    blob = git('hash-object', '-w', str(archive))
    if parent and git('rev-parse', f'{parent}:native-evidence.zip') == blob:
        return parent
    tree = git('mktree', input=f'100644 blob {blob}\tnative-evidence.zip\n'.encode())
    run = read_json(workspace / 'input-contract.json')['run']
    args = ['-c', 'user.name=Monofuki native verification', '-c', 'user.email=nodoubleg@users.noreply.github.com', 'commit-tree', tree]
    if parent:
        args += ['-p', parent]
    commit = git(*args, input=f'Native verification: {run["head_sha"]}, run {run["id"]}, attempt {run["run_attempt"]}\n'.encode())
    (workspace / 'push-state.json').write_bytes(canonical({'commit': commit, 'status': 'pending', 'archive_sha256': file_hash(archive)}))
    result = subprocess.run(['git', '--git-dir', str(repo), 'push', remote, f'{commit}:{ref}'], capture_output=True)
    actual = command(['git', 'ls-remote', '--heads', remote, ref]).split()
    require(actual and actual[0] == commit, 'Evidence push was not confirmed; inspect push-state.json before retrying (no force push was attempted)')
    (workspace / 'push-state.json').write_bytes(canonical({'commit': commit, 'status': 'confirmed', 'archive_sha256': file_hash(archive)}))
    return commit


def find_publication(run_id, commit, source_sha):
    title = f'Publish verified build {run_id} / {commit}'
    runs = gh_api(f'repos/{REPOSITORY}/actions/workflows/{PUBLISH_WORKFLOW}/runs?event=workflow_dispatch&per_page=100')['workflow_runs']
    return next((r for r in runs if r.get('display_title') == title and r.get('head_sha') == source_sha), None)


def dispatch_verified(workspace, run, commit):
    existing = find_publication(run['id'], commit, run['head_sha'])
    state = workspace / 'dispatch-state.json'
    if not existing:
        require(not state.exists(), 'A dispatch outcome is uncertain; recheck Actions before explicitly retrying it')
        state.write_bytes(canonical({'status': 'pending', 'evidence_commit': commit, 'build_run_id': run['id']}))
        result = subprocess.run(['gh', 'workflow', 'run', PUBLISH_WORKFLOW, '--repo', REPOSITORY, '--ref', 'master',
                                 '-f', f'build_run_id={run["id"]}', '-f', f'evidence_commit={commit}'], capture_output=True)
        for _ in range(6):
            existing = find_publication(run['id'], commit, run['head_sha'])
            if existing:
                break
            time.sleep(2)
        require(existing, 'Dispatch outcome not confirmed; pending state retained; do not blindly redispatch')
    state.write_bytes(canonical({'status': 'confirmed', 'evidence_commit': commit, 'build_run_id': run['id'],
                                'publication_run_id': existing['id'], 'url': existing['html_url']}))
    print(existing['html_url'])
    print(f'Publication is {existing["status"]}; monitor it to completion. A failed run may be explicitly retried without repeating native checks if inputs remain identical.')


def submit(workspace):
    workspace = Path(workspace).resolve()
    require(gh_api('user')['login'] == OWNER, 'Only the repository owner submits supervised evidence')
    expected = read_json(workspace / 'input-contract.json')
    run, artifacts = context(expected['run']['id'], expected['run']['head_sha'], expected['run']['run_attempt'])
    require(expected['run'] == run and expected['artifacts'] == artifacts, 'Source artifacts changed')
    fresh = contract(run, artifacts, workspace / 'fonts', workspace / 'source/script_helper')
    require(expected == fresh, 'Local inputs or native scripts changed')
    # Verify script identity against the source commit again before submission.
    refresh = workspace / ('source-refresh-' + str(time.time_ns()))
    download_scripts(run['head_sha'], refresh)
    require({n: file_hash(refresh / n) for n in expected['script_sha256']} == expected['script_sha256'], 'Native scripts differ from source commit')
    validate_evidence(workspace / 'evidence', expected, workspace / 'fonts', refresh)
    archive = workspace / 'native-evidence.zip'
    bundle_evidence(workspace / 'evidence', archive)
    commit = git_data_commit(workspace, archive)
    require(context(run['id'], run['head_sha'], run['run_attempt']) == (run, artifacts), 'Build changed before publication dispatch')
    dispatch_verified(workspace, run, commit)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('check')
    a.add_argument('run_id', type=int)
    a.add_argument('--output', type=Path, required=True)
    a = sub.add_parser('submit')
    a.add_argument('directory', type=Path)
    args = p.parse_args()
    if args.command == 'check':
        check(args.run_id, args.output)
    else:
        submit(args.directory)


if __name__ == '__main__':
    main()
