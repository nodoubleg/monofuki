#!/usr/bin/env python3
"""Assemble pinned upstream sources and owned overlays; never save over upstream."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import fontforge
from glyph_overrides import apply_overrides, digest
from upstream_decisions import binding, accepted_action, replace_identity
from add_braille import update as add_braille
from add_terminal_symbols import make_symbols, update as add_symbols
from fetch_build_dependencies import fetch, MANIFEST, ROOT

STYLES = ('Regular', 'Italic', 'Bold', 'Bold-Italic')
OUTPUT = ROOT / '.font-build' / 'assembled'
RECORD = re.compile(r'^StartChar: .*?^EndChar\n', re.MULTILINE | re.DOTALL)


def records(text):
    items = RECORD.findall(text)
    result = {r.splitlines()[0].removeprefix('StartChar: '): r for r in items}
    if len(items) != len(result):
        raise ValueError('Duplicate glyph names')
    count = re.search(r'^BeginChars: (\d+) (\d+)$', text, re.M)
    if not count or int(count[2]) != len(items):
        raise ValueError('Incorrect SFD record count')
    return result


def encoding(record):
    return tuple(map(int, re.search(r'^Encoding: (-?\d+) (-?\d+) (\d+)$', record, re.M).groups()))


def check_references(text):
    rs = records(text)
    by_id = {encoding(r)[2]: (name, encoding(r)[1]) for name, r in rs.items()}
    if len(by_id) != len(rs):
        raise ValueError('Duplicate glyph IDs')
    edges = {name: [] for name in rs}
    for name, record in rs.items():
        for gid, cp in re.findall(r'^Refer: (\d+) (-?\d+) ', record, re.M):
            if int(gid) not in by_id or by_id[int(gid)][1] != int(cp):
                raise ValueError(f'{name}: unresolved or inconsistent reference {gid}/{cp}')
            edges[name].append(by_id[int(gid)][0])
    visiting, visited = set(), set()
    def visit(name):
        if name in visiting:
            raise ValueError(f'Cyclic glyph reference: {name}')
        if name in visited:
            return
        visiting.add(name)
        for child in edges[name]:
            visit(child)
        visiting.remove(name)
        visited.add(name)
    for name in edges:
        visit(name)


def restore_arrows(target, source, points):
    sr, tr = records(source), records(target)
    source_ids = {encoding(r)[2]: name for name, r in sr.items()}
    target_ids = {name: encoding(r)[2] for name, r in tr.items()}
    target_cp = {encoding(r)[1] for r in tr.values()}
    additions = {}
    for cp in points:
        if cp in target_cp:
            raise ValueError(f'Arrow U+{cp:04X} now exists upstream: review overlay')
        record = next(r for r in sr.values() if encoding(r)[1] == cp)
        def remap(match):
            name = source_ids[int(match[1])]
            if name not in target_ids:
                raise ValueError(f'Missing arrow component {name}')
            return f'Refer: {target_ids[name]} '
        additions[cp] = re.sub(r'^Refer: (\d+) ', remap, record, flags=re.M)
    return add_symbols(target, additions)


def renamed(text, style):
    values = {'FontName': f'Monofuki-{style}', 'FullName': f'Monofuki {style.replace("-", " ")}', 'FamilyName': 'Monofuki'}
    for field, value in values.items():
        text, count = re.subn(rf'^{field}: .*$', f'{field}: {value}', text, flags=re.M)
        if count != 1:
            raise ValueError(f'Expected one {field}')
    return text


def check_preservation(base, result, style, overrides=None):
    overrides = overrides or {}
    old, new = records(base), records(result)
    for name, record in old.items():
        if new.get(name) != overrides.get(name, record):
            raise ValueError(f'{style}: inherited glyph changed: {name}')
    header = lambda s: re.sub(r'^BeginChars:.*$', '', s[:s.index('StartChar:')], flags=re.M)
    if header(renamed(base, style)) != header(result):
        raise ValueError(f'{style}: unexpected metadata or line metric change')
    check_references(result)
    return len(set(old) - set(overrides))


def glyph_inventory(base, result, catalog, arrows, authored):
    upstream, final = records(base), records(result)
    by_id = {encoding(r)[2]: name for name, r in final.items()}
    donors = {int(item['codepoint'], 16): item for item in catalog['additions']}
    arrow_points = {int(cp, 16) for cp in arrows['codepoints']} if arrows else set()
    inventory = []
    for name, record in final.items():
        slot, cp, gid = encoding(record)
        if name in authored:
            source = authored[name]
        elif name in upstream:
            source = {'kind': 'upstream', 'record_sha256': digest(upstream[name])}
        elif 0x2800 <= cp <= 0x28FF:
            source = {'kind': 'generated-braille', 'generator': 'script_helper/add_braille.py',
                      'generator_sha256': digest((ROOT / 'script_helper/add_braille.py').read_text())}
        elif cp in arrow_points:
            source = {'kind': 'same-weight-upstream-arrow', 'source_style': arrows['source_style']}
        elif cp in donors:
            source = {'kind': 'donor', **donors[cp]}
        else:
            raise ValueError(f'No glyph provenance: {name}')
        inventory.append({'glyph_name': name, 'glyph_id': gid, 'encoding_slot': slot,
                          'codepoint': f'{cp:04X}' if cp >= 0 else None,
                          'alternate_unicode_records': re.findall(r'^AltUni.*$', record, re.M),
                          'dependencies': [by_id[int(gid)] for gid in re.findall(r'^Refer: (\d+) ', record, re.M)],
                          'record_sha256': digest(record), 'source': source})
    return inventory


def assemble(output=OUTPUT, check=False, recipe=None, decisions=None, manifest=None, require_coverage=True):
    recipe = recipe if recipe is not None else json.loads((ROOT / 'src/overlays.json').read_text())
    decisions = decisions if decisions is not None else json.loads((ROOT / 'src/upstream-decisions.json').read_text())['decisions']
    manifest = manifest or MANIFEST
    if recipe['braille'] != {'generator': 'script_helper/add_braille.py', 'range': ['2800', '28FF']}:
        raise ValueError('Unsupported Braille recipe; update generator and checks together')
    if recipe['family'] != 'Monofuki':
        raise ValueError('Unexpected family or unimplemented authored override: review assembler')
    for name, expected in manifest['vendored_files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Pinned vendored input changed: {name}')
    if any(manifest['assets']['upstream-' + style]['revision'] != manifest['upstream']['revision'] for style in STYLES):
        raise ValueError('Upstream styles must share the explicitly pinned revision')
    bases = {style: fetch(f'upstream-{style}', manifest=manifest).read_text() for style in STYLES}
    catalog = json.loads((ROOT / recipe['symbols']).read_text())
    original_catalog = json.dumps(catalog, sort_keys=True)
    symbols = make_symbols(catalog)
    if json.dumps(catalog, sort_keys=True) != original_catalog:
        raise ValueError('Donor provenance changed; review and update manifest explicitly')
    owned = set(range(0x2800, 0x2900)) | set(symbols)
    provenance = {'family': 'Monofuki', 'upstream': manifest['upstream'],
                  'fontforge_version': fontforge.version(), 'inputs': manifest['assets'],
                  'recipe_canonical_sha256': digest(json.dumps(recipe, sort_keys=True)),
                  'decisions_canonical_sha256': digest(json.dumps(decisions, sort_keys=True)),
                  'modifications': 'Renamed family; generated Braille; selected donor glyphs scaled, positioned and merged; same-weight upstream arrows restored in italic styles.',
                  'styles': {}}
    outputs, inventory = {}, {'schema_version': 1, 'upstream': manifest['upstream'], 'styles': {}}
    for style, base in bases.items():
        base_by_cp = {encoding(r)[1]: r for r in records(base).values() if encoding(r)[1] >= 0}
        collisions = set(base_by_cp) & owned
        result = add_braille(base)
        braille_by_cp = {encoding(r)[1]: r for r in records(result).values() if 0x2800 <= encoding(r)[1] <= 0x28FF}
        collision_overrides, collision_provenance = {}, {}
        for cp in sorted(collisions):
            kind = 'braille' if cp in braille_by_cp else 'donor'
            overlay = braille_by_cp[cp] if kind == 'braille' else symbols[cp]
            expected = binding(style, kind, cp, base_by_cp[cp], overlay, manifest['upstream']['revision'])
            action = accepted_action(decisions, expected)
            if kind == 'braille':
                result = result.replace(braille_by_cp[cp], base_by_cp[cp], 1)
            if action == 'keep-overlay':
                replacement = replace_identity(overlay, base_by_cp[cp])
                result = result.replace(base_by_cp[cp], replacement, 1)
                name = base_by_cp[cp].splitlines()[0][11:]
                collision_overrides[name] = replacement
                collision_provenance[name] = {**expected, 'kind': 'accepted-' + kind, 'action': action,
                    'provider': next((item for item in catalog['additions'] if int(item['codepoint'], 16) == cp), {'generator': 'script_helper/add_braille.py'})}
        arrows = recipe['restore_from_same_weight_upright'].get(style)
        if arrows:
            result = restore_arrows(result, bases[arrows['source_style']], [int(cp, 16) for cp in arrows['codepoints']])
        result = renamed(add_symbols(result, {cp: record for cp, record in symbols.items() if cp not in collisions}), style)
        result, overrides, authored = apply_overrides(result, style, recipe['authored_overrides'], manifest['upstream']['revision'], ROOT)
        overrides = {**collision_overrides, **overrides}
        authored = {**collision_provenance, **authored}
        unchanged = check_preservation(base, result, style, overrides)
        inventory['styles'][style] = glyph_inventory(base, result, catalog, arrows, authored)
        outputs[style] = result
        provenance['styles'][style] = {'inherited_records_unchanged': unchanged,
                                      'assembled_sha256': hashlib.sha256(result.encode()).hexdigest(),
                                      'braille': 256, 'donor_symbols': len(symbols), 'restored_arrows': arrows, 'authored_glyphs': sum(v.get('kind') == 'authored' for v in authored.values())}
        target = output / f'monofuki-{style}.sfd'
        if check:
            if not target.is_file() or target.read_text() != result:
                raise ValueError(f'Stale/missing assembly: {target}; run assemble_sources.py')
        else:
            output.mkdir(parents=True, exist_ok=True)
            target.write_text(result)
        print(f'PASS {style}: {unchanged} inherited records/metadata preserved; {len(records(result))} assembled records')
    coverages = [{encoding(r)[1] for r in records(s).values() if encoding(r)[1] >= 0} for s in outputs.values()]
    if require_coverage and any(c != coverages[0] for c in coverages[1:]):
        raise ValueError('Style coverage differs')
    if not check:
        (output / 'glyph-provenance.json').write_text(json.dumps(inventory, indent=2) + '\n')
        (output / 'source-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.output.resolve() == ROOT / 'src':
        parser.error('src contains recipes, not generated sources')
    assemble(args.output, args.check)
