#!/usr/bin/env python3
"""Import the audited macOS symbol gaps without reserializing existing SFDs.

    fontforge -lang=py -script script_helper/add_terminal_symbols.py [--check]

Donor binaries are checksum-pinned build inputs, never tracked font outputs.
Only records listed in symbol_additions.json belong to this helper.
"""
import argparse
import json
import re
import tempfile
from pathlib import Path

import fontforge
import psMat

from fetch_build_dependencies import fetch

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'script_helper/symbol_additions.json'
RECORD = re.compile(r'^StartChar: .*?^EndChar\n', re.MULTILINE | re.DOTALL)


def glyph_records(text):
    return {int(re.search(r'^Encoding: -?\d+ (-?\d+) \d+$', m[0], re.MULTILINE)[1]): m[0]
            for m in RECORD.finditer(text)}


def grid_character(cp):
    return (0x1FB00 <= cp <= 0x1FBAF or 0x1FBC1 <= cp <= 0x1FBC3
            or 0x1FBCE <= cp <= 0x1FBEF)


def clip_cell(glyph):
    """Clip straight semigraphic polygons exactly at adjacent cell boundaries."""
    left, bottom, right, top = glyph.boundingBox()
    if left >= 0 and bottom >= -320 and right <= 575 and top <= 910:
        return
    layer = fontforge.layer()
    for contour in glyph.foreground:
        assert all(point.on_curve for point in contour), 'Unexpected curved overhang'
        polygon = [(point.x, point.y) for point in contour]
        for axis, edge, keep_greater in ((0, 0, True), (0, 575, False), (1, -320, True), (1, 910, False)):
            result = []
            if not polygon:
                break
            for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                inside_a = a[axis] >= edge if keep_greater else a[axis] <= edge
                inside_b = b[axis] >= edge if keep_greater else b[axis] <= edge
                if inside_a:
                    result.append(a)
                if inside_a != inside_b:
                    ratio = (edge - a[axis]) / (b[axis] - a[axis])
                    result.append(tuple(a[n] + ratio * (b[n] - a[n]) for n in (0, 1)))
            polygon = result
        if len(polygon) >= 3:
            clipped = fontforge.contour()
            clipped.moveTo(*polygon[0])
            for point in polygon[1:]:
                clipped.lineTo(*point)
            clipped.closed = True
            layer += clipped
    glyph.foreground = layer


def make_symbols(catalog):
    donors = [(name, fontforge.open(str(fetch(name))))
              for name in ('iosevka', 'noto-symbols2', 'kreative-square')]
    symbols = fontforge.font()
    symbols.encoding = 'UnicodeFull'
    symbols.em = 1024
    try:
        for item in catalog['additions']:
            cp = int(item['codepoint'], 16)
            source_cp = 0x2BF9 if cp == 0x2B96 else cp
            name, donor = next((name, font) for name, font in donors if source_cp in font)
            donor.selection.select(('unicode',), source_cp)
            donor.unlinkReferences()
            original = donor[source_cp]
            assert not original.references, (name, hex(source_cp), 'unresolved component')
            glyph = symbols.createChar(cp, f'uni{cp:04X}' if cp <= 0xFFFF else f'u{cp:05X}')
            glyph.foreground = original.foreground
            if cp == 0x2B96:
                # U+2BF9 is the opposite chess compensation symbol. Reflect
                # vertically to place infinity above the symmetric equals sign.
                _, bottom, _, top = glyph.boundingBox()
                glyph.transform(psMat.compose(psMat.scale(1, -1), psMat.translate(0, top + bottom)))
            if grid_character(cp):
                # Semigraphics must meet at cell edges, including between rows.
                sx = 575 / original.width
                sy = 1230 / (donor.hhea_ascent - donor.hhea_descent)
                glyph.transform((sx, 0, 0, sy, 0, 910 - donor.hhea_ascent * sy))
                clip_cell(glyph)
                transform = 'fit full terminal cell, 575 by 1230; clip overhangs at cell edges'
            else:
                left, bottom, right, top = glyph.boundingBox()
                scale = min(1024 / donor.em, 527 / (right - left), 896 / (top - bottom))
                glyph.transform(psMat.scale(scale))
                left, bottom, right, top = glyph.boundingBox()
                glyph.transform(psMat.translate((575 - left - right) / 2, 320 - (top + bottom) / 2))
                transform = 'uniform fit with side bearings; center in symbol area'
            glyph.width = 575
            glyph.removeOverlap()
            glyph.correctDirection()
            glyph.round()
            item['donor'] = name
            item['source_codepoint'] = f'{source_cp:04X}'
            item['transform'] = ('reflect vertically; ' if cp == 0x2B96 else '') + transform
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'symbols.sfd'
            symbols.save(str(path))
            return glyph_records(path.read_text())
    finally:
        symbols.close()
        for _, font in donors:
            font.close()


def update(text, additions):
    records = glyph_records(text)
    count = re.search(r'^BeginChars: (\d+) (\d+)$', text, re.MULTILINE)
    record_count = len(list(RECORD.finditer(text)))
    if not count or int(count[2]) != record_count:
        raise ValueError('Unexpected SFD glyph count')
    next_id = 1 + max(map(int, re.findall(r'^Encoding: -?\d+ -?\d+ (\d+)$', text, re.MULTILINE)))
    new = []
    for cp, record in additions.items():
        old = records.get(cp)
        gid = int(re.search(r'^Encoding: -?\d+ -?\d+ (\d+)$', old, re.MULTILINE)[1]) if old else next_id
        record = re.sub(r'^Encoding: .*$', f'Encoding: {cp} {cp} {gid}', record, flags=re.MULTILINE)
        if old:
            text = text.replace(old, record, 1)
        else:
            new.append(record)
            next_id += 1
    if new:
        text = text.replace('EndChars\n', '\n'.join(new) + 'EndChars\n', 1)
        text = text.replace(count[0], f'BeginChars: {max(int(count[1]), max(additions) + 1)} {record_count + len(new)}', 1)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--source-dir', type=Path, default=ROOT / '.font-build/assembled')
    args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text())
    additions = make_symbols(catalog)
    stale = []
    for style in ('Regular', 'Italic', 'Bold', 'Bold-Italic'):
        path = args.source_dir / f'monofuki-{style}.sfd'
        original = path.read_text()
        result = update(original, additions)
        if result != original:
            stale.append(path.name)
            if not args.check:
                path.write_text(result)
        print(f'{path.name}: {len(additions)} symbols, ' + ('needs update' if args.check and result != original else 'OK'))
    provenance = json.dumps(catalog, indent=2) + '\n'
    if args.check:
        if stale or provenance != CATALOG.read_text():
            raise SystemExit(1)
    else:
        CATALOG.write_text(provenance)


if __name__ == '__main__':
    main()
