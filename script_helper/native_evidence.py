#!/usr/bin/env python3
"""Shared, fail-closed contract for supervised native verification.

The repository owner's authenticated submission is the assertion that native
checks ran. Hashes bind that assertion to exact inputs; they do not prove execution.
Evidence is data, never executable input to the publishing workflow.
"""
import hashlib
import json
import math
import re
import stat
import struct
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY = 'nodoubleg/monofuki'
OWNER = 'nodoubleg'
BUILD_WORKFLOW = '.github/workflows/build-fonts.yml'
EVIDENCE_BRANCH = 'native-verification'
PUBLISH_WORKFLOW = 'publish-verified-site.yml'
SCRIPTS = (
    'render_coretext_previews.swift', 'check_tuned_coretext.swift',
    'check_small_n_coretext.swift', 'check_export_visibility.swift',
    'check_macos_emoji.swift', 'check_emoji_results.py',
)
STEPS = ('fallback', 'tuned', 'small_n', 'visibility', 'emoji', 'emoji_validation')
REPORTS = ('coretext.json', 'tuned-coretext-proof.json', 'small-n-coretext.json',
           'export-visibility.json', 'emoji-coretext.json')
REGULAR = ('Regular', 'Italic', 'Bold', 'Bold-Italic')
NERD = ('Regular', 'Italic', 'Bold', 'BoldItalic')
MAX_EVIDENCE = 24 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    return sha256(Path(path).read_bytes())


def canonical(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b'\n'


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f'Invalid JSON number: {x}')))


def valid_sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{40}', value) is not None


def safe_path(name):
    p = PurePosixPath(name)
    require(isinstance(name, str) and name and not p.is_absolute() and '\\' not in name
            and all(part not in ('', '.', '..') for part in name.split('/')),
            f'Unsafe archive path: {name!r}')
    return p


def inventory(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Symlinks are not allowed')
        if path.is_file():
            name = path.relative_to(root).as_posix()
            safe_path(name)
            result[name] = file_hash(path)
    return result


def extract_zip(archive, destination, max_bytes=512 * 1024 * 1024, max_files=2048):
    destination = Path(destination)
    require(not destination.exists(), f'Extraction target already exists: {destination}')
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        require(len(entries) <= max_files, 'Archive has too many entries')
        require(sum(i.file_size for i in entries) <= max_bytes, 'Archive expands beyond limit')
        names = set()
        for item in entries:
            name = item.filename.rstrip('/') if item.is_dir() else item.filename
            safe_path(name)
            require(name not in names, 'Duplicate archive entry')
            names.add(name)
            mode = item.external_attr >> 16
            require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR),
                    'Archive contains a special file')
            require(not item.flag_bits & 1, 'Encrypted archive')
        destination.mkdir(parents=True)
        for item in entries:
            target = destination / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(item))


def validate_run(run, workflow, master_sha, expected_sha=None, expected_attempt=None):
    require(run.get('repository', {}).get('full_name') == REPOSITORY, 'Wrong build repository')
    require(run.get('head_repository', {}).get('full_name') == REPOSITORY, 'Fork build is not publishable')
    require(run.get('path') == BUILD_WORKFLOW and workflow.get('path') == BUILD_WORKFLOW
            and run.get('workflow_id') == workflow.get('id'), 'Wrong build workflow')
    require(run.get('event') in ('push', 'workflow_dispatch') and run.get('head_branch') == 'master'
            and not run.get('pull_requests'), 'Only trusted master builds are publishable')
    require(run.get('status') == 'completed' and run.get('conclusion') == 'success', 'Build is not successful and complete')
    require(valid_sha(run.get('head_sha')) and run['head_sha'] == master_sha, 'Build is stale relative to master')
    require(isinstance(run.get('run_attempt'), int) and run['run_attempt'] > 0, 'Missing build attempt')
    if expected_sha is not None:
        require(run['head_sha'] == expected_sha, 'Source commit changed')
    if expected_attempt is not None:
        require(run['run_attempt'] == expected_attempt, 'Build attempt changed; native verification must be refreshed')
    return {k: run[k] for k in ('id', 'run_attempt', 'head_sha', 'workflow_id', 'html_url')}


