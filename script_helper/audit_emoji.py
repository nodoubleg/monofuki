#!/usr/bin/env python3
"""Classify added/encoded glyphs using pinned Unicode emoji data; emit macOS probes."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'script_helper/unicode/18.0.0'


def properties():
    result = {}
    for line in (DATA / 'emoji-data.txt').read_text().splitlines():
        fields = line.split('#')[0].strip()
        if not fields: continue
        span, prop = map(str.strip, fields.split(';'))
        bounds = span.split('..')
        result.setdefault(prop, set()).update(range(int(bounds[0],16), int(bounds[-1],16)+1))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fonts',nargs='+',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'.font-build/emoji-audit.json')
    parser.add_argument('--cases',type=Path,default=ROOT/'.font-build/emoji-cases.json')
    args=parser.parse_args()
    lock=json.loads((ROOT/'script_helper/build_dependencies.json').read_text())
    for name in ('emoji-data.txt','emoji-variation-sequences.txt','emoji-zwj-sequences.txt','emoji-sequences.txt'):
        path=DATA/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=lock['vendored_files'][str(path.relative_to(ROOT))]:
            raise ValueError(f'Pinned emoji data changed: {name}')
    props=properties()
    variation={int(m[1],16) for line in (DATA/'emoji-variation-sequences.txt').read_text().splitlines() if (m:=re.match(r'^([0-9A-F]+) FE0F\s*;',line))}
    additions=json.loads((ROOT/'script_helper/symbol_additions.json').read_text())['additions']
    def category(cp):
        if cp in props['Emoji_Presentation']: return 'default-emoji'
        if cp in props['Emoji']: return 'text-default-emoji-capable'
        return 'not-emoji'
    report={'unicode_version':'18.0.0','data_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (DATA/'emoji-data.txt',DATA/'emoji-variation-sequences.txt',DATA/'emoji-zwj-sequences.txt',DATA/'emoji-sequences.txt')},
            'additions':[{**item,'emoji_category':category(int(item['codepoint'],16)),'standardized_variations':int(item['codepoint'],16) in variation} for item in additions], 'fonts':[]}
    cases=[]
    points={0x263A,0x263B,0x1F600,0x2665,0x2764,0x1F49B,0x2600,0x263C,0x2197,0x2B66,0x25FD,0x25FE,0x26A1,0x0031}
    for path in args.fonts:
        with TTFont(path) as f:
            cmap=f.getBestCmap();mapped=set(cmap)
            report['fonts'].append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
              'emoji_capable':[f'{cp:04X}' for cp in sorted(mapped&props['Emoji'])],
              'default_emoji':[f'{cp:04X}' for cp in sorted(mapped&props['Emoji_Presentation'])],
              'cmap14_present':any(t.format==14 for t in f['cmap'].tables)})
            points |= mapped & props['Emoji_Presentation']
    for cp in sorted(points):
        for mode, suffix in [('plain',''),('VS15','\ufe0e'),('VS16','\ufe0f')]:
            cases.append({'label':f'U+{cp:04X} {mode}','text':chr(cp)+suffix,'category':category(cp),
                          'standardized_variation':mode=='plain' or cp in variation})
    available={tuple(int(cp,16) for cp in line.split(';')[0].split()) for line in (DATA/'emoji-zwj-sequences.txt').read_text().splitlines() if line.strip() and not line.startswith('#')}
    for label,points in [('woman-technologist',[0x1F469,0x200D,0x1F4BB]),('heart-on-fire',[0x2764,0xFE0F,0x200D,0x1F525]),('family',[0x1F468,0x200D,0x1F469,0x200D,0x1F467,0x200D,0x1F466])]:
        if tuple(points) not in available: raise ValueError(f'Unlisted ZWJ probe: {label}')
        cases.append({'label':label,'text':''.join(map(chr,points)),'category':'standardized-ZWJ','standardized_variation':True})
    sequences = {tuple(int(cp,16) for cp in line.split(';')[0].split()) for line in (DATA/'emoji-sequences.txt').read_text().splitlines() if line.strip() and not line.startswith('#') and '..' not in line.split(';')[0]}
    for label, points in [('keycap-one',[0x31,0xFE0F,0x20E3]),('keycap-hash',[0x23,0xFE0F,0x20E3]),('victory-medium-skin',[0x270C,0x1F3FD]),('Japan-flag',[0x1F1EF,0x1F1F5])]:
        if tuple(points) not in sequences: raise ValueError(f'Unlisted sequence probe: {label}')
        cases.append({'label':label,'text':''.join(map(chr,points)),'category':'standardized-sequence','standardized_variation':True})
    for path, data in ((args.output,report),(args.cases,cases)):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    counts={kind:sum(i['emoji_category']==kind for i in report['additions']) for kind in ('default-emoji','text-default-emoji-capable','not-emoji')}
    print(json.dumps({'added_symbol_categories':counts,'fonts':report['fonts'],'cases':len(cases)},indent=2))

if __name__=='__main__':main()
