#!/usr/bin/env python3
"""Compare two locked upstream revisions; never modify locks or source recipes."""
import argparse
import difflib
import json
import re
from pathlib import Path
from assemble_sources import records, encoding, check_references, STYLES
from fetch_build_dependencies import fetch, ROOT
from glyph_overrides import digest


def compare(before, after):
    check_references(before)
    check_references(after)
    old, new = records(before), records(after)
    changed = sorted(name for name in old.keys() & new.keys() if old[name] != new[name])
    affected = set(changed) | (old.keys() - new.keys())
    by_id = {encoding(r)[2]: name for name, r in old.items()}
    while True:
        dependents = {name for name, r in old.items() if any(by_id[int(gid)] in affected for gid in re.findall(r'^Refer: (\d+) ', r, re.M))}
        if dependents <= affected:
            break
        affected |= dependents
    def metadata(text):
        for record in records(text).values():
            text = text.replace(record, '', 1)
        return text
    return {'added_glyphs': sorted(new.keys() - old.keys()), 'removed_glyphs': sorted(old.keys() - new.keys()),
            'changed_glyphs': [{'glyph_name': name, 'before_sha256': digest(old[name]), 'after_sha256': digest(new[name]),
                                'diff': ''.join(difflib.unified_diff(old[name].splitlines(True), new[name].splitlines(True), fromfile='before', tofile='after'))} for name in changed],
            'affected_reference_dependents': sorted(affected - set(changed) - (old.keys() - new.keys())),
            'metadata_metrics_layout_diff': ''.join(difflib.unified_diff(metadata(before).splitlines(True), metadata(after).splitlines(True), fromfile='before metadata', tofile='after metadata'))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before-lock', type=Path, required=True)
    parser.add_argument('--after-lock', type=Path, default=ROOT / 'script_helper/build_dependencies.json')
    parser.add_argument('--output', type=Path, default=ROOT / '.font-build/upstream-review.json')
    args = parser.parse_args()
    old, new = (json.loads(p.read_text()) for p in (args.before_lock, args.after_lock))
    report = {'before': old['upstream'], 'after': new['upstream'], 'styles': {}}
    for style in STYLES:
        before = fetch('upstream-' + style, manifest=old).read_text()
        after = fetch('upstream-' + style, manifest=new).read_text()
        report['styles'][style] = compare(before, after)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Wrote upstream glyph, dependency, metadata, metric and layout review to {args.output}')
