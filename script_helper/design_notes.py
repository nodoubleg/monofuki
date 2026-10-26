"""Lightweight current design notes. Read-only; notes never veto a proposal."""
import hashlib
import json
from fontTools.pens.recordingPen import DecomposingRecordingPen


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def rule_basis(rule):
    keys=('id','scope','targets','method','expected','tolerance','y_em','reference')
    return digest({key:rule[key] for key in keys if key in rule})


def glyph_basis(font, c):
    pen=DecomposingRecordingPen(font.gs)
    font.gs[font.name(c)].draw(pen)
    operations=[]
    for op,points in pen.value:
        operations.append([op,[None if point is None else [round(value/font.upm,9) for value in point] for point in points]])
    # Decomposition includes component dependencies; other glyphs and font metadata do not.
    return digest({'version':1,'operations':operations,'advance_em':round(font.advance(c),9)})


def capture_basis(scope, rule_ids, font, rules):
    by_id={r['id']:r for r in rules['rules']}
    return {'scope':digest(scope),'rules':{rid:rule_basis(by_id[rid]) for rid in rule_ids},
            'glyphs':{c:glyph_basis(font,c) for c in scope['characters']}}


def validate(data, rules):
    def obj(value,required,optional,label):
        if not isinstance(value,dict) or set(value)-set(required)-set(optional) or set(required)-set(value):
            raise ValueError('Malformed '+label)
    def text(value,label):
        if not isinstance(value,str) or not value.strip(): raise ValueError('Blank/invalid '+label)
    def strings(value,label,empty=False):
        if not isinstance(value,list) or (not value and not empty): raise ValueError('Invalid '+label)
        for item in value: text(item,label)
        if len(set(value))!=len(value): raise ValueError('Duplicate '+label)
    def hash_value(value):
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Invalid note basis digest')
    obj(data,{'version','notes'},set(),'current design notes')
    if type(data['version']) is not int or data['version']!=1 or not isinstance(data['notes'],list): raise ValueError('Expected note version1 and notes array')
    ids=set();rule_ids={r['id'] for r in rules['rules']}
    for note in data['notes']:
        obj(note,{'id','kind','scope','rule_ids','note','rationale'}, {'evidence','implementation','basis'},'design note')
        for key in ('id','kind','note','rationale'): text(note[key],key)
        if note['id'] in ids: raise ValueError('Duplicate design note ID')
        ids.add(note['id'])
        if note['kind'] not in {'choice','approved-exception','open-question'}: raise ValueError('Unknown note kind')
        scope=note['scope'];obj(scope,{'characters','weight','width','variant'},set(),'note scope')
        strings(scope['characters'],'note characters')
        for c in scope['characters']:
            if len(c)!=1 or 0xD800<=ord(c)<=0xDFFF: raise ValueError('Note target must be one Unicode scalar')
        text(scope['weight'],'note weight');text(scope['width'],'note width')
        if scope['weight'] not in {'Light','Regular','Black'} or scope['width'] not in {'mono','proportional'}:
            raise ValueError('Unknown note weight/width')
        text(scope['variant'],'note variant')
        strings(note['rule_ids'],'note rule IDs',empty=note['kind']!='approved-exception')
        if 'evidence' in note: strings(note['evidence'],'note evidence',empty=True)
        if 'implementation' in note: text(note['implementation'],'implementation note')
        if 'basis' in note:
            basis=note['basis'];obj(basis,{'scope','rules','glyphs'},set(),'note basis')
            hash_value(basis['scope'])
            for key in ('rules','glyphs'):
                if not isinstance(basis[key],dict): raise ValueError('Invalid note basis mapping')
                for item,value in basis[key].items(): text(item,'basis key');hash_value(value)
            # Missing/old rule IDs or glyph keys are reconsideration, never a design veto.
    return data


def matches(note,font,c):
    scope=note['scope']
    return c in scope['characters'] and all(font.entry[k]==scope[k] for k in ('weight','width','variant'))


def assess(note,font,c,rules):
    reasons=[];basis=note.get('basis');by_id={r['id']:r for r in rules['rules']}
    if basis:
        if basis['scope']!=digest(note['scope']): reasons.append('note scope changed')
        if set(basis['rules'])!=set(note['rule_ids']): reasons.append('linked rules changed')
        for rid in note['rule_ids']:
            if rid not in by_id or basis['rules'].get(rid)!=rule_basis(by_id[rid]): reasons.append('rule basis changed or unavailable: '+rid)
        if set(basis['glyphs'])!=set(note['scope']['characters']): reasons.append('glyph scope changed')
        try:
            if basis['glyphs'].get(c)!=glyph_basis(font,c): reasons.append('glyph outline or advance changed')
        except ValueError: reasons.append('glyph unavailable')
    elif note['kind']!='open-question': reasons.append('basis not captured; compare manually')
    status='open-question' if note['kind']=='open-question' else 'reconsider-note' if reasons else 'current-note'
    return dict(id=note['id'],kind=note['kind'],font=font.entry['id'],character=c,status=status,
                note=note['note'],rationale=note['rationale'],evidence=note.get('evidence',[]),
                implementation=note.get('implementation','Implementation is not recorded.'),
                rule_ids=note['rule_ids'],reasons=reasons)


def assessments(data,fonts,rules,selected=()):
    result=[assess(note,f,c,rules) for note in data['notes'] for f in fonts.values()
            if f.entry['role'] in {'current','proposed'} or f.entry['id'] in selected
            for c in note['scope']['characters'] if matches(note,f,c)]
    # Conflicting notes prompt discussion; they do not veto experiments or require a transition.
    for row in result:
        if row['kind']=='open-question': continue
        peers=[n for n in result if n['id']!=row['id'] and n['kind']==row['kind'] and n['font']==row['font'] and n['character']==row['character'] and (row['kind']=='choice' or set(n['rule_ids'])&set(row['rule_ids']))]
        if peers:
            row['status']='reconsider-note'
            row['reasons'].append('overlapping current notes; compare manually')
    return result


def interpretation(notes, default='unresolved-advisory'):
    exceptions=[n for n in notes if n['kind']=='approved-exception']
    return 'approved-exception' if any(n['status']=='current-note' for n in exceptions) else 'reconsider-note' if exceptions else default


def annotate(rows, notes):
    for row in rows:
        members=set(row.get('members',{}).values())|{row['font']}
        relevant=[n for n in notes if n['font'] in members and n['character'] in row['targets'] and row['rule_id'] in n['rule_ids']]
        row['current_notes']=relevant
        # A single scoped exception never classifies an entire multi-target/family row.
        row['interpretation']='advisory-with-scoped-notes' if any(n['kind']=='approved-exception' for n in relevant) else 'unresolved-advisory' if row['status']=='advisory' else row['status']
        row['target_interpretations']={fid:{c:interpretation([n for n in relevant if n['font']==fid and n['character']==c],row['status']) for c in row['targets']} for fid in sorted(members) if fid!='family'}
