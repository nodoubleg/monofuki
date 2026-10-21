#!/usr/bin/env python3
"""Verify actual tuned binaries against full base fonts and the JS outline oracle."""
import argparse
import copy
import hashlib
import io
import json
import random
import subprocess
import sys
import time
from pathlib import Path
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import RecordingPen
from tuning_compiler import compile_font, replay, smart_shift, safety_envelope, stronger_shift

ROOT = Path(__file__).resolve().parents[1]
STYLES = ('Regular','Bold','Italic','BoldItalic')


def oracle(settings):
    code = "const {createEngine}=require('./script_helper/tuning_reference.cjs');let s=JSON.parse(require('fs').readFileSync(0,'utf8')),e=createEngine(s),out={};for(const style of e.styles)out[style]=Object.fromEntries(e.characters(style).map(c=>[c,e.outline(style,c)]));process.stdout.write(JSON.stringify(out));"
    return json.loads(subprocess.check_output(['node','-e',code],input=json.dumps(settings).encode(),cwd=ROOT))


def measure(draw):
    area,bounds=AreaPen(None),BoundsPen(None)
    draw(area);draw(bounds)
    return area.value,bounds.bounds


def check_outlines(font, geometry, tolerance=0.002):
    gs, cmap = font.getGlyphSet(),font.getBestCmap()
    for c, outline in geometry.items():
        expected = measure(lambda p: replay(outline,p))
        actual = measure(gs[cmap[ord(c)]].draw)
        assert (expected[1] is None)==(actual[1] is None),c
        if expected[1]:
            assert max(abs(a-b) for a,b in zip(expected[1],actual[1])) <= tolerance,(c,expected,actual)
            # Winding may reverse for TTF; signed area magnitude must agree.
            assert abs(abs(expected[0])-abs(actual[0])) <= (0.25 if tolerance<0.01 else 1000),(c,'area',expected,actual)


