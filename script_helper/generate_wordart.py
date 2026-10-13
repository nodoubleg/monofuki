#!/usr/bin/env python3
"""Deterministic Monofuki WordArt: fontTools required; Inkscape for PNG preview.
Usage: python generate_wordart.py /path/Monofuki-Bold.ttf --out assets
Letterforms are embedded outlines, never font-family fallbacks.
"""
import argparse, hashlib, json, math
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

def fingerprint(font, text):
 gs=font.getGlyphSet(); cmap=font.getBestCmap(); upem=font['head'].unitsPerEm
 data={}
 for c in sorted(set(text)):
  p=DecomposingRecordingPen(gs);gs[cmap[ord(c)]].draw(p)
  data[c]={'advance':gs[cmap[ord(c)]].width,'outline':p.value}
 return {'upem':upem,'glyphs':data}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('font');ap.add_argument('--out',default='.');ap.add_argument('--compare-font');a=ap.parse_args()
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 f=TTFont(a.font);gs=f.getGlyphSet();cm=f.getBestCmap();word='Monofuki';s=0.245*1000/f['head'].unitsPerEm
 widths=[gs[cm[ord(c)]].width*s for c in word];total=sum(widths);start=(1280-total)/2
 paths=[];x=start
 for c,w in zip(word,widths):
  center=x+w/2;u=(center-start)/total;angle=math.atan(-45*math.pi/total*math.cos(math.pi*u));ca=math.cos(angle);sa=math.sin(angle)
  baseline=265-45*math.sin(math.pi*u)
  # Preserve each glyph shape with uniform scale and a gentle baseline rotation.
  # x'=ca*s*x+sa*s*y; y'=sa*s*x-ca*s*y.
  pen=SVGPathPen(gs); gs[cm[ord(c)]].draw(TransformPen(pen,(ca*s,sa*s,sa*s,-ca*s,center-ca*w/2,baseline-sa*w/2)))
  paths.append(pen.getCommands());x+=w
 d=' '.join(paths)
 defs=f'''<defs>
 <linearGradient id="face" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff84ff"/><stop offset=".44" stop-color="#a18aff"/><stop offset=".49" stop-color="#ecebf0"/><stop offset=".52" stop-color="#68ffd6"/><stop offset="1" stop-color="#6b50ff"/></linearGradient>
 <linearGradient id="depth" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#6b50ff"/><stop offset="1" stop-color="#201f26"/></linearGradient>
 <path id="letters" d="{d}"/>
</defs>'''
 layers=[]
 # Pale outer keyline ensures the same transparent asset works in both themes.
 for i in range(22,-1,-1):
  layers.append(f'<use href="#letters" x="{i*.9:.2f}" y="{i*.8:.2f}" fill="#ecebf0" stroke="#ecebf0" stroke-width="9" stroke-linejoin="round"/>')
 for i in range(22,0,-1):
  layers.append(f'<use href="#letters" x="{i*.9:.2f}" y="{i*.8:.2f}" fill="url(#depth)" stroke="url(#depth)" stroke-width="3.5" stroke-linejoin="round"/>')
 layers.append('<use href="#letters" fill="url(#face)" stroke="#201f26" stroke-width="3.5" stroke-linejoin="round"/>')
 svg='<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1280 330" width="1280" height="330" role="img" aria-labelledby="title desc">\n<title id="title">Monofuki</title>\n<desc id="desc">Monofuki letterforms in a gently arched 1990s WordArt-style header, with pink, violet and mint chrome and purple extrusion.</desc>\n'+defs+'\n'+'\n'.join(layers)+'\n</svg>\n'
 # xlink is used for compatibility with older SVG renderers.
 svg=svg.replace('href="#letters"','xlink:href="#letters"')
 (out/'monofuki-wordart.svg').write_text(svg)
 proof=fingerprint(f,word)
 (out/'glyph-fingerprint.json').write_text(json.dumps(proof,indent=2))
 names={str(n.nameID):n.toUnicode() for n in f['name'].names if n.nameID in (1,2,4,6)}
 manifest={'source_font_filename':Path(a.font).name,'source_font_sha256':hashlib.sha256(Path(a.font).read_bytes()).hexdigest(),'source_names':names,'text':word,'outline_fingerprint_sha256':hashlib.sha256(json.dumps(proof,sort_keys=True).encode()).hexdigest(),'dimensions':[1280,330],'font_outline_equivalence':None}
 if a.compare_font:
  same=proof==fingerprint(TTFont(a.compare_font),word);manifest['font_outline_equivalence']=same
  if not same: raise SystemExit('Comparison font glyph outlines differ; rebuild using actual Monofuki font.')
 (out/'provenance.json').write_text(json.dumps(manifest,indent=2))
 print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
