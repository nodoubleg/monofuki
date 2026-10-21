#!/usr/bin/env python3
"""Regression for FontForge's lost Bold superscript/subscript n exports."""
import argparse
import io
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from repair_bold_small_n import repair, CODEPOINTS
from check_visible_glyphs import check

ROOT = Path(__file__).resolve().parents[1]


def read(data):
    return TTFont(io.BytesIO(data), recalcTimestamp=False, recalcBBoxes=False)


def geometry(font, name):
    glyphs = font.getGlyphSet()
    bounds, area = BoundsPen(glyphs), AreaPen(glyphs)
    glyphs[name].draw(bounds)
    glyphs[name].draw(area)
    return bounds.bounds, abs(area.value)


def verify(source_data, target_data):
    source, before = read(source_data), read(target_data)
    result, report = repair(source_data, target_data)
    after = read(result)
    check(after)
    assert before.getBestCmap() == after.getBestCmap(), 'cmap changed'
    assert before.getGlyphOrder() == after.getGlyphOrder(), 'glyph order changed'
    names = {before.getBestCmap()[cp] for cp in CODEPOINTS}
    for name in before.getGlyphOrder():
        if name not in names:
            assert before['glyf'][name].compile(before['glyf']) == after['glyf'][name].compile(after['glyf']), name
            assert before['hmtx'][name] == after['hmtx'][name], name
    allowed = {'GlyphOrder', 'glyf', 'loca', 'hmtx', 'head'}
    for tag in before.keys():
        if tag not in allowed:
            assert before.getTableData(tag) == after.getTableData(tag), tag
    # The new ink sits inside existing global bounds; only checksum may change.
    for key, value in vars(before['head']).items():
        if key not in ('checkSumAdjustment',):
            assert value == getattr(after['head'], key), key
    for cp in CODEPOINTS:
        reference_bounds, reference_area = geometry(source, source.getBestCmap()[cp])
        bounds, area = geometry(after, after.getBestCmap()[cp])
        assert max(abs(a-b) for a,b in zip(bounds, reference_bounds)) <= 1, (cp, bounds, reference_bounds)
        assert abs(area-reference_area) / reference_area < .01, (cp, area, reference_area)
        assert after['hmtx'][after.getBestCmap()[cp]][0] == 575
    repeated, _ = repair(source_data, result)
    assert repeated == result, 'repair is not byte-idempotent'
    # Reproduce the actual failure independently, one missing character at a time.
    for cp in CODEPOINTS:
        blank = read(result)
        blank['glyf'][blank.getBestCmap()[cp]] = TTGlyphPen(None).glyph()
        out = io.BytesIO(); blank.save(out)
        try:
            check(read(out.getvalue()))
        except ValueError as error:
            assert f'U+{cp:04X}' in str(error)
        else:
            raise AssertionError(f'Empty U+{cp:04X} falsely passed visibility')
        restored, _ = repair(source_data, out.getvalue())
        check(read(restored))
    print(f'PASS {len(before.getGlyphOrder())-len(names)} untouched glyphs, cmap, metrics, other tables; '
          'two visible OTF-derived outlines; deterministic repair; both blank negative controls')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT/'export/tuning-base')
    args = parser.parse_args()
    verify((args.base/'Monofuki-Bold.otf').read_bytes(), (args.base/'Monofuki-Bold.ttf').read_bytes())