def select_artifacts(run, artifacts):
    result = {}
    for kind, family in (('regular', 'Monofuki'), ('nerd', 'MonofukiNerdFont')):
        name = f'{family}-{run["head_sha"]}-attempt-{run["run_attempt"]}'
        found = [a for a in artifacts if a.get('name') == name]
        require(len(found) == 1, f'Missing or ambiguous current-attempt artifact: {name}')
        a = found[0]
        require(not a.get('expired') and isinstance(a.get('digest'), str)
                and re.fullmatch(r'sha256:[0-9a-f]{64}', a['digest']), 'Expired artifact or missing digest')
        origin = a.get('workflow_run', {})
        require(origin.get('id') == run['id'] and origin.get('head_sha') == run['head_sha']
                and origin.get('head_branch') == 'master', 'Artifact origin mismatch')
        require(isinstance(a.get('size_in_bytes'), int) and 0 < a['size_in_bytes'] < 150 * 1024 * 1024, 'Artifact size outside limit')
        result[kind] = {k: a[k] for k in ('id', 'name', 'digest', 'size_in_bytes')}
    require(result['regular']['id'] != result['nerd']['id'], 'Duplicate artifact ID')
    return result


def expected_fonts(root):
    root = Path(root)
    paths = []
    for kind, family, styles, suffixes in (
        ('regular', 'Monofuki', REGULAR, ('.otf', '.ttf', '-hinted.ttf', '.woff2', '-hinted.woff2')),
        ('nerd', 'MonofukiNerdFont', NERD, ('.otf', '.ttf', '.woff2')),
    ):
        expected = {f'{family}-{style}{suffix}' for style in styles for suffix in suffixes}
        actual = {p.name for p in (root / kind).iterdir() if p.suffix in ('.otf', '.ttf', '.woff2')}
        require(actual == expected, f'Incomplete or extra {kind} fonts')
        paths.extend(root / kind / name for name in sorted(expected))
    return paths


def contract(run, artifacts, fonts, script_root):
    expected_fonts(fonts)
    return {'schema_version': 1, 'repository': REPOSITORY, 'run': run, 'artifacts': artifacts,
            'input_files': {kind: inventory(Path(fonts) / kind) for kind in ('regular', 'nerd')},
            'script_sha256': {name: file_hash(Path(script_root) / name) for name in SCRIPTS}}


