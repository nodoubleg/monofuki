#!/usr/bin/env python3
"""Check that explicitly expected visible characters contain drawable ink."""
import sys
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.areaPen import AreaPen

EXPECTED_VISIBLE = (0x207F, 0x2099)


def check(font, label='font'):
    glyph_set, cmap = font.getGlyphSet(), font.getBestCmap()
    for codepoint in EXPECTED_VISIBLE:
        if codepoint not in cmap:
            raise ValueError(f'{label}: missing U+{codepoint:04X}')
        name = cmap[codepoint]
        bounds, area = BoundsPen(glyph_set), AreaPen(glyph_set)
        glyph_set[name].draw(bounds)
        glyph_set[name].draw(area)
        b = bounds.bounds
        if b is None or b[0] >= b[2] or b[1] >= b[3] or abs(area.value) < 1:
            raise ValueError(f'{label}: expected visible U+{codepoint:04X} has no ink')
        if font['hmtx'][name][0] != 575:
            raise ValueError(f'{label}: U+{codepoint:04X} advance changed')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Supply generated font files')
    for path in sys.argv[1:]:
        with TTFont(path) as font:
            check(font, Path(path).name)
        print(f'PASS {Path(path).name}: expected visible U+207F/U+2099 contain ink, advance 575')
