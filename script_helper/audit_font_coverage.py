#!/usr/bin/env python3
"""Report terminal Unicode coverage using FontForge.

    fontforge -lang=py -script script_helper/audit_font_coverage.py [fonts ...]

Defaults to the four source SFDs. Add a reference font as the final argument
to list characters present in that font but absent in the first font.
Counts use code-point slots, including unassigned slots, rather than assigned
Unicode character totals. Private-use Nerd Font icons are deliberately excluded.
"""

import sys
from pathlib import Path

import fontforge


RANGES = (
    ("Printable ASCII", 0x20, 0x7e),
    ("Arrows", 0x2190, 0x21ff),
    ("Misc. Technical", 0x2300, 0x23ff),
    ("Control Pictures", 0x2400, 0x243f),
    ("Box Drawing", 0x2500, 0x257f),
    ("Block Elements", 0x2580, 0x259f),
    ("Geometric Shapes", 0x25a0, 0x25ff),
    ("Misc. Symbols", 0x2600, 0x26ff),
    ("Dingbats", 0x2700, 0x27bf),
    ("Braille", 0x2800, 0x28ff),
    ("Supplemental Arrows A", 0x27f0, 0x27ff),
    ("Supplemental Arrows B", 0x2900, 0x297f),
    ("Misc. Symbols/Arrows", 0x2b00, 0x2bff),
    ("Legacy Computing", 0x1fb00, 0x1fbff),
)


def main():
    root = Path(__file__).resolve().parents[1]
    paths = [Path(p) for p in sys.argv[1:]] or sorted((root / ".font-build/assembled").glob("*.sfd"))
    if not paths:
        raise SystemExit("No assembled sources; run assemble_sources.py first")
    fonts = [fontforge.open(str(p)) for p in paths]
    try:
        print("Range | " + " | ".join(p.name for p in paths))
        for label, start, end in RANGES:
            present = [{cp for cp in range(start, end + 1) if cp in f} for f in fonts]
            print(label + " | " + " | ".join(f"{len(s)}/{end-start+1}" for s in present))
            if sys.argv[1:] and len(fonts) > 1:
                missing = sorted(present[-1] - present[0])
                if missing:
                    print("  Reference-only: " + " ".join(f"U+{cp:04X}" for cp in missing))
    finally:
        for font in fonts:
            font.close()


if __name__ == "__main__":
    main()
