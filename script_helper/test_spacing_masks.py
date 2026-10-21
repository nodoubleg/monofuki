#!/usr/bin/env python3
"""Protect contextual kerning when neighboring glyphs use different feature masks."""
import json
import uharfbuzz as hb
from tuning_compiler import compile_font,STYLES
from test_tuning import ROOT,oracle

def shape(data,text,direction,features):
 font=hb.Font(hb.Face(data));buf=hb.Buffer();buf.add_utf8(text.encode());buf.guess_segment_properties()
 if direction:buf.direction=direction
 hb.shape(font,buf,features)
 return [(i.codepoint,i.cluster,p.x_advance,p.y_advance,p.x_offset,p.y_offset) for i,p in zip(buf.glyph_infos,buf.glyph_positions)]
settings=json.loads((ROOT/'src/tuning/defaults.json').read_text())
settings['experiments'].update(smartStrength=400,symbolEnabled=True,symbolStrength=400)
geometry=oracle(settings)
texts=['A\u200cVVA V\u200ciA VVA\u200c','minimum Toffee MWiMWiMWi', 'a ... b === c +-*/ d ..... e ======== f','A\u0301 V\u0308A ÁÉÅÜ ď7ŁŁ ď7TŁ','VVA\u200dVYA\u200bWYA\u2060A','a::b a!=b x->y']
count=0
for style in STYLES:
 suffix=style.replace('BoldItalic','Bold-Italic')
 data,_=compile_font((ROOT/'export/tuning-base'/f'Monofuki-{suffix}.otf').read_bytes(),geometry[style],settings,style)
 for text in texts:
  length=len(text.encode())
  for direction in(None,'ltr','rtl'):
   enabled=shape(data,text,direction,{'kern':True});disabled=shape(data,text,direction,{'kern':False})
   for start,end in((0,1),(3,9),(1,length-1),(length-2,length)):
    actual=shape(data,text,direction,{'kern':[(0,2**32-1,1),(start,end,0)]})
    expected=[off if start<=on[1]<end else on for on,off in zip(enabled,disabled)]
    assert actual==expected,(style,text,direction,start,end,actual,expected)
    count+=1
print('PASS',count,'partial feature-mask cases, symbols/marks/default-ignorables, LTR/RTL')
