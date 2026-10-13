#!/usr/bin/env python3
"""Validate CoreText probe output against its same-host Menlo baseline."""
import json
import sys
from pathlib import Path

report=json.loads(Path(sys.argv[1]).read_text())
baseline={r['probe']['label']:r for r in report['results'] if r['source']=='system baseline'}
checked=0
for result in report['results']:
    if result['source']=='system baseline' or not result['probe']['standardized_variation']:
        continue  # Unsupported selectors and system gaps are diagnostic observations.
    runs=result['runs'];label=result['probe']['label']
    if not runs or any('LastResort' in r['font'] or 0 in r['glyphs'] for r in runs):
        raise ValueError(f"{result['requested_font']} {label}: missing glyph")
    expected=baseline[label]['runs']
    if len(expected)==1 and expected[0]['font']=='AppleColorEmoji':
        if len(runs)!=1 or runs[0]['font']!='AppleColorEmoji' or runs[0]['glyphs']!=expected[0]['glyphs'] or runs[0]['utf16_range']!=expected[0]['utf16_range']:
            raise ValueError(f"{result['requested_font']} {label}: emoji selection/cluster differs from same-host baseline")
    checked+=1
print(f'PASS {checked} supported custom-font cases; no tofu or baseline emoji/cluster regression on {report["platform"]}')
