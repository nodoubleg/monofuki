#!/usr/bin/env python3
"""Bracket eligibility, exact maximal runs, fixed advances and ink clearance."""
import copy,io,itertools,json,math,subprocess
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from test_tuning import ROOT,STYLES,oracle
from test_spacing_safety import intersections,segments
from tuning_compiler import SYMBOLS,compile_font

DELIMITERS='()[]{}'
def main():
 defaults=json.loads((ROOT/'src/tuning/defaults.json').read_text());checks=contours=0
 pairs=[a+b for a in SYMBOLS for b in SYMBOLS if a in DELIMITERS or b in DELIMITERS]
 runs={pair for pair in pairs}
 for length in (3,4):
  for index in range(length-1):
   runs.update('='*index+pair+'='*(length-index-2) for pair in pairs)
 runs.update(['(( )) [[ ]] {{ }}','(())','[[]]','{{}}','([])','(){}','([{}])','(((((','[[[[[[','{{{{{{{','========',*DELIMITERS])
 cases=sorted(runs)
 for braces in ('original','curved'):
  s=copy.deepcopy(defaults);s['glyphAlternatives']['braces']=braces;s['experiments'].update(smartEnabled=False,symbolEnabled=True)
  geometry=oracle(s)
  for style in STYLES:
   suffix=style.replace('BoldItalic','Bold-Italic');base=(ROOT/'export/tuning-base'/f'Monofuki-{suffix}.otf').read_bytes();baseline={};old_range={};cache={}
   for strength in (0,70,94,100,112,200,400):
    s['experiments']['symbolStrength']=strength
    data,_=compile_font(base,geometry[style],s,style);font=TTFont(io.BytesIO(data));gs=font.getGlyphSet();cmap=font.getBestCmap();hbfont=hb.Font(hb.Face(data))
    ink={c:segments(gs[cmap[ord(c)]].draw) for c in SYMBOLS}
    bounds={}
    for c in SYMBOLS:
     pen=BoundsPen(gs);gs[cmap[ord(c)]].draw(pen);bounds[c]=pen.bounds
    code="const {createEngine}=require('./script_helper/tuning_reference.cjs'),v=JSON.parse(require('fs').readFileSync(0,'utf8')),e=createEngine(v.settings);process.stdout.write(JSON.stringify(v.cases.map(t=>e.spacing(t,v.style).shifts)));"
    refs=json.loads(subprocess.check_output(['node','-e',code],input=json.dumps({'settings':s,'style':style,'cases':cases}).encode(),cwd=ROOT))
    moved=0
    for text,reference in zip(cases,refs):
     buf=hb.Buffer();buf.add_str(text);buf.guess_segment_properties();hb.shape(hbfont,buf,{'kern':True});got=buf.glyph_positions
     assert len(got)==len(reference),(style,text,'length')
     assert all(p.x_advance==575 and abs(p.x_offset-v)<=.50001 for p,v in zip(got,reference)),(style,strength,text,'preview/compiler parity')
     if len(text)>=5 and ' ' not in text:assert not any(reference),(text,'long run guard')
     if len(text)==1:assert reference==[0],(text,'single character')
     if text in ('((','))','[[',']]','{{','}}') and strength:assert any(reference),(style,text,'bracket run has no movement')
     moved+=sum(v!=0 for v in reference)
     for i,(a,b) in enumerate(zip(text,text[1:])):
      if a not in SYMBOLS or b not in SYMBOLS or (a not in DELIMITERS and b not in DELIMITERS):continue
      key=(a,b,i,text);counts=[]
      for delta in (575+reference[i+1]-reference[i],575+got[i+1].x_offset-got[i].x_offset):
       ck=(a,b,delta)
       if ck not in cache:
        cache[ck]=0 if bounds[a][2]<bounds[b][0]+delta else intersections(ink[a],ink[b],delta)
        contours+=1
       counts.append(cache[ck])
      if strength==0:baseline[key]=counts
      if strength==100:old_range[key]=counts
      assert all(n<=old for n,old in zip(counts,baseline[key])),(style,braces,strength,text,i,counts,'new bracket collision',baseline[key])
      if strength>100:assert all(n<=old for n,old in zip(counts,old_range[key])),(style,braces,strength,text,i,counts,'stronger collision',old_range[key])
     checks+=1
    if strength:assert moved>0
    # Turning kern off retains strict positions even with bracket runs enabled.
    buf=hb.Buffer();buf.add_str('(( )) [[ ]] {{ }}');buf.guess_segment_properties();hb.shape(hbfont,buf,{'kern':False});assert all(p.x_advance==575 and p.x_offset==0 for p in buf.glyph_positions)
    print('PASS',style,braces,strength,len(cases),'symbol-run cases',flush=True)
 print('PASS',checks,'shaping/preview cases;',contours,'unique bracket-pair clearance checks')
if __name__=='__main__':main()
