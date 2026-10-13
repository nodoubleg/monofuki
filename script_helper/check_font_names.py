#!/usr/bin/env python3
"""Reject stale family names in font identity fields (copyright history is kept)."""
import sys
from pathlib import Path
from fontTools.ttLib import TTFont


def check(path):
    nerd = path.name.startswith('MonofukiNerdFont-')
    prefix = 'MonofukiNerdFont-' if nerd else 'Monofuki-'
    style = path.stem.removeprefix(prefix).removesuffix('-hinted')
    expected_ps = ('MonofukiNF-' if nerd else 'Monofuki-') + style
    with TTFont(path) as font:
        names = font['name']
        if names.getDebugName(6) != expected_ps:
            raise ValueError(f'{path}: unexpected PostScript name {names.getDebugName(6)}')
        expected_family = 'Monofuki Nerd Font' if nerd else 'Monofuki'
        if names.getDebugName(1) != expected_family:
            raise ValueError(f'{path}: unexpected family {names.getDebugName(1)}')
        for record in names.names:
            if record.nameID in (1, 3, 4, 6, 16, 17, 18, 21, 22):
                if 'monofoki' in record.toUnicode().lower():
                    raise ValueError(f'{path}: stale identity field {record.nameID}')
        if 'CFF ' in font:
            cff = font['CFF '].cff
            if cff.fontNames != [expected_ps]:
                raise ValueError(f'{path}: stale CFF font name')
            if cff.topDictIndex[0].FamilyName != expected_family:
                raise ValueError(f'{path}: stale CFF family')
    print(f'PASS {path.name}: {expected_family} / {expected_ps}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Supply the exported TTF/OTF paths')
    for path in map(Path, sys.argv[1:]):
        check(path)
