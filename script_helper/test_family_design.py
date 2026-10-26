#!/usr/bin/env python3
"""Behavioral regressions; in-memory fixtures never change historical fonts."""
import copy
import contextlib
import io
import os
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fontTools.ttLib import TTFont

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

import family_design as d


def fixture(path, h_width=600, proportional=False, slashes=False, stem_width=80, upm=1000, extent=700):
    builder=FontBuilder(upm,isTTF=True)
    chars='Hn0ΩæQΠ/\\ÁǺ'
    order=['.notdef']+[f'g{i}' for i in range(len(chars))]
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap({ord(c):g for c,g in zip(chars,order[1:])})
    glyphs={}
    factor=upm/1000
    for name in order:
        pen=TTGlyphPen(None)
        if slashes and name in (order[chars.index('/')+1],order[chars.index(chr(92))+1]):
            points=[(50,0),(150,0),(500,700),(400,700)]
            if name==order[chars.index(chr(92))+1]: points=[(600-x,y) for x,y in points]
            pen.moveTo(tuple(v*factor for v in points[0]))
            for point in points[1:]: pen.lineTo(tuple(v*factor for v in point))
            pen.closePath()
        else:
            for x in (50,400):
                pen.moveTo((x*factor,0));pen.lineTo(((x+stem_width)*factor,0));pen.lineTo(((x+stem_width)*factor,extent*factor));pen.lineTo((x*factor,extent*factor));pen.closePath()
        glyphs[name]=pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({g:((int((h_width if g==order[1] else 600)*factor)),int(50*factor)) for g in order})
    builder.setupHorizontalHeader(ascent=800,descent=-200)
    builder.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200)
    builder.setupNameTable(dict(familyName='Test',styleName='Regular',uniqueFontIdentifier='Test',fullName='Test',psName='Test'))
    builder.setupPost()
    builder.setupMaxp()
    builder.font.recalcTimestamp=False
    builder.font['head'].created=builder.font['head'].modified=3400000000
    builder.save(path)
    return dict(id='fixture',path=str(path),sha256=d.sha(path),weight='Light',width='proportional' if proportional else 'mono',role='current',variant='default')


class AdvisoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.rules=d.load_rules()
    def tearDown(self): self.tmp.cleanup()
    def font(self,**kwargs):
        entry=fixture(self.root/'fixture.ttf',**kwargs)
        return d.Font(entry,self.root)

    def test_cross_section_and_normalization(self):
        font=self.font()
        self.assertAlmostEqual(font.stem('H',.2),.08)
        self.assertAlmostEqual(font.advance('H'),.6)
        with self.assertRaises(ValueError): font.stem('H',.8)
        # Rectangles have no designated slash edge; never invent an angle.
        with self.assertRaises(ValueError): font.angle('/')

    def test_designated_slash_angles(self):
        font=self.font(slashes=True)
        self.assertAlmostEqual(font.angle('/'),63.4349488229)
        self.assertAlmostEqual(font.angle(chr(92)),font.angle('/'))

    def test_curve_section_nonzero_winding_and_unsupported_endpoint(self):
        pen=d.SectionPen(None,20)
        pen.moveTo((0,0));pen.curveTo((100,0),(100,100),(0,100));pen.lineTo((0,0));pen.closePath()
        spans=pen.intervals()
        self.assertEqual(len(spans),1)
        self.assertAlmostEqual(spans[0][0],0)
        self.assertGreater(spans[0][1],50)
        other=d.SectionPen(None,0)
        other.moveTo((0,0))
        with self.assertRaises(ValueError): other.lineTo((10,100))

    def test_conflict_stays_in_worksheet_and_exits_zero(self):
        f=self.font(h_width=640)
        inputs=self.root/'inputs.json'
        inputs.write_text(json.dumps(dict(fonts=[f.entry])))
        req=dict(title='TEST EXAMPLE',notice='Synthetic fixture; not feedback.',items=[dict(character='H',label='Example',request='Widen H by 40',current='fixture',proposed='fixture',rule_ids=['MF-STEM-001'])])
        request_path=self.root/'requests.json';request_path.write_text(json.dumps(req))
        before=(self.root/'fixture.ttf').read_bytes()
        process=subprocess.run([sys.executable,str(Path(d.__file__)),'generate','--inputs',str(inputs),'--requests',str(request_path),'--out',str(self.root/'out')],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        report=json.loads((self.root/'out/report.json').read_text())
        issue=next(r for r in report['findings'] if r['rule_id']=='MF-MONO-001')
        self.assertEqual(issue['status'],'advisory')
        self.assertNotIn('MF-MONO-001',req['items'][0]['rule_ids'])
        self.assertEqual(issue['observed']['H'],.64)
        sheet=(self.root/'out/worksheet.html').read_text()
        for visible in ('Widen H by 40','MF-MONO-001','Expected:','Observed/proposed:','Reason:','Decision:','PROPOSED'):
            self.assertIn(visible,sheet)
        self.assertEqual(before,(self.root/'fixture.ttf').read_bytes())

    def test_guide_accepts_new_font_ids_and_missing_glyph_sheet(self):
        f=self.font()
        f.entry['id']='a-new-review-id'
        req=dict(title='Coverage example',notice='Test only',items=[dict(character=chr(0x10ffff),label='Missing glyph',request='Inspect unsupported character',current=f.entry['id'],proposed=f.entry['id'],rule_ids=['MF-MONO-001'])])
        outputs,report=d.generate(self.rules,{f.entry['id']:f},self.root/'out',req)
        self.assertIn('<svg',outputs['guide.html'])
        self.assertIn('a-new-review-id',outputs['guide.html'])
        self.assertIn('Unsupported: Missing U+10FFFF',outputs['worksheet.html'])
        self.assertIn('Advance: unmeasured',outputs['worksheet.html'])

    def test_proportional_scope_and_visible_exception(self):
        f=self.font(h_width=640,proportional=True)
        rows=d.evaluate(self.rules,{'fixture':f})
        self.assertFalse(any(r['rule_id']=='MF-MONO-001' for r in rows))
        self.assertTrue(any(r['rule_id']=='MF-PROP-001' and r['status']=='visual-review' for r in rows))
        f.entry.update(weight='Black',width='mono',variant='original-g')
        rows=d.evaluate(self.rules,{'fixture':f})
        optical=next(r for r in rows if r['rule_id']=='MF-OPTICAL-001')
        self.assertEqual(optical['exceptions'][0]['id'],'MF-EX-001')
        self.assertEqual(optical['status'],'visual-review')

    def test_missing_glyph_is_unmeasured_and_hash_mismatch_is_error(self):
        f=self.font()
        del f.cmap[ord('H')]
        row=next(r for r in d.evaluate(self.rules,{'fixture':f}) if r['rule_id']=='MF-MONO-001')
        self.assertEqual(row['status'],'unmeasured')
        with self.assertRaises(ValueError): d.Font(dict(f.entry,sha256='0'*64),self.root)

    def test_invalid_rules_stale_outputs_and_no_silent_rewrite(self):
        bad=copy.deepcopy(self.rules);bad['rules'].append(bad['rules'][0])
        path=self.root/'bad.yaml';path.write_text(json.dumps(bad))
        with self.assertRaises(ValueError): d.load_rules(path)
        for tolerance in (-1,float('nan')):
            bad=copy.deepcopy(self.rules);bad['rules'][0]['tolerance']=tolerance
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError): d.load_rules(path)
        f=self.font();inputs=self.root/'inputs.json';inputs.write_text(json.dumps(dict(fonts=[f.entry])))
        args=['generate','--inputs',str(inputs),'--out',str(self.root/'out')]
        self.assertEqual(d.main(args),0)
        self.assertEqual(d.main(args+['--verify']),0)
        (self.root/'out/guide.md').write_text('stale')
        self.assertEqual(d.main(args+['--verify']),2)
        self.assertEqual((self.root/'out/guide.md').read_text(),'stale')

    def entries(self):
        fonts={}
        for weight,width in [('Light',50),('Regular',80),('Black',120)]:
            entry=fixture(self.root/(weight+'.ttf'),stem_width=width)
            entry.update(id=weight,weight=weight)
            fonts[weight]=d.Font(entry,self.root)
        return fonts

    def run_main(self,args):
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()) as err:
            code=d.main(args)
        self.assertNotIn('Traceback',err.getvalue())
        return code

    def test_proposed_weight_order_is_checked_and_visible(self):
        fonts=self.entries()
        entry=fixture(self.root/'thin-black.ttf',stem_width=30)
        entry.update(id='Black-next',weight='Black',role='proposed')
        fonts[entry['id']]=d.Font(entry,self.root)
        req=dict(title='Test proposal',notice='Synthetic fixture',items=[dict(character='H',label='Thin Black',request='Propose thinner Black stems',current='Black',proposed=entry['id'],rule_ids=[])])
        outputs,report=d.generate(self.rules,fonts,self.root/'out',req)
        proposal=next(r for r in report['findings'] if r['rule_id']=='MF-WEIGHT-001' and r['font']==entry['id'])
        self.assertEqual(proposal['status'],'advisory')
        self.assertEqual(proposal['members']['Black'],entry['id'])
        self.assertIn('MF-WEIGHT-001 / Black-next / advisory',outputs['worksheet.html'])
        # An explicit worksheet proposal is also checked when reusing a current font.
        fonts[entry['id']].entry['role']='current'
        outputs,report=d.generate(self.rules,fonts,self.root/'second',req)
        self.assertTrue(any(r['rule_id']=='MF-WEIGHT-001' and r['font']==entry['id'] and r['status']=='advisory' for r in report['findings']))

    def test_weight_rule_honors_target_and_variant_context(self):
        fonts=self.entries()
        rules=copy.deepcopy(self.rules)
        rule=next(r for r in rules['rules'] if r['method']=='weight-order')
        rule.update(targets=['Z'],examples=['Z'])
        d.validate_rules(rules)
        row=next(r for r in d.evaluate(rules,fonts) if r['rule_id']==rule['id'])
        self.assertEqual(row['status'],'unmeasured')
        self.assertEqual(row['observed'],{})
        self.assertIn('U+005A',row['reason'])
        entry=fixture(self.root/'prop.ttf',proportional=True)
        entry.update(id='prop',weight='Black',role='proposed')
        fonts['prop']=d.Font(entry,self.root)
        req=dict(title='Proportional example',notice='Test only',items=[dict(character='H',label='Independent scope',request='Propose proportional H',current='prop',rule_ids=[])])
        outputs,_=d.generate(self.rules,fonts,self.root/'out',req)
        self.assertNotIn('MF-WEIGHT-001',outputs['worksheet.html'])

    def test_missing_target_preserves_known_conflict(self):
        entry=fixture(self.root/'partial.ttf',h_width=640)
        font=TTFont(self.root/'partial.ttf')
        for table in font['cmap'].tables:
            if table.isUnicode(): table.cmap.pop(ord('Ω'),None)
        font.save(self.root/'partial.ttf')
        entry['sha256']=d.sha(self.root/'partial.ttf')
        f=d.Font(entry,self.root)
        row=next(r for r in d.evaluate(self.rules,{'fixture':f}) if r['rule_id']=='MF-MONO-001')
        self.assertEqual(row['status'],'advisory')
        self.assertEqual(row['observed']['H'],.64)
        self.assertIn('Ω',row['unmeasured_targets'])
        self.assertIn('0.600000',row['expected'])

    def test_verified_snapshot_survives_rebuild_between_reads(self):
        entry=fixture(self.root/'original.ttf',h_width=640)
        replacement=fixture(self.root/'replacement.ttf',h_width=600)
        original_read=Path.read_bytes
        alternate=original_read(Path(replacement['path']))
        def rebuilding_read(path):
            blob=original_read(path)
            if path.resolve()==Path(entry['path']).resolve(): path.write_bytes(alternate)
            return blob
        with patch.object(Path,'read_bytes',rebuilding_read):
            f=d.Font(entry,self.root)
        self.assertEqual(f.digest,entry['sha256'])
        self.assertAlmostEqual(f.advance('H'),.64)
        self.assertNotEqual(d.sha(Path(entry['path'])),f.digest)

    def test_no_unicode_cmap_stays_cleanly_unmeasured(self):
        entry=fixture(self.root/'no-cmap.ttf')
        font=TTFont(entry['path']);font['cmap'].tables=[];font.save(entry['path'])
        entry['sha256']=d.sha(entry['path'])
        f=d.Font(entry,self.root)
        self.assertEqual(f.cmap,{})
        outputs,report=d.generate(self.rules,{'fixture':f},self.root/'out')
        self.assertTrue(any(r['status']=='unmeasured' for r in report['findings']))
        self.assertIn('Unsupported: Missing',outputs['guide.html'])

    def test_shared_frame_encloses_tall_glyphs_and_normalizes_upm(self):
        entries=[fixture(self.root/f'{upm}.ttf',upm=upm,extent=1300) for upm in (1000,2000)]
        fonts=[d.Font(e,self.root) for e in entries]
        frame=d.shared_frame(fonts,['Á','Ǻ'])
        self.assertGreater(frame[3],1.3)
        a=fonts[0].svg('Ǻ',frame=frame);b=fonts[1].svg('Ǻ',frame=frame)
        self.assertEqual(a.split('viewBox="')[1].split('"')[0],b.split('viewBox="')[1].split('"')[0])
        self.assertIn('scale(0.001,-0.001)',a)
        self.assertIn('scale(0.0005,-0.0005)',b)

    def test_no_request_regeneration_cannot_certify_stale_worksheet(self):
        f=self.font();inputs=self.root/'inputs.json';inputs.write_text(json.dumps(dict(fonts=[f.entry])))
        request=self.root/'requests.json'
        req=dict(title='OLD PROPOSAL',notice='Test only',items=[dict(character='H',label='Old',request='OLD REQUEST',current='fixture',rule_ids=[])])
        request.write_text(json.dumps(req))
        args=['generate','--inputs',str(inputs),'--out',str(self.root/'out')]
        self.assertEqual(self.run_main(args+['--requests',str(request)]),0)
        self.assertEqual(self.run_main(args),0)
        sheet=self.root/'out/worksheet.html'
        self.assertNotIn('OLD REQUEST',sheet.read_text())
        self.assertIn('No worksheet requests supplied',sheet.read_text())
        self.assertEqual(self.run_main(args+['--verify']),0)
        sheet.write_text('stale proposal')
        self.assertEqual(self.run_main(args+['--verify']),2)

    def test_input_aliases_and_symlinks_do_not_modify_any_source(self):
        f=self.font();before=f.path.read_bytes()
        for kind in ('symlink','hardlink','direct'):
            out=self.root/kind;out.mkdir()
            target=out/'guide.html'
            if kind=='symlink': target.symlink_to(f.path)
            elif kind=='hardlink': os.link(f.path,target)
            else:
                target.write_bytes(before)
                f=d.Font(dict(f.entry,path=str(target)),self.root)
            with self.assertRaises(ValueError): d.generate(self.rules,{'fixture':f},out)
            self.assertEqual(f.path.read_bytes(),before)
            self.assertFalse((out/'report.json').exists())
        # A source manifest may also collide with a managed output filename.
        out=self.root/'manifest-alias';out.mkdir()
        inputs=out/'report.json';inputs.write_text(json.dumps(dict(fonts=[f.entry])))
        saved=inputs.read_bytes()
        self.assertEqual(self.run_main(['generate','--inputs',str(inputs),'--out',str(out)]),2)
        self.assertEqual(inputs.read_bytes(),saved)

    def test_prepare_failure_preserves_existing_output_set(self):
        f=self.font();out=self.root/'out'
        d.generate(self.rules,{'fixture':f},out)
        before={p.name:p.read_bytes() for p in out.iterdir()}
        write=Path.write_bytes
        count=0
        def failing_write(path,content):
            nonlocal count
            count+=1
            if count==2: raise OSError('fixture write failure')
            return write(path,content)
        with patch.object(Path,'write_bytes',failing_write),self.assertRaises(OSError):
            d.generate(self.rules,{'fixture':f},out)
        self.assertEqual(before,{p.name:p.read_bytes() for p in out.iterdir()})

    def test_interrupted_replacement_is_detected_then_repaired(self):
        f=self.font();out=self.root/'out';inputs=self.root/'inputs.json'
        inputs.write_text(json.dumps(dict(fonts=[f.entry])))
        args=['generate','--inputs',str(inputs),'--out',str(out)]
        self.assertEqual(self.run_main(args),0)
        before=(out/'output-manifest.json').read_bytes()
        f.entry['role']='alternate';inputs.write_text(json.dumps(dict(fonts=[f.entry])))
        replace=os.replace
        count=0
        def failing_replace(source,target):
            nonlocal count
            count+=1
            if count==2: raise OSError('fixture replacement interruption')
            replace(source,target)
        with patch.object(d.os,'replace',failing_replace):
            self.assertEqual(self.run_main(args),2)
        self.assertEqual((out/'output-manifest.json').read_bytes(),before)
        self.assertEqual(self.run_main(args+['--verify']),2)
        self.assertEqual(self.run_main(args),0)
        self.assertEqual(self.run_main(args+['--verify']),0)

    def test_manifest_rules_and_request_schema_fail_before_writes(self):
        f=self.font();valid=dict(fonts=[f.entry]);inputs=self.root/'inputs.json'
        for malformed in ([],{'fonts':'abc'},dict(fonts=[{k:v for k,v in f.entry.items() if k!='variant'}]),dict(fonts=[dict(f.entry,wieght='Black')])):
            inputs.write_text(json.dumps(malformed))
            self.assertEqual(self.run_main(['generate','--inputs',str(inputs),'--out',str(self.root/'out')]),2)
            self.assertFalse((self.root/'out').exists())
        inputs.write_text(json.dumps(valid))
        req=dict(title='Test',notice='Test only',items=[dict(character='H',label='Test',request='Retain this proposal',current='fixture',proposd='fixture',rule_ids=[])])
        request=self.root/'request.json';request.write_text(json.dumps(req))
        self.assertEqual(self.run_main(['generate','--inputs',str(inputs),'--requests',str(request),'--out',str(self.root/'out')]),2)
        for field,value in [('scope',[]),('targets','Hn'),('examples',['HH'])]:
            bad=copy.deepcopy(self.rules);bad['rules'][0][field]=value
            with self.assertRaises(ValueError): d.validate_rules(bad)
        bad=copy.deepcopy(self.rules);bad['exceptions'].append(bad['exceptions'][0])
        with self.assertRaises(ValueError): d.validate_rules(bad)
        bad=copy.deepcopy(self.rules);bad['exceptions'][0]['scope']['variant']='original-g'
        with self.assertRaises(ValueError): d.validate_rules(bad)
        inputs.write_text('{"fonts": [], "fonts": []}')
        self.assertEqual(self.run_main(['generate','--inputs',str(inputs),'--out',str(self.root/'out')]),2)

    def test_cross_process_hash_seeds_produce_identical_outputs(self):
        fonts=self.entries();inputs=self.root/'inputs.json'
        inputs.write_text(json.dumps(dict(fonts=[f.entry for f in fonts.values()])))
        directories=[]
        for seed in ('1','2'):
            out=self.root/('seed-'+seed);directories.append(out)
            result=subprocess.run([sys.executable,str(Path(d.__file__)),'generate','--inputs',str(inputs),'--out',str(out)],env=dict(os.environ,PYTHONHASHSEED=seed,PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
        for name in ('guide.html','guide.md','worksheet.html','report.json','output-manifest.json'):
            self.assertEqual((directories[0]/name).read_bytes(),(directories[1]/name).read_bytes(),name)

    def test_output_receipt_binds_all_text_and_sources(self):
        f=self.font();fonts={'fixture':f};out=self.root/'out'
        outputs,report=d.generate(self.rules,fonts,out)
        receipt=json.loads(outputs['output-manifest.json'])
        for name,digest in receipt['files'].items(): self.assertEqual(d.sha(out/name),digest)
        old=report['source_digest']
        f.entry['role']='alternate'
        _,report=d.generate(self.rules,fonts,self.root/'other')
        self.assertNotEqual(old,report['source_digest'])
        self.assertIn('generator_sha256',report)


if __name__=='__main__': unittest.main()
