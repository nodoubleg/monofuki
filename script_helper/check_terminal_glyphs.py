#!/usr/bin/env python3
"""Validate actual outlines with FontForge, including exported font rounding.

    fontforge -lang=py -script script_helper/check_terminal_glyphs.py [fonts ...]

Defaults to the four source SFDs. Supply exported TTF/OTF files to check the build.
"""

import sys
import json
import unicodedata
from pathlib import Path

import fontforge


def check(path, tuned=False):
    font = fontforge.open(str(path))
    try:
        assert font.em == 1024, (path, "em changed")
        ascent, descent = (880, -270) if tuned else (910, -320)
        cell_height = ascent - descent
        assert (font.hhea_ascent, font.hhea_descent, font.hhea_linegap) == (ascent, descent, 0)
        assert font.os2_typoascent - font.os2_typodescent + font.os2_typolinegap == cell_height
        width = font[0x20].width
        assert width == 575
        # Independent expectation from Unicode character names, not the generator.
        columns = {1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1, 7: 0, 8: 1}
        rows = {1: 0, 2: 1, 3: 2, 4: 0, 5: 1, 6: 2, 7: 3, 8: 3}
        for cp in range(0x2800, 0x2900):
            assert cp in font, (path, hex(cp), "missing")
            glyph = font[cp]
            assert glyph.width == width, (path, hex(cp), "advance")
            assert not glyph.references, (path, hex(cp), "unexpected reference")
            name = unicodedata.name(chr(cp))
            dots = [] if cp == 0x2800 else [int(n) for n in name.split("-")[1]]
            expected = sorted(((columns[n] + 0.5) * width / 2,
                               ascent - (rows[n] + 0.5) * cell_height / 4) for n in dots)
            actual = []
            for contour in glyph.foreground:
                assert contour.closed and contour.isClockwise(), (path, hex(cp), "contour")
                points = list(contour)
                xs, ys = [p.x for p in points], [p.y for p in points]
                corners = {(x, y) for x in (min(xs), max(xs)) for y in (min(ys), max(ys))}
                assert corners <= {(p.x, p.y) for p in points if p.on_curve}, (path, hex(cp), 'corners')
                # TTF conversion may retain collinear control points near a
                # rounded corner. Verify the rectangle itself, not point count.
                assert all(a.x == b.x or a.y == b.y for a, b in zip(points, points[1:] + points[:1]))
                assert all(p.x in (min(xs), max(xs)) or p.y in (min(ys), max(ys)) for p in points)
                assert abs(max(xs) - min(xs) - 172.5) <= 1
                assert abs(max(ys) - min(ys) - 184.5 * cell_height / 1230) <= 1
                actual.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
            assert len(actual) == len(expected), (path, hex(cp), "dot count")
            for observed, wanted in zip(sorted(actual), expected):
                assert all(abs(a - b) <= 0.5 for a, b in zip(observed, wanted)), (path, hex(cp), observed, wanted)
        # All graphics ranges involved in the fix must survive every export.
        for cp in [*range(0x20, 0x7f), *range(0x2500, 0x25a0), 0x21e8, 0x21e9, 0x21ef]:
            assert cp in font, (path, hex(cp), "missing graphic")
        for cp in (0x21e8, 0x21e9, 0x21ef):
            assert font[cp].width == width
            left, bottom, right, top = font[cp].boundingBox()
            assert right > left and top > bottom, (path, hex(cp), "empty arrow")
        additions = json.loads((Path(__file__).parent / 'symbol_additions.json').read_text())['additions']
        for item in additions:
            cp = int(item['codepoint'], 16)
            assert cp in font, (path, hex(cp), 'missing audited symbol')
            glyph = font[cp]
            assert glyph.width == width, (path, hex(cp), 'symbol advance')
            left, bottom, right, top = glyph.boundingBox()
            assert right > left and top > bottom, (path, hex(cp), 'empty symbol')
            assert left >= -1 and right <= width + 1 and bottom >= -321 and top <= 911, (path, hex(cp), 'outside cell')
        for cp in (0x2B80, 0x2B81, 0x2B84, 0x2B85, 0x2B86, 0x2B87):
            assert len(font[cp].foreground) == 2, (path, hex(cp), 'paired arrow lost a component')
        if 'NerdFont' in str(path):
            assert 'Nerd Fonts 3.5.1' in font.version, (path, font.version, 'wrong patcher version')
            assert all('Nerd Fonts 3.5.1' in value for _, name, value in font.sfnt_names if name == 'Version'), (path, 'stale version name')
            style = Path(path).stem.removeprefix('MonofukiNerdFont-')
            assert font.fontname == f'MonofukiNF-{style}', (path, font.fontname, 'terminal profile name changed')
        print(f"PASS {path}: 256 Braille patterns, {len(additions)} added symbols, metrics, ASCII, boxes, blocks, arrows")
    finally:
        font.close()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    tuned = '--tuned' in sys.argv
    paths = [arg for arg in sys.argv[1:] if arg != '--tuned'] or sorted((root / ".font-build/assembled").glob("*.sfd"))
    if not paths:
        raise SystemExit("No assembled sources; run fontforge -lang=py -script script_helper/assemble_sources.py")
    for path in paths:
        check(path, tuned)
