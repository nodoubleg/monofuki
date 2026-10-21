#!/usr/bin/env python3
"""GitHub transport for exact-build native evidence; uses existing gh access."""
import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path

from native_evidence import (BUILD_WORKFLOW, EVIDENCE_BRANCH, MAX_EVIDENCE, OWNER,
    REPOSITORY, SCRIPTS, canonical, contract, extract_zip, file_hash, read_json,
    require, select_artifacts, sha256, valid_sha, validate_evidence, validate_run)


def gh_api(endpoint, binary=False):
    require(endpoint.startswith(f'repos/{REPOSITORY}/') or endpoint == 'user', 'Unexpected API target')
    data = subprocess.run(['gh', 'api', endpoint], check=True, capture_output=True).stdout
    return data if binary else json.loads(data)


def context(run_id, expected_sha=None, expected_attempt=None):
    require(str(run_id).isdigit() and int(run_id) > 0, 'Invalid build run ID')
    prefix = f'repos/{REPOSITORY}'
    run = gh_api(f'{prefix}/actions/runs/{run_id}')
    workflow = gh_api(f'{prefix}/actions/workflows/build-fonts.yml')
    head = gh_api(f'{prefix}/git/ref/heads/master')['object']['sha']
    binding = validate_run(run, workflow, head, expected_sha, expected_attempt)
    require(binding['id'] == int(run_id), 'Build run ID mismatch')
    items = []
    for page in range(1, 21):
        batch = gh_api(f'{prefix}/actions/runs/{run_id}/artifacts?per_page=100&page={page}')['artifacts']
        items.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ValueError('Too many artifacts')
    return binding, select_artifacts(binding, items)


def download_fonts(run, artifacts, workspace):
    workspace = Path(workspace)
    (workspace / 'archives').mkdir(parents=True, exist_ok=True)
    for kind, item in artifacts.items():
        data = gh_api(f'repos/{REPOSITORY}/actions/artifacts/{item["id"]}/zip', binary=True)
        require(len(data) == item['size_in_bytes'] and 'sha256:' + sha256(data) == item['digest'], 'Artifact archive digest or size mismatch')
        archive = workspace / 'archives' / f'{kind}.zip'
        archive.write_bytes(data)
        extract_zip(archive, workspace / 'fonts' / kind)
    fresh = context(run['id'], run['head_sha'], run['run_attempt'])
    require(fresh == (run, artifacts), 'Artifacts changed during download')


def download_scripts(commit, directory):
    require(valid_sha(commit), 'Invalid source SHA')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    for name in SCRIPTS:
        item = gh_api(f'repos/{REPOSITORY}/contents/script_helper/{name}?ref={commit}')
        require(item.get('type') == 'file' and item.get('encoding') == 'base64', 'Unexpected native script object')
        data = base64.b64decode(item['content'].replace('\n', ''), validate=True)
        require(hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest() == item['sha'], 'Native source blob mismatch')
        (directory / name).write_bytes(data)


def fetch_evidence(commit, workspace):
    require(valid_sha(commit), 'Invalid evidence commit SHA')
    prefix = f'repos/{REPOSITORY}'
    tip = gh_api(f'{prefix}/git/ref/heads/{EVIDENCE_BRANCH}')['object']['sha']
    comparison = gh_api(f'{prefix}/compare/{commit}...{tip}')
    require(comparison.get('status') in ('ahead', 'identical')
            and comparison.get('merge_base_commit', {}).get('sha') == commit,
            'Evidence is not retained on the dedicated data branch')
    record = gh_api(f'{prefix}/git/commits/{commit}')
    tree = gh_api(f'{prefix}/git/trees/{record["tree"]["sha"]}')
    entries = tree.get('tree', [])
    require(not tree.get('truncated') and len(entries) == 1, 'Evidence commit must contain exactly one data bundle')
    entry = entries[0]
    require(entry.get('path') == 'native-evidence.zip' and entry.get('type') == 'blob'
            and entry.get('mode') == '100644' and 0 < entry.get('size', 0) <= MAX_EVIDENCE,
            'Unexpected evidence tree payload')
    blob = gh_api(f'{prefix}/git/blobs/{entry["sha"]}')
    require(blob.get('encoding') == 'base64', 'Unexpected evidence blob encoding')
    data = base64.b64decode(blob['content'].replace('\n', ''), validate=True)
    require(len(data) == entry['size'] and hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest() == entry['sha'], 'Evidence blob mismatch')
    archive = Path(workspace) / 'native-evidence.zip'
    archive.write_bytes(data)
    extract_zip(archive, Path(workspace) / 'evidence', max_bytes=64 * 1024 * 1024, max_files=64)
    return archive


def prepare_site(run_id, evidence_commit, workspace, source_sha, script_root):
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY
            and os.environ.get('GITHUB_REF') == 'refs/heads/master'
            and os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
            and os.environ.get('GITHUB_ACTOR') == OWNER
            and os.environ.get('GITHUB_TRIGGERING_ACTOR') == OWNER,
            'Publication requires an explicit repository-owner dispatch on master')
    require(valid_sha(source_sha) and source_sha == os.environ.get('GITHUB_SHA'), 'Wrong publication source checkout')
    workspace = Path(workspace)
    require(not workspace.exists(), 'Publication workspace must be fresh')
    workspace.mkdir(parents=True)
    run, artifacts = context(run_id, source_sha)
    download_fonts(run, artifacts, workspace)
    archive = fetch_evidence(evidence_commit, workspace)
    expected = contract(run, artifacts, workspace / 'fonts', script_root)
    manifest = validate_evidence(workspace / 'evidence', expected, workspace / 'fonts', script_root)
    receipt = {'schema_version': 1, 'source_commit': source_sha, 'build_run_id': run['id'],
               'build_attempt': run['run_attempt'], 'build_url': run['html_url'],
               'evidence_commit': evidence_commit, 'evidence_sha256': file_hash(archive),
               'manifest_sha256': file_hash(workspace / 'evidence/manifest.json'),
               'host': manifest['host'], 'supervisor': manifest['supervisor'],
               'completed_at': manifest['completed_at'], 'status': 'passed'}
    (workspace / 'receipt.json').write_bytes(canonical(receipt))
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a') as f:
            f.write(f'source_sha={source_sha}\nbuild_attempt={run["run_attempt"]}\nbuild_url={run["html_url"]}\n')
    return receipt


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare-site')
    prepare.add_argument('--run-id', required=True, type=int)
    prepare.add_argument('--evidence-commit', required=True)
    prepare.add_argument('--workspace', required=True, type=Path)
    prepare.add_argument('--source-sha', required=True)
    check = sub.add_parser('check-current')
    check.add_argument('--run-id', required=True, type=int)
    check.add_argument('--source-sha', required=True)
    check.add_argument('--attempt', required=True, type=int)
    args = p.parse_args()
    if args.command == 'prepare-site':
        print(json.dumps(prepare_site(args.run_id, args.evidence_commit, args.workspace, args.source_sha, Path(__file__).parent), indent=2))
    else:
        context(args.run_id, args.source_sha, args.attempt)
        print('PASS current master, successful build attempt, and immutable artifact identities')


if __name__ == '__main__':
    main()
