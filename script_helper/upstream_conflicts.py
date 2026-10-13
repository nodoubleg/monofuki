#!/usr/bin/env python3
"""Report, check and explicitly apply fingerprint-bound upstream ownership choices."""
import argparse
import copy
import hashlib
import html
import json
import re
import tempfile
from pathlib import Path
import fontforge
from assemble_sources import (STYLES, records, encoding, renamed, assemble, add_braille,
                              make_symbols, ROOT)
from fetch_build_dependencies import fetch
from glyph_overrides import digest, apply_overrides
from upstream_decisions import binding, accepted_action, overlay_hash
from review_upstream import compare


class SVGPen:
    def __init__(self): self.parts = []
    def moveTo(self, p): self.parts.append(f'M{p[0]} {p[1]}')
    def lineTo(self, p): self.parts.append(f'L{p[0]} {p[1]}')
    def curveTo(self, *points):
        if len(points) != 3: raise ValueError('Expected cubic source contours')
        self.parts.append('C' + ' '.join(f'{p[0]} {p[1]}' for p in points))
    def qCurveTo(self, *points):
        if len(points) != 2 or points[-1] is None: raise ValueError('Expected simple quadratic source contours')
        self.parts.append('Q' + ' '.join(f'{p[0]} {p[1]}' for p in points))
    def closePath(self): self.parts.append('Z')
    def endPath(self): pass
    def addComponent(self, *args): raise ValueError('Unresolved visual specimen component')


def export_svg(glyph, path):
    bounds = glyph.boundingBox()
    glyph.unlinkRef()
    pen = SVGPen(); glyph.draw(pen)
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-100 -1030 775 1470"><path fill="#201f26" transform="scale(1,-1)" d="' + ' '.join(pen.parts) + '"/></svg>')
    return bounds


