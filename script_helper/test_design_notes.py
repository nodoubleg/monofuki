"""Current intent and exceptions stay soft, scoped, reproducible and nonblocking."""
import copy
import tempfile
import unittest
from pathlib import Path
from fontTools.pens.ttGlyphPen import TTGlyphPen
import family_design as d
import design_notes as n
from test_family_design import fixture


class CurrentNotesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.rules=d.load_rules()
        entry=fixture(self.root/'font.ttf',h_width=640)
        self.font=d.Font(entry,self.root)
    def tearDown(self): self.tmp.cleanup()
    def note(self,kind='approved-exception'):
        scope=dict(characters=['H'],weight='Light',width='mono',variant='default')
        return dict(id='TEST-INTENT',kind=kind,scope=scope,rule_ids=['MF-MONO-001'],
                    note='Synthetic current exception: retain the wider H cell.',
                    rationale='Fixture only; no real owner approval is claimed.',
                    implementation='Intent only. This test does not apply a drawing.',
                    evidence=['Test fixture, not owner feedback.'],
                    basis=n.capture_basis(scope,['MF-MONO-001'],self.font,self.rules))
    def request(self,c='H'):
        return dict(title='Notes test',notice='Synthetic fixture, no owner decision.',items=[dict(character=c,label='Proposed',request='Retain the requested drawing',current='fixture',proposed='fixture',approved='fixture',rule_ids=[])])
    def generate(self,notes,fonts=None,request=None,rules=None):
        return d.generate(rules or self.rules,fonts or {'fixture':self.font},self.root/'out',request or self.request(),notes=dict(version=1,notes=notes))
    def test_current_exception_is_distinct_but_does_not_suppress_advisory(self):
        outputs,report=self.generate([self.note()])
        row=next(r for r in report['findings'] if r['rule_id']=='MF-MONO-001')
        self.assertEqual(row['status'],'advisory')
        self.assertEqual(row['target_interpretations']['fixture']['H'],'approved-exception')
        self.assertNotEqual(row['interpretation'],'approved-exception')
        self.assertIn('APPROVED EXCEPTION',outputs['worksheet.html'])
        self.assertIn('Retain the requested drawing',outputs['worksheet.html'])
        self.assertIn('Intent only',outputs['worksheet.html'])
    def test_changed_relevant_geometry_or_rule_reconsiders_without_veto(self):
        note=self.note()
        self.font.font['hmtx'][self.font.name('H')]=(680,50)
        outputs,report=self.generate([note])
        self.assertEqual(report['current_notes'][0]['status'],'reconsider-note')
        self.assertIn('PROPOSED',outputs['worksheet.html'])
        self.assertIn('glyph outline or advance changed',outputs['worksheet.html'])
        rules=copy.deepcopy(self.rules);rules['rules'][0]['tolerance']=.01
        outputs,report=self.generate([note],rules=rules)
        self.assertIn('rule basis changed',outputs['worksheet.html'])
    def test_unrelated_glyph_and_editorial_rule_changes_do_not_stale_note(self):
        note=self.note()
        self.font.font['hmtx'][self.font.name('Q')]=(900,50)
        rules=copy.deepcopy(self.rules);rules['rules'][0]['provenance']='Editorial evidence clarification'
        outputs,report=self.generate([note],rules=rules)
        self.assertEqual(report['current_notes'][0]['status'],'current-note')
    def test_composite_dependency_change_reconsiders_glyph_note(self):
        glyph=self.font.name('æ');base=self.font.name('H')
        pen=TTGlyphPen(self.font.font.getGlyphSet());pen.addComponent(base,(1,0,0,1,0,0))
        self.font.font['glyf'][glyph]=pen.glyph()
        note=self.note('choice');note['scope']['characters']=['æ'];note['basis']=n.capture_basis(note['scope'],note['rule_ids'],self.font,self.rules)
        self.font.font['glyf'][base].coordinates[0]=(75,0)
        self.assertEqual(n.assess(note,self.font,'æ',self.rules)['status'],'reconsider-note')
    def test_scope_is_exact_and_raw_reference_cannot_claim_choice(self):
        note=self.note()
        for dimension,value in [('variant','alternate'),('width','proportional'),('weight','Black')]:
            other=copy.deepcopy(note);other['scope'][dimension]=value
            _,report=self.generate([other])
            self.assertEqual(report['current_notes'],[])
        outputs,_=self.generate([])
        self.assertNotIn('RECORDED CHOICE / CURRENT',outputs['worksheet.html'])
        self.assertIn('CURRENT / REFERENCE (choice not recorded)',outputs['worksheet.html'])
        note=self.note('choice');outputs,_=self.generate([note])
        self.assertIn('RECORDED CHOICE / CURRENT',outputs['worksheet.html'])
    def test_missing_basis_changed_scope_and_overlaps_are_soft(self):
        note=self.note();del note['basis']
        outputs,report=self.generate([note])
        self.assertEqual(report['current_notes'][0]['status'],'reconsider-note')
        self.assertIn('PROPOSED',outputs['worksheet.html'])
        a=self.note();b=copy.deepcopy(a);b['id']='TEST-OTHER'
        _,report=self.generate([a,b])
        self.assertTrue(all(row['status']=='reconsider-note' for row in report['current_notes']))
        a=self.note();a['scope']['characters'].append('n')
        _,report=self.generate([a])
        self.assertTrue(all(row['status']=='reconsider-note' for row in report['current_notes']))
    def test_retired_rule_and_previous_forms_do_not_block_current_proposal(self):
        note=self.note();note['rule_ids']=['MF-RETIRED-001']
        _,report=self.generate([note])
        self.assertEqual(report['current_notes'][0]['status'],'reconsider-note')
        self.font.entry['role']='previous'
        # It is a historical comparison only, not a current/proposed observation.
        _,report=d.generate(self.rules,{'fixture':self.font},self.root/'history',notes=dict(version=1,notes=[self.note()]))
        self.assertEqual(report['current_notes'],[])
    def test_open_question_never_labels_a_reference_as_settled(self):
        note=self.note('open-question');del note['basis']
        outputs,report=self.generate([note])
        self.assertEqual(report['current_notes'][0]['status'],'open-question')
        self.assertNotIn('RECORDED CHOICE / CURRENT',outputs['worksheet.html'])
    def test_exception_for_h_never_labels_q_as_excepted(self):
        note=self.note()
        self.font.font['hmtx'][self.font.name('Q')]=(900,50)
        outputs,report=self.generate([note],request=self.request('Q'))
        self.assertNotIn('APPROVED EXCEPTION',outputs['worksheet.html'])
        self.assertNotIn(' / approved-exception',outputs['worksheet.html'])
        row=next(r for r in report['findings'] if r['rule_id']=='MF-MONO-001')
        self.assertNotEqual(row['target_interpretations']['fixture']['Q'],'approved-exception')
        self.assertIn('unresolved-advisory',outputs['worksheet.html'])
    def test_recorded_choice_remains_recorded_without_or_after_basis(self):
        note=self.note('choice');del note['basis']
        outputs,_=self.generate([note])
        self.assertIn('RECORDED CHOICE / CURRENT / RECONSIDER NOTE',outputs['worksheet.html'])
        self.assertNotIn('choice not recorded',outputs['worksheet.html'])
    def test_note_shape_validation_uses_clean_value_errors(self):
        for key,value in [('weight',[]),('width',{})]:
            note=self.note();note['scope'][key]=value
            with self.assertRaises(ValueError): n.validate(dict(version=1,notes=[note]),self.rules)
        with self.assertRaises(ValueError): n.validate(dict(version=True,notes=[]),self.rules)

    def test_real_initial_notes_are_narrow_and_no_exception_is_invented(self):
        notes=d.read_json(d.NOTES)
        n.validate(notes,self.rules)
        settled={c for note in notes['notes'] if note['kind']=='choice' for c in note['scope']['characters']}
        self.assertEqual(settled,{'æ','Ω'})
        self.assertFalse(any(note['kind']=='approved-exception' for note in notes['notes']))
        self.assertTrue(all(note['kind']=='open-question' for note in notes['notes'] if set(note['scope']['characters'])&{'Q','Π'}))


if __name__=='__main__': unittest.main()
