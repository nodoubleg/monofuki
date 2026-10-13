#!/usr/bin/env python3
"""Align source Braille with Nerd Fonts 3.5.1's rectangular 0.6-ratio grid.

Run from any directory. --check verifies that all four sources are up to date.
The grid stays upright and identical in every style, including bold and italic.
"""

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("Regular", "Italic", "Bold", "Bold-Italic")
# Unicode bit order: dots 1,2,3 down the left; 4,5,6 down the right;
# then dots 7 and 8 on the bottom row.
DOTS = ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3))
DOT_RATIO = 0.6  # Same default as Nerd Fonts' bin/scripts/braille/Braille.py.
RECORD = re.compile(r"^StartChar: .*?^EndChar\n", re.MULTILINE | re.DOTALL)


def field(text, name):
    return int(re.search(rf"^{name}: (-?\d+)$", text, re.MULTILINE)[1])


def braille_record(codepoint, glyph_id, width, top, bottom):
    lines = [f"StartChar: uni{codepoint:04X}",
             f"Encoding: {codepoint} {codepoint} {glyph_id}",
             f"Width: {width}", "Flags: W", "LayerCount: 2", "Fore"]
    mask = codepoint - 0x2800
    if mask:
        lines.append("SplineSet")
        for bit, (column, row) in enumerate(DOTS):
            if not mask & (1 << bit):
                continue
            x = (column + 0.5) * width / 2
            y = top - (row + 0.5) * (top - bottom) / 4
            half_x = width / 4 * DOT_RATIO
            half_y = (top - bottom) / 8 * DOT_RATIO
            left, right = x - half_x, x + half_x
            low, high = y - half_y, y + half_y
            # Clockwise outer contours; fractional source coordinates retain
            # the exact lattice. The existing export pipeline rounds to units.
            lines.extend((f"{left:g} {low:g} m 1", f" {left:g} {high:g} l 1",
                          f" {right:g} {high:g} l 1", f" {right:g} {low:g} l 1",
                          f" {left:g} {low:g} l 1"))
        lines.append("EndSplineSet")
    lines.append("EndChar")
    return "\n".join(lines) + "\n"


def update(text):
    records = list(RECORD.finditer(text))
    count = re.search(r"^BeginChars: (\d+) (\d+)$", text, re.MULTILINE)
    if not count or int(count[2]) != len(records):
        raise ValueError("Unexpected SFD glyph count")
    top, bottom = field(text, "HheadAscent"), field(text, "HheadDescent")
    if field(text, "LineGap") != 0:
        raise ValueError("Braille grid requires zero hhea line gap")
    width = next(field(m[0], "Width") for m in records
                 if m[0].startswith("StartChar: space\n"))
    if not 0 < DOT_RATIO < 1:
        raise ValueError("Dots must not touch neighboring dots")
    encodings = {}
    ids = []
    for m in records:
        encoding = re.search(r"^Encoding: (-?\d+) (-?\d+) (\d+)$", m[0], re.MULTILINE)
        cp, gid = int(encoding[2]), int(encoding[3])
        encodings[cp] = (m[0], gid)
        ids.append(gid)
    additions = []
    next_id = max(ids) + 1
    for cp in range(0x2800, 0x2900):
        if cp in encodings:
            old, gid = encodings[cp]
            # Only the Braille records owned by this helper are replaced.
            text = text.replace(old, braille_record(cp, gid, width, top, bottom), 1)
        else:
            additions.append(braille_record(cp, next_id, width, top, bottom))
            next_id += 1
    if additions:
        text = text.replace("EndChars\n", "\n".join(additions) + "EndChars\n", 1)
        text = text.replace(count[0], f"BeginChars: {max(int(count[1]), 0x2900)} "
                            f"{len(records) + len(additions)}", 1)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--source-dir", type=Path, default=ROOT / ".font-build/assembled")
    args = parser.parse_args()
    stale = []
    for variant in VARIANTS:
        path = args.source_dir / f"monofuki-{variant}.sfd"
        original = path.read_text()
        result = update(original)
        if result != original:
            stale.append(path.name)
            if not args.check:
                path.write_text(result)
        print(f"{path.name}: {'needs update' if args.check and result != original else 'OK'}")
    if args.check and stale:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