def json_hash(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')))


def by_cp(text):
    return {encoding(r)[1]: r for r in records(text).values() if encoding(r)[1] >= 0}


def describe(record):
    if record is None:
        return None
    return {'glyph_name': record.splitlines()[0][11:], 'sha256': digest(record),
            'encoding': list(encoding(record)),
            'width': re.search(r'^Width:.*$', record, re.M)[0],
            'references': re.findall(r'^Refer:.*$', record, re.M), 'record': record}


def ownership_items(style, old, new, current, recipe, symbols, revision, accepted, root=ROOT, effective=None):
    old_records, new_records, current_records = records(old), records(new), records(current)
    old_cp, new_cp, current_cp = by_cp(old), by_cp(new), by_cp(current)
    effective_records = records(effective if effective is not None else new)
    generated = {cp: r for cp, r in by_cp(add_braille(new)).items() if 0x2800 <= cp <= 0x28FF}
    items = []
    for cp, overlay in sorted({**generated, **symbols}.items()):
        if cp not in new_cp:
            continue
        kind = 'braille' if 0x2800 <= cp <= 0x28FF else 'donor'
        expected = binding(style, kind, cp, new_cp[cp], overlay, revision)
        try:
            action = accepted_action(accepted, expected)
        except ValueError:
            action = None
        items.append({'kind': kind, 'binding': expected, 'requires_decision': action is None,
                      'accepted_action': action, 'old': describe(old_cp.get(cp)),
                      'candidate': describe(new_cp[cp]), 'current': describe(current_cp.get(cp)),
                      'overlay': describe(overlay), 'dependency_changes': []})
    owned = {e['glyph_name']: e for e in recipe['authored_overrides'] if e['style'] == style}
    for name, entry in sorted(owned.items()):
        overlay = (root / entry['source']).read_text()
        if digest(overlay) != entry['source_sha256']:
            raise ValueError(f'{name}: authored file differs from recipe; review/edit its source hash first')
        candidate = new_records.get(name)
        cp = -1 if entry['codepoint'] is None else int(entry['codepoint'], 16)
        if candidate is None and cp >= 0:
            candidate = new_cp.get(cp)
        dependency_changes = []
        for dep in entry['dependencies']:
            dep_name = dep['glyph_name']
            new_dep = ((root / owned[dep_name]['source']).read_text() if dep_name in owned else effective_records.get(dep_name))
            if new_dep is None or digest(new_dep) != dep['expected_source_sha256']:
                dependency_changes.append({'glyph_name': dep_name, 'expected_sha256': dep['expected_source_sha256'],
                                           'candidate_sha256': digest(new_dep) if new_dep else None,
                                           'old': describe(old_records.get(dep_name)), 'candidate': describe(new_dep)})
        effective_base = effective_records.get(name)
        if effective_base is None and cp >= 0:
            effective_base = next((r for r in effective_records.values() if encoding(r)[1] == cp), None)
        old_expected = entry['expected_base_sha256']
        changed = (digest(effective_base) if effective_base else None) != old_expected
        expected = {'style': style, 'kind': 'authored', 'glyph_name': name,
                    'codepoint': entry['codepoint'], 'candidate_revision': revision,
                    'candidate_sha256': digest(effective_base) if effective_base else None,
                    'candidate_upstream_sha256': digest(candidate) if candidate else None,
                    'overlay_sha256': digest(overlay), 'dependency_changes': [{key: dep[key] for key in ('glyph_name', 'expected_sha256', 'candidate_sha256')} for dep in dependency_changes]}
        items.append({'kind': 'authored', 'binding': expected, 'requires_decision': changed or bool(dependency_changes),
                      'accepted_action': None if changed or dependency_changes else 'keep-overlay',
                      'old': describe(old_records.get(name)), 'candidate': describe(candidate),
                      'current': describe(current_records.get(name)), 'overlay': describe(overlay),
                      'candidate_base': describe(effective_base), 'entry': entry, 'dependency_changes': dependency_changes})
    for item in items:
        item['id'] = json_hash(item['binding'])
    return items


def make_report(before_path, candidate_path, assembled, output):
    before, candidate = (json.loads(p.read_text()) for p in (before_path, candidate_path))
    # This command handles an upstream update, keeping other inputs fixed.
    old_other = {k: v for k, v in before['assets'].items() if not k.startswith('upstream-')}
    new_other = {k: v for k, v in candidate['assets'].items() if not k.startswith('upstream-')}
    if old_other != new_other:
        raise ValueError('Review donor/patcher changes separately from this upstream update')
    recipe_path, decisions_path = ROOT / 'src/overlays.json', ROOT / 'src/upstream-decisions.json'
    recipe = json.loads(recipe_path.read_text())
    accepted = json.loads(decisions_path.read_text())['decisions']
    catalog = json.loads((ROOT / recipe['symbols']).read_text())
    symbols = make_symbols(catalog)
    donor_sources = {item['codepoint']: item for item in catalog['additions']}
    snapshot_paths = [ROOT / 'script_helper/build_dependencies.json', before_path, candidate_path,
                      recipe_path, decisions_path, ROOT / recipe['symbols'],
                      *(ROOT / e['source'] for e in recipe['authored_overrides'])]
    report = {'schema_version': 1, 'before_lock': before, 'candidate_lock': candidate,
              'recipe': recipe, 'accepted': accepted, 'styles': {}, 'items': []}
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    provisional = copy.deepcopy(accepted)
    for style in STYLES:
        new = fetch('upstream-' + style, manifest=candidate).read_text()
        for item in ownership_items(style,new,new,new,{'authored_overrides':[]},symbols,candidate['upstream']['revision'],accepted):
            if item['requires_decision']:
                b=item['binding']
                provisional=[d for d in provisional if (d['style'],d['kind'],d['codepoint'])!=(b['style'],b['kind'],b['codepoint'])]
                provisional.append({**b,'action':'adopt-upstream'})
    with tempfile.TemporaryDirectory() as temporary:
        pre_recipe=copy.deepcopy(recipe);pre_recipe['authored_overrides']=[]
        assemble(Path(temporary),recipe=pre_recipe,decisions=provisional,manifest=candidate,require_coverage=False)
        effective={style:(Path(temporary)/f'monofuki-{style}.sfd').read_text() for style in STYLES}
    for style in STYLES:
        old_path, new_path = (fetch('upstream-' + style, manifest=m) for m in (before, candidate))
        current_path = assembled / f'monofuki-{style}.sfd'
        old, new, current = old_path.read_text(), new_path.read_text(), current_path.read_text()
        snapshot_paths.append(current_path)
        report['styles'][style] = compare(old, new)
        items = ownership_items(style, old, new, current, recipe, symbols, candidate['upstream']['revision'], accepted, root=ROOT, effective=effective[style])
        for item in items:
            cp = item['binding']['codepoint']
            if item['kind'] == 'donor':
                provider = donor_sources[cp]
                item['source'] = {**provider, 'input': candidate['assets'][provider['donor']]}
            elif item['kind'] == 'authored':
                item['source'] = item['entry']
            else:
                item['source'] = {'generator': 'script_helper/add_braille.py'}
        report['items'].extend(items)
        font_paths = {'old': old_path, 'candidate': new_path, 'current': current_path}
        opened = {str(path): fontforge.open(str(path)) for path in set(font_paths.values())}
        fonts = {label: opened[str(path)] for label, path in font_paths.items()}
        try:
            for item in items:
                cells = []
                for label in ('old', 'candidate', 'current'):
                    data = item[label]
                    if data is None:
                        cells.append('<td>Absent</td>')
                        continue
                    name = data['glyph_name']; glyph = fonts[label][name]
                    filename = f"{item['id']}-{label}.svg"
                    bounds = export_svg(glyph, output / filename)
                    cells.append(f'<td><img src="{filename}" alt="{html.escape(name)}"><br>{html.escape(data["width"])}<br>{html.escape(str(bounds))}</td>')
                title = f"{style} {item['binding']['glyph_name']} {item['binding']['codepoint']} ({item['kind']})"
                rows.append(f'<tr><th>{html.escape(title)}<br><code>{item["id"]}</code></th>{"".join(cells)}</tr>')
        finally:
            for font in opened.values(): font.close()
    report['snapshots'] = [{'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in dict.fromkeys(snapshot_paths)]
    report['id'] = json_hash(report)
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'choices.json').write_text(json.dumps({'report_id': report['id'], 'choices': [{'id': i['id'], 'action': 'CHOOSE'} for i in report['items'] if i['requires_decision']]}, indent=2) + '\n')
    (output / 'specimen.html').write_text('<!doctype html><meta charset="utf-8"><title>Upstream ownership review</title><style>body{font:16px system-ui}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:12px}img{width:180px;height:200px}code{font-size:10px;overflow-wrap:anywhere}th{max-width:300px}</style><h1>Old upstream / candidate upstream / current custom glyph</h1><p>Compare outlines, widths and bounds. Decisions are recorded separately in choices.json.</p><table><tr><th>Glyph</th><th>Old upstream</th><th>Candidate upstream</th><th>Current custom</th></tr>' + ''.join(rows) + '</table>')
    print(f"Report {report['id']}: {sum(i['requires_decision'] for i in report['items'])} choices required; {output / 'specimen.html'}")
    return report


def resolve(report, choices, root=ROOT):
    expected_id = json_hash({k: v for k, v in report.items() if k != 'id'})
    if report['id'] != expected_id or choices['report_id'] != expected_id:
        raise ValueError('Stale or modified review/decision fingerprint')
    for snapshot in report['snapshots']:
        if hashlib.sha256(Path(snapshot['path']).read_bytes()).hexdigest() != snapshot['sha256']:
            raise ValueError(f"Stale review input: {snapshot['path']}")
    selected = {c['id']: c for c in choices['choices']}
    if len(selected) != len(choices['choices']) or set(selected) - {i['id'] for i in report['items']}:
        raise ValueError('Duplicate or unknown decision ID')
    recipe, decisions = copy.deepcopy(report['recipe']), copy.deepcopy(report['accepted'])
    for item in report['items']:
        choice = selected.get(item['id'])
        if choice is None and item['requires_decision']:
            raise ValueError(f"Unresolved ownership choice: {item['id']}")
        action = choice['action'] if choice else item['accepted_action']
        if action not in ('adopt-upstream', 'keep-overlay', 'revise-overlay'):
            raise ValueError('Choose adopt-upstream, keep-overlay, or revise-overlay explicitly')
        b = item['binding']
        if item['kind'] != 'authored' and action != 'revise-overlay':
            decisions = [d for d in decisions if (d['style'], d['kind'], d['codepoint']) != (b['style'], b['kind'], b['codepoint'])]
            decisions.append({**b, 'action': action, 'review_fingerprint': report['id']})
            continue
        old_entry = item.get('entry')
        if old_entry:
            recipe['authored_overrides'] = [e for e in recipe['authored_overrides'] if (e['style'], e['glyph_name']) != (old_entry['style'], old_entry['glyph_name'])]
        if choice and item['kind'] == 'authored':
            decisions = [d for d in decisions if (d['style'], d['kind'], d.get('glyph_name')) != (b['style'], 'authored', b['glyph_name'])]
            decisions.append({**b, 'action': action, 'review_fingerprint': report['id']})
        if action == 'adopt-upstream':
            if item['candidate'] is None:
                raise ValueError('Cannot adopt a removed glyph; revise its references explicitly')
            continue
        entry = copy.deepcopy(choice['override'] if action == 'revise-overlay' else old_entry)
        if entry is None:
            raise ValueError('Revising a donor requires an explicit authored override entry')
        if entry['style'] != b['style'] or entry['codepoint'] != b['codepoint']:
            raise ValueError('Revised override changes style or character identity')
        candidate_base = item.get('candidate_base', item['candidate'])
        if candidate_base and entry['glyph_name'] != candidate_base['glyph_name']:
            raise ValueError('Candidate glyph name differs; revise the authored identity explicitly')
        if action == 'keep-overlay':
            # Only an explicit keep (or an unchanged reviewed binding) rebases
            # existing ownership. A revision supplies its own exact guards.
            entry['expected_upstream_revision'] = report['candidate_lock']['upstream']['revision']
            entry['expected_base_sha256'] = b['candidate_sha256']
            entry['operation'] = 'replace' if candidate_base else 'add'
            changes = {d['glyph_name']: d['candidate_sha256'] for d in item['dependency_changes']}
            for dep in entry['dependencies']:
                if dep['glyph_name'] in changes:
                    if changes[dep['glyph_name']] is None:
                        raise ValueError('Referenced component was removed; revise the override/dependency explicitly')
                    dep['expected_source_sha256'] = changes[dep['glyph_name']]
        if item['kind'] != 'authored':
            # Let upstream own the base slot, then apply the explicitly authored revision.
            decisions = [d for d in decisions if (d['style'], d['kind'], d['codepoint']) != (b['style'], b['kind'], b['codepoint'])]
            decisions.append({**b, 'action': 'adopt-upstream', 'review_fingerprint': report['id']})
        recipe['authored_overrides'].append(entry)
    recipe['authored_overrides'].sort(key=lambda e: (e['style'], e['glyph_name']))
    return recipe, decisions


def checked_apply(report_path, choices_path, write=False):
    report, choices = (json.loads(p.read_text()) for p in (report_path, choices_path))
    target_paths = {ROOT / 'src/overlays.json', ROOT / 'src/upstream-decisions.json',
                    ROOT / 'script_helper/build_dependencies.json'}
    snapshotted = {Path(s['path']).resolve() for s in report['snapshots']}
    if not {p.resolve() for p in target_paths}.issubset(snapshotted):
        raise ValueError('Review must snapshot every live apply target; generate a fresh report')
    recipe, decisions = resolve(report, choices)
    with tempfile.TemporaryDirectory() as directory:
        # The assembler must validate the reviewed/supplied fingerprints as-is.
        # Refreshing them here would turn drift into silently accepted ownership.
        assemble(Path(directory)/'final', recipe=recipe, decisions=decisions, manifest=report['candidate_lock'])
    if write:
        # Also catch inputs edited while candidate assembly was running.
        resolve(report, choices)
        targets = {ROOT / 'src/overlays.json': recipe,
                   ROOT / 'src/upstream-decisions.json': {'schema_version': 1, 'decisions': decisions, 'last_review_fingerprint': report['id']},
                   ROOT / 'script_helper/build_dependencies.json': report['candidate_lock']}
        for path, data in targets.items():
            path.write_text(json.dumps(data, indent=2) + '\n')
        print('Applied explicit choices to lock/recipes only; inspect the diff and rebuild before committing')
    else:
        print('Choices and complete candidate source assembly validated; no authored files changed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('report')
    p.add_argument('--before-lock', type=Path, required=True)
    p.add_argument('--candidate-lock', type=Path, default=ROOT / 'script_helper/build_dependencies.json')
    p.add_argument('--assembled', type=Path, default=ROOT / '.font-build/assembled')
    p.add_argument('--output', type=Path, default=ROOT / '.font-build/upstream-review')
    for mode in ('check', 'apply'):
        p = sub.add_parser(mode)
        p.add_argument('--report', type=Path, required=True)
        p.add_argument('--choices', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'report': make_report(args.before_lock, args.candidate_lock, args.assembled, args.output)
    else: checked_apply(args.report, args.choices, args.command == 'apply')
