#!/usr/bin/env python3
"""Preserve Bold U+207F/U+2099 when FontForge's quadratic overlap cleanup loses it.

This is an export repair, using the correct same-style OTF as the only source.
No authored SFD, other glyph, advance, or OpenType feature is changed.
"""
import argparse
import hashlib
import io
import json
import os
import tempfile
import struct
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.areaPen import AreaPen

CODEPOINTS = (0x207F, 0x2099)
MAX_ERROR = 0.5


def repair(source_bytes, target_bytes):
    source = TTFont(io.BytesIO(source_bytes), recalcTimestamp=False)
    target = TTFont(io.BytesIO(target_bytes), recalcTimestamp=False, recalcBBoxes=False)
    if 'CFF ' not in source or 'glyf' not in target:
        raise ValueError('Expected an OTF source and TrueType target')
    for font in (source, target):
        if font['OS/2'].usWeightClass != 700 or font['OS/2'].fsSelection & 1:
            raise ValueError('This repair is restricted to upright Bold')
    if source['name'].getDebugName(1) != target['name'].getDebugName(1):
        raise ValueError('Source and target families differ')
    glyph_set = source.getGlyphSet()
    repaired = []
    metrics = bytearray(target.reader["hmtx"])
    metric_count = target["hhea"].numberOfHMetrics
    for codepoint in CODEPOINTS:
        name = target.getBestCmap()[codepoint]
        source_name = source.getBestCmap()[codepoint]
        if target['hmtx'][name][0] != 575 or source['hmtx'][source_name][0] != 575:
            raise ValueError('Unexpected advance for small n')
        bounds, area = BoundsPen(glyph_set), AreaPen(glyph_set)
        glyph_set[source_name].draw(bounds)
        glyph_set[source_name].draw(area)
        if not bounds.bounds or abs(area.value) < 1:
            raise ValueError('The OTF reference must contain visible ink')
        pen = TTGlyphPen(None)
        glyph_set[source_name].draw(Cu2QuPen(pen, MAX_ERROR, reverse_direction=True))
        glyph = pen.glyph()
        if glyph.numberOfContours <= 0:
            raise ValueError('Quadratic conversion produced an empty glyph')
        glyph.recalcBounds(target['glyf'])
        target['glyf'][name] = glyph
        # Keep the original hmtx encoding and every unrelated table byte exact.
        gid = target.getGlyphID(name)
        offset = 4 * gid + 2 if gid < metric_count else 4 * metric_count + 2 * (gid - metric_count)
        struct.pack_into('>h', metrics, offset, glyph.xMin)
        if len(glyph.coordinates) > target['maxp'].maxPoints or glyph.numberOfContours > target['maxp'].maxContours:
            raise ValueError('Repaired glyph exceeds existing TrueType maximums')
        repaired.append({'codepoint': f'U+{codepoint:04X}', 'glyph': name})
    for tag in target.reader.keys():
        if tag not in ('head', 'glyf', 'loca', 'maxp'):
            table = DefaultTable(tag)
            table.data = bytes(metrics) if tag == 'hmtx' else target.reader[tag]
            target[tag] = table
    output = io.BytesIO()
    target.save(output)
    return output.getvalue(), {
        'glyphs': repaired, 'style': 'Bold',
        'method': 'same-style OTF outline converted with fontTools Cu2QuPen',
        'maximum_conversion_error_units': MAX_ERROR, 'advance': 575,
        'source_otf_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'target_before_sha256': hashlib.sha256(target_bytes).hexdigest(),
        'target_after_sha256': hashlib.sha256(output.getvalue()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    parser.add_argument('--provenance', type=Path, required=True)
    args = parser.parse_args()
    data, report = repair(args.source.read_bytes(), args.target.read_bytes())
    report.update(source=args.source.name, target=args.target.name)
    with tempfile.NamedTemporaryFile(dir=args.target.parent, delete=False) as temp:
        temp.write(data)
        temporary = temp.name
    os.replace(temporary, args.target)
    args.provenance.write_text(json.dumps(report, indent=2)+'\n')
    print('Repaired Bold U+207F/U+2099 from their OTF outlines; advance 575')


if __name__ == '__main__':
    main()
