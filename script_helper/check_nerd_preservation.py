#!/usr/bin/env python3
"""Compare the exact regular patcher input against the Nerd output and policy."""
import json
import sys
from pathlib import Path
import fontforge

ROOT = Path(__file__).resolve().parents[1]


def check(source, patched):
    policy = json.loads((ROOT / 'src/nerd-policy.json').read_text())
    allowed = {int(cp, 16) for cp in policy['replaced_existing_codepoints']}
    start, end = (int(cp, 16) for cp in policy['regenerated_range'])
    allowed.update(range(start, end + 1))
    a, b = fontforge.open(str(source)), fontforge.open(str(patched))
    try:
        if a.em != b.em or (a.hhea_ascent, a.hhea_descent, a.hhea_linegap) != (b.hhea_ascent, b.hhea_descent, b.hhea_linegap):
            raise ValueError('Unexpected em or hhea line metric change')
        for field in ('os2_winascent', 'os2_windescent'):
            if getattr(a, field) != getattr(b, field):
                raise ValueError(f'Unexpected {field} change')
        if [b.os2_typoascent, b.os2_typodescent, b.os2_typolinegap] != policy['output_typographic_metrics']:
            raise ValueError('Unexpected Nerd typographic metrics')
        checked = 0
        for glyph in a.glyphs():
            cp = glyph.unicode
            key = cp if cp >= 0 else glyph.glyphname
            if key not in b:
                raise ValueError(f'Lost glyph: {key}')
            if cp in allowed:
                continue
            other = b[key]
            glyph.unlinkRef()
            other.unlinkRef()
            if glyph.width != other.width or not glyph.foreground.similar(other.foreground, policy['outline_tolerance_font_units']):
                raise ValueError(f'Unexpected outline/advance change: {glyph.glyphname} U+{cp:04X}')
            checked += 1
        print(f'PASS {Path(patched).name}: {checked} protected outlines/advances; only explicit policy substitutions allowed')
    finally:
        a.close()
        b.close()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: fontforge -lang=py -script check_nerd_preservation.py SOURCE PATCHED')
    check(*sys.argv[1:])