def shape(data,text,kern):
    font=hb.Font(hb.Face(data));buf=hb.Buffer();buf.add_str(text);buf.guess_segment_properties()
    hb.shape(font,buf,{'kern':kern})
    return [(p.x_advance,p.x_offset,p.y_offset)for p in buf.glyph_positions]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-profiles',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'.font-build/tuning-checks.json')
    args=parser.parse_args()
    settings=json.loads((ROOT/'src/tuning/defaults.json').read_text());geometry=oracle(settings)
    report={'default_fonts':[],'profiles':0,'shaping_cases':0,'started':time.time()}
    for family in ('Monofuki','MonofukiNerdFont'):
        for style in STYLES:
            suffix=style.replace('BoldItalic','Bold-Italic') if family=='Monofuki' else style
            for extension in ('otf','ttf'):
                name=f'{family}-{suffix}.{extension}'
                base=TTFont(ROOT/'export/tuning-base'/name)
                font=TTFont(ROOT/'export'/name)
                assert font.getBestCmap()==base.getBestCmap(),name
                assert font.getGlyphOrder()==base.getGlyphOrder(),name
                assert {k:v[0] for k,v in font['hmtx'].metrics.items()}=={k:v[0] for k,v in base['hmtx'].metrics.items()},name
                assert (font['head'].unitsPerEm,font['hhea'].ascent,font['hhea'].descent,font['hhea'].lineGap)==(1024,880,-270,0),name
                os2=font['OS/2'];assert (os2.sTypoAscender,os2.sTypoDescender,os2.sTypoLineGap)==(880,-270,0),name
                assert font['name'].getDebugName(1)==base['name'].getDebugName(1),name
                assert font['name'].getDebugName(6)==base['name'].getDebugName(6),name
                check_outlines(font,geometry[style],0.002 if extension=='otf' else 1.7)
                # All glyphs outside the explicit tuning/graphics sets retain outlines.
                changed={font.getBestCmap()[ord(c)] for c in geometry[style]}
                changed.update(font.getBestCmap()[cp] for cp in [*range(0x2500,0x25A0),*range(0x2800,0x2900)])
                a,b=base.getGlyphSet(),font.getGlyphSet();unchanged=0
                for glyph in font.getGlyphOrder():
                    if glyph in changed:continue
                    pa,pb=RecordingPen(),RecordingPen();a[glyph].draw(pa);b[glyph].draw(pb)
                    assert pa.value==pb.value,(name,glyph,'untouched outline changed')
                    unchanged+=1
                data=(ROOT/'export'/name).read_bytes()
                for text in ['minimum Toffee VVA VYA WYA','ÁÉÅÜ ÇĽ','a 0 q {7} g','A\u0301 Á']:
                    for kern in (False,True):
                        positions=shape(data,text,kern)
                        assert all(p[0]==575 for p in positions),(name,text,positions)
                        if not kern:assert all(p[1]==0 for p in positions),(name,text,positions)
                report['default_fonts'].append({'name':name,'sha256':hashlib.sha256(data).hexdigest(),'coverage':len(font.getBestCmap()),'unchanged_outlines':unchanged})
                print('PASS',name,'coverage, metrics, selected/untouched outlines, names, advances',flush=True)
    # Real shaped offsets, including boundaries, disabled features and saturation.
    for strength in (0,94,100,200,400):
        current=copy.deepcopy(settings)
        current['experiments'].update(smartStrength=strength,symbolEnabled=True,symbolStrength=strength)
        geom=oracle(current)
        for style in STYLES:
            suffix=style.replace('BoldItalic','Bold-Italic')
            data,_=compile_font((ROOT/'export/tuning-base'/f'Monofuki-{suffix}.otf').read_bytes(),geom[style],current,style)
            env=safety_envelope(geom[style]);random.seed(17)
            letters=[c for c in geom[style] if c.isalnum() and geom[style][c]['sourceBounds']]
            cases=['minimum Toffee VVA VYA WYA','... :: -> === ==== ===== ====== += !=','AÁA ÉÉÉ']
            cases += [''.join(random.choices(letters,k=3))for _ in range(250)]
            code="const {createEngine}=require('./script_helper/tuning_reference.cjs'),v=JSON.parse(require('fs').readFileSync(0,'utf8')),e=createEngine(v.settings);process.stdout.write(JSON.stringify(v.cases.map(t=>e.spacing(t,v.style))));"
            expected=json.loads(subprocess.check_output(['node','-e',code],input=json.dumps({'settings':current,'style':style,'cases':cases}).encode(),cwd=ROOT))
            for text,reference in zip(cases,expected):
                got=shape(data,text,True)
                assert len(got)==len(reference['shifts']),(style,text,'cluster count')
                assert all(abs(pos[1]-want)<=0.50001 and pos[0]==575 for pos,want in zip(got,reference['shifts'])),(style,strength,text,got,reference)
                report['shaping_cases']+=1
            print('PASS shaping',style,strength,flush=True)
    if args.all_profiles:
        for mask in range(32):
            current=copy.deepcopy(settings)
            current['experiments']['gAlternative']='open-double-storey' if mask&1 else 'original'
            current['glyphAlternatives']={'q':'tailed' if mask&2 else 'original','0':'dotted' if mask&4 else 'original','braces':'curved' if mask&16 else 'original'}
            current['sevenCrossbar']['enabled']=bool(mask&8)
            geom=oracle(current)
            for style in STYLES:
                suffix=style.replace('BoldItalic','Bold-Italic')
                data,r=compile_font((ROOT/'export/tuning-base'/f'Monofuki-{suffix}.otf').read_bytes(),geom[style],current,style)
                font=TTFont(io.BytesIO(data));check_outlines(font,{c:geom[style][c]for c in 'gq07{}'})
                assert font.getBestCmap()==TTFont(ROOT/'export/tuning-base'/f'Monofuki-{suffix}.otf').getBestCmap()
                report['profiles']+=1
            print('PASS alternative profile',mask,flush=True)
    report['elapsed_seconds']=round(time.time()-report.pop('started'),2)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS tuning matrix:',len(report['default_fonts']),'default binaries;',report['profiles'],'style/profile builds;',report['shaping_cases'],'shaped strings')


if __name__=='__main__':main()