def png_dimensions(path):
    data = Path(path).read_bytes()
    require(len(data) >= 33 and data[:16] == b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR', f'Invalid PNG: {path.name}')
    width, height = struct.unpack('>II', data[16:24])
    require(0 < width <= 16384 and 0 < height <= 16384, 'PNG dimensions outside limit')
    return width, height


def validate_reports(evidence, fonts, script_root, host):
    from fontTools.ttLib import TTFont
    evidence, fonts = Path(evidence), Path(fonts)
    paths = expected_fonts(fonts)
    otfs = [p for p in paths if p.suffix == '.otf']
    native = [p for p in paths if p.suffix in ('.otf', '.ttf')]
    hashes = {p.name: file_hash(p) for p in native}
    font_data = {}
    for path in native:
        with TTFont(path) as font:
            font_data[path.name] = {'cmap': len(font.getBestCmap()), 'name': font['name'].getDebugName(6)}
    reports = {name: read_json(evidence / name) for name in REPORTS}
    snapshot = reports['coretext.json']
    catalog = read_json(fonts / 'nerd/character-catalog.json')
    require(snapshot.get('font_sha256') == catalog['font_sha256'] == {
        'regular': hashes['Monofuki-Regular.otf'], 'nerd': hashes['MonofukiNerdFont-Regular.otf']}, 'Fallback input mismatch')
    require(snapshot.get('renderer') == 'CoreText' and snapshot.get('architecture') == host['architecture'], 'Wrong native renderer or architecture')
    require(host['product_version'] in snapshot.get('macos', ''), 'Fallback macOS version mismatch')
    expected = {(item['codepoint'], kind) for item in catalog['fallback'] for kind in ('regular', 'nerd') if not item[kind]}
    records = snapshot.get('records', [])
    require(len(records) == len(expected) and {(r['codepoint'], r['variant']) for r in records} == expected, 'Incomplete fallback coverage')
    require(snapshot.get('columns') == 16 and snapshot.get('cell') == 128, 'Unexpected fallback grid')
    for kind in ('regular', 'nerd'):
        count = sum(variant == kind for _, variant in expected)
        require(snapshot.get('counts', {}).get(kind) == count, 'Fallback count mismatch')
        for theme in ('light', 'dark'):
            require(png_dimensions(evidence / f'{kind}-{theme}.png') == (2048, max(128, ((count + 15)//16)*128)), 'Fallback atlas dimensions mismatch')
    for name in REPORTS[1:]:
        require(host['product_version'] in reports[name].get('platform', ''), f'Host version mismatch: {name}')

    tuned = reports['tuned-coretext-proof.json']
    sample = 'minimum Toffee VVA VYA WYA ÁÉÅÜ ÇĽ gq07{}'
    require(tuned.get('sample') == sample, 'Wrong tuned sample')
    expected_regular = {p.name for p in otfs if p.parent.name == 'regular'}
    rows = tuned.get('fonts', [])
    require(len(rows) == 4 and {r['file'] for r in rows} == expected_regular, 'Incomplete tuned native styles')
    for row in rows:
        require(row['sha256'] == hashes[row['file']] and row['postscript_name'] == font_data[row['file']]['name'], 'Tuned font identity mismatch')
        require(abs(row['ascent_font_units'] - 880) < .01 and abs(row['descent_font_units'] - 270) < .01, 'Native vertical metrics changed')
        modes = row.get('modes', [])
        require(len(modes) == 2 and {m['kern_default'] for m in modes} == {True, False}, 'Missing native feature mode')
        for mode in modes:
            require(mode['actual_fonts'] == [row['postscript_name']], 'Native sample used fallback')
            advances, positions, shifts = (mode[k] for k in ('run_advance_widths_font_units', 'positions_font_units', 'shifts_font_units'))
            require(len(advances) == len(positions) == len(shifts) == len(sample), 'Partial native sample')
            # CoreText reports distances between positioned glyph origins here;
            # XPlacement therefore changes these distances even with fixed hmtx.
            next_positions = positions[1:] + [mode['total_font_units']]
            require(all(math.isfinite(v) and abs(v - (next_positions[i] - positions[i])) < .01
                        for i, v in enumerate(advances)), 'Inconsistent native advances and positions')
            require(abs(mode['total_font_units'] - 575*len(sample)) < .01, 'Native total advance changed')
            require(all(math.isfinite(v) and abs(v - (positions[i] - i*575)) < .01 for i, v in enumerate(shifts)), 'Inconsistent native positions')
            if not mode['kern_default']:
                require(all(abs(v) < .01 for v in shifts) and all(abs(v - 575) < .01 for v in advances), 'Strict native positioning changed')
    png_dimensions(evidence / 'tuned-coretext-proof.png')

    small = reports['small-n-coretext.json']
    rows = small.get('results', [])
    expected = {(p.name, size, cp) for p in native for size in (12, 20, 64, 128) for cp in ('U+207F', 'U+2099')}
    require(small.get('checks') == len(rows) == len(expected) and {(r['file'], r['size'], r['codepoint']) for r in rows} == expected, 'Partial small-n coverage')
    for row in rows:
        require(row['sha256'] == hashes[row['file']] and row['actual_font'] == font_data[row['file']]['name'], 'Small-n font mismatch')
        require(row['ink_pixels'] > 0 and abs(row['advance'] - 575*row['size']/1024) < .001, 'Invisible or wrong-advance small n')
    visible = reports['export-visibility.json']
    rows = visible.get('results', [])
    expected = {p.name for p in native if p.suffix == '.ttf'}
    require(visible.get('size') == 64 and len(rows) == len(expected) and {r['file'] for r in rows} == expected, 'Partial export visibility coverage')
    for row in rows:
        source = row['file'].removesuffix('.ttf').replace('-hinted', '') + '.otf'
        # CTFontCopyCharacterSet also includes virtual control mappings (nine on
        # macOS 27); the native script visits the complete returned set. Do not
        # mistake those platform additions for an altered font cmap.
        require(font_data[source]['cmap'] <= row['mapped'] <= 0x110000
                and 0 < row['otf_visible'] <= row['mapped'] and row['lost'] == 0,
                'Failed or incomplete visibility audit')

    emoji = reports['emoji-coretext.json']
    cases = read_json(fonts / 'nerd/emoji-cases.json')
    rows = emoji.get('results', [])
    expected_previews = {'Menlo-Regular.png'} | {font_data[p.name]['name'] + '.png' for p in otfs}
    require(set(inventory(evidence / 'emoji-previews')) == expected_previews, 'Missing or extra emoji preview files')
    expected_sources = {'system baseline'} | {f'fonts/{p.parent.name}/{p.name}' for p in otfs}
    require(len(rows) == len(cases)*len(expected_sources), 'Partial emoji coverage')
    for source in expected_sources:
        selected = [r for r in rows if r['source'] == source]
        require([r['probe'] for r in selected] == cases, 'Missing or altered emoji probes')
        expected_name = 'Menlo-Regular' if source == 'system baseline' else font_data[Path(source).name]['name']
        require(all(r['requested_font'] == expected_name for r in selected), 'Emoji font mismatch')
        png_dimensions(evidence / 'emoji-previews' / f'{expected_name}.png')
    subprocess.run([sys.executable, str(Path(script_root) / 'check_emoji_results.py'), str(evidence / 'emoji-coretext.json')], check=True, capture_output=True)


def validate_evidence(evidence, expected, fonts, script_root):
    evidence = Path(evidence)
    manifest = read_json(evidence / 'manifest.json')
    require(manifest.get('contract') == expected, 'Evidence does not match the exact build, attempt, files, and native scripts')
    require(manifest.get('supervisor') == OWNER, 'Wrong supervising identity')
    require(manifest.get('status') == 'passed' and manifest.get('steps') == [{'name': name, 'exit_code': 0} for name in STEPS], 'Missing, partial, or failed native steps')
    host = manifest.get('host', {})
    require(host.get('system') == 'Darwin' and host.get('architecture') in ('arm64', 'x86_64')
            and re.fullmatch(r'\d+\.\d+(?:\.\d+)?', host.get('product_version', ''))
            and host.get('build_version') and host.get('swift_version'), 'Missing native host provenance')
    require(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', manifest.get('completed_at', '')), 'Missing completion timestamp')
    files = inventory(evidence)
    files.pop('manifest.json')
    require(files == manifest.get('output_sha256'), 'Missing, extra, or corrupt evidence files')
    allowed = set(REPORTS) | {f'{kind}-{theme}.png' for kind in ('regular', 'nerd') for theme in ('dark', 'light')} | {'tuned-coretext-proof.png'}
    for name in files:
        require(name in allowed or re.fullmatch(r'emoji-previews/(?:Menlo-Regular|Monofuki[A-Za-z0-9-]*)\.png', name), 'Unexpected evidence payload')
    require(allowed <= files.keys(), 'Missing native results')
    validate_reports(evidence, fonts, script_root, host)
    return manifest


def bundle_evidence(evidence, output):
    evidence = Path(evidence)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(inventory(evidence)):
            item = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = (stat.S_IFREG | 0o644) << 16
            z.writestr(item, (evidence / name).read_bytes())
    require(Path(output).stat().st_size <= MAX_EVIDENCE, 'Native evidence bundle exceeds size limit')
