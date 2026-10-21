#!/usr/bin/env python3
"""Regression cases for edited 7 bars and italic pairs above the legacy range."""
import copy
import io
import json
import subprocess
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.misc.bezierTools import segmentSegmentIntersections
from test_tuning import ROOT, STYLES, oracle, shape
from tuning_compiler import compile_font, replay

class Segments(BasePen):
    def __init__(self):
        super().__init__(None)
        self.segments=[]
    def _moveTo(self,p): self.first=p
    def _lineTo(self,p):
        if self._getCurrentPoint()!=p:self.segments.append((self._getCurrentPoint(),p))
    def _curveToOne(self,p1,p2,p3):self.segments.append((self._getCurrentPoint(),p1,p2,p3))
    def _qCurveToOne(self,p1,p2):self.segments.append((self._getCurrentPoint(),p1,p2))
    def _closePath(self):self._lineTo(self.first)
    def _endPath(self):pass

def intersections(left,right,distance):
    shifted=[tuple((x+distance,y) for x,y in seg)for seg in right]
    return sum(0<=hit.t1<=1 and 0<=hit.t2<=1 for a in left for b in shifted for hit in segmentSegmentIntersections(a,b))

def segments(draw):
    pen=Segments();draw(pen);return pen.segments

def main():
    defaults=json.loads((ROOT/'src/tuning/defaults.json').read_text());checks=0
    for y,words in [(250,['ď7ŁŁ']),(550,['ď7TŁ']),(None,['VVA','VYA','WYA'])]:
        baseline={}
        for strength in (94,100,200,400):
            settings=copy.deepcopy(defaults)
            if y is not None:settings['sevenCrossbar'].update(enabled=True,angle=20,length=280,thickness=100,x=425,y=y)
            settings['experiments']['smartStrength']=strength
            geometry=oracle(settings)
            for style in STYLES:
                suffix=style.replace('BoldItalic','Bold-Italic')
                data,_=compile_font((ROOT/'export/tuning-base'/f'Monofuki-{suffix}.otf').read_bytes(),geometry[style],settings,style)
                font=TTFont(io.BytesIO(data));gs=font.getGlyphSet();cmap=font.getBestCmap()
                code="const {createEngine}=require('./script_helper/tuning_reference.cjs'),v=JSON.parse(require('fs').readFileSync(0,'utf8')),e=createEngine(v.settings);process.stdout.write(JSON.stringify(v.words.map(t=>e.spacing(t,v.style))));"
                preview=json.loads(subprocess.check_output(['node','-e',code],input=json.dumps({'settings':settings,'style':style,'words':words}).encode(),cwd=ROOT))
                for word,reference in zip(words,preview):
                    actual=shape(data,word,True)
                    assert all(p[0]==575 and abs(p[1]-s)<=0.5 for p,s in zip(actual,reference['shifts'])),(style,word,strength)
                    for index in ([1] if y is not None else range(len(word)-1)):
                        a,b=word[index:index+2]
                        vector=[segments(lambda p:replay(geometry[style][c],p))for c in (a,b)]
                        binary=[segments(gs[cmap[ord(c)]].draw)for c in (a,b)]
                        counts=(intersections(*vector,575+reference['shifts'][index+1]-reference['shifts'][index]),intersections(*binary,575+actual[index+1][1]-actual[index][1]))
                        key=(style,word,index)
                        if strength==100:baseline[key]=counts
                        if strength>100:assert all(n<=old for n,old in zip(counts,baseline[key])),(style,word,strength,counts,baseline[key])
                        if strength in (94,100) and y is not None and style in ('Regular','Bold'):assert counts==(0,0),(style,word,strength,counts)
                        checks+=1
                print('PASS',style,'bar y='+str(y),'strength',strength,flush=True)
    print('PASS',checks,'preview/compiled contour-pair checks; fixed advances; nearest-unit shaping parity')

if __name__=='__main__':main()
