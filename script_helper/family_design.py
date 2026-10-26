#!/usr/bin/env python3
"""Advisory family-design beta. Never writes an input font or edits a rule."""
import argparse
import hashlib
import html
import io
import json
import math
import os
import re
import tempfile
import sys
from pathlib import Path

from fontTools.misc.bezierTools import solveCubic, solveQuadratic
from fontTools.pens.basePen import BasePen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
import design_notes

ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / 'src/design-rules/family-v0.1.yaml'
BETA = ROOT / 'src/design-rules/beta-inputs.json'
NOTES = ROOT / 'src/design-rules/current-notes.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError(f'Nonfinite JSON number: {value}')
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=nonfinite)


def fields(value, required, optional, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label} must be an object')
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        raise ValueError(f'{label}: missing {sorted(missing)}, unknown {sorted(extra)}')


def text_value(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a nonblank string')


def character(value, label):
    if not isinstance(value, str) or len(value) != 1 or 0xD800 <= ord(value) <= 0xDFFF:
        raise ValueError(f'{label} must be one Unicode scalar')


def characters(value, label):
    if not isinstance(value, list) or not value:
        raise ValueError(f'{label} must be a nonempty character array')
    for c in value:
        character(c, label)
    if len(set(value)) != len(value):
        raise ValueError(f'{label} has duplicate characters')


DIMENSIONS = {'weight': {'Light', 'Regular', 'Black'},
              'width': {'mono', 'proportional'},
              'role': {'current', 'previous', 'proposed', 'alternate'}, 'variant': None}


def scope(value):
    if not isinstance(value, dict) or not value or not value.keys() <= DIMENSIONS.keys():
        raise ValueError('Scope must use weight, width, role or variant dimensions')
    for dimension, values in value.items():
        if not isinstance(values, list) or not values:
            raise ValueError('Scope values must be nonempty arrays')
        for item in values:
            text_value(item, 'Scope value')
        if len(set(values)) != len(values):
            raise ValueError('Duplicate scope value')
        if DIMENSIONS[dimension] is not None and not set(values) <= DIMENSIONS[dimension]:
            raise ValueError('Unknown scope value for '+dimension)


def finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(label+' must be finite')


def validate_rules(rules):
    fields(rules, {'version', 'policy', 'rules', 'exceptions'}, {'serialization'}, 'Rules')
    if 'serialization' in rules:
        text_value(rules['serialization'], 'Serialization note')
    if rules['version'] != '0.1' or rules['policy'] != 'advisory':
        raise ValueError('Expected v0.1 advisory policy')
    if not isinstance(rules['rules'], list) or not rules['rules']:
        raise ValueError('Rules must be a nonempty array')
    ids = set()
    for r in rules['rules']:
        fields(r, {'id','title','scope','targets','method','expected','provenance','approval','examples'},
               {'tolerance','y_em','reference'}, 'Rule')
        for key in ('id','title','method','expected','provenance','approval'):
            text_value(r[key], 'Rule '+key)
        if not re.fullmatch(r'[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+', r['id']) or r['id'] in ids:
            raise ValueError('Invalid or duplicate rule ID')
        ids.add(r['id'])
        method = r['method']
        if method not in {'advance','stem','angle','weight-order','visual'}:
            raise ValueError('Unsupported measurement method')
        if r['approval'] not in {'approved-policy','candidate','approved-specific-forms','open'}:
            raise ValueError('Unknown approval state')
        scope(r['scope'])
        characters(r['targets'], 'Rule targets')
        characters(r['examples'], 'Rule examples')
        if not set(r['examples']) <= set(r['targets']):
            raise ValueError('Examples must be declared targets')
        allowed = set()
        if method != 'visual':
            finite(r.get('tolerance'), 'Tolerance')
            if r['tolerance'] < 0:
                raise ValueError('Tolerance must be nonnegative')
            allowed.add('tolerance')
        if method in {'stem','weight-order'}:
            finite(r.get('y_em'), 'Stem y_em')
            allowed.add('y_em')
        if method == 'advance':
            character(r.get('reference'), 'Advance reference')
            allowed.add('reference')
        if method in {'stem','angle'} and len(r['targets']) < 2:
            raise ValueError('Comparison requires at least two targets')
        if method == 'weight-order' and len(r['targets']) != 1:
            raise ValueError('Weight order requires exactly one designated stem character')
        if method == 'angle' and set(r['targets']) != {'/', chr(92)}:
            raise ValueError('Angle v0.1 supports designated slash/backslash only')
        if {'tolerance','y_em','reference'}.intersection(r) - allowed:
            raise ValueError('Unexpected method-specific rule field')
    if not isinstance(rules['exceptions'], list):
        raise ValueError('Exceptions must be an array')
    exception_ids = set()
    for e in rules['exceptions']:
        fields(e, {'id','rule','scope','reason','approval','provenance'}, set(), 'Exception')
        for key in ('id','rule','reason','approval','provenance'):
            text_value(e[key], 'Exception '+key)
        if e['id'] in exception_ids or e['id'] in ids or not re.fullmatch(r'[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+', e['id']):
            raise ValueError('Invalid or duplicate exception ID')
        exception_ids.add(e['id'])
        scope(e['scope'])
        if e['rule'] not in ids or e['approval'] not in {'approved','candidate','open','observed-limitation'}:
            raise ValueError('Invalid exception rule/approval')
    return rules


def load_rules(path=RULES):
    # JSON is a YAML 1.2 subset: one parser, no new runtime dependencies.
    return validate_rules(read_json(path))


def validate_entries(data):
    fields(data, {'fonts'}, {'provenance'}, 'Input manifest')
    if 'provenance' in data:
        text_value(data['provenance'], 'Input provenance')
    if not isinstance(data['fonts'], list) or not data['fonts']:
        raise ValueError('Fonts must be a nonempty array')
    ids = set()
    for e in data['fonts']:
        fields(e, {'id','path','sha256','weight','width','role','variant'}, set(), 'Font entry')
        for key, value in e.items():
            text_value(value, 'Font '+key)
        if e['id'] in ids or e['id'] == 'family':
            raise ValueError('Duplicate or reserved font ID')
        ids.add(e['id'])
        if not re.fullmatch('[0-9a-f]{64}', e['sha256']):
            raise ValueError('Font sha256 must be 64 lowercase hexadecimal characters')
        for dimension in ('weight','width','role'):
            if e[dimension] not in DIMENSIONS[dimension]:
                raise ValueError('Unknown font '+dimension)
    return data['fonts']


def validate_requests(requests, fonts, rules):
    fields(requests, {'title','notice','items'}, set(), 'Requests')
    text_value(requests['title'], 'Request title')
    text_value(requests['notice'], 'Request notice')
    if not isinstance(requests['items'], list):
        raise ValueError('Request items must be an array')
    ids = {r['id'] for r in rules['rules']}
    for item in requests['items']:
        fields(item, {'character','label','request','current','rule_ids'}, {'approved','proposed','previous'}, 'Worksheet item')
        character(item['character'], 'Requested character')
        for key in ('label','request','current'):
            text_value(item[key], 'Worksheet '+key)
        if not isinstance(item['rule_ids'], list) or not all(isinstance(r,str) for r in item['rule_ids']) or not set(item['rule_ids']) <= ids:
            raise ValueError('Unknown or malformed worksheet rule IDs')
        if len(item['rule_ids']) != len(set(item['rule_ids'])):
            raise ValueError('Duplicate worksheet rule ID')
        for role in ('current','proposed','previous','approved'):
            if role in item and (not isinstance(item[role],str) or item[role] not in fonts):
                raise ValueError('Unknown worksheet font for '+role)
    return requests


class SectionPen(BasePen):
    """Exact Bezier intersections with a horizontal line, nonzero winding fill."""
    def __init__(self, glyph_set, y):
        super().__init__(glyph_set)
        self.y, self.hits, self.start = y, [], None

    def _moveTo(self, p):
        self.start = p

    def segment(self, pts):
        # Convert Bezier y to descending polynomial coefficients.
        ys = [p[1] - self.y for p in pts]
        if len(pts) == 2:
            coeff = [ys[1]-ys[0], ys[0]]
            roots = [] if abs(coeff[0]) < 1e-10 else [-coeff[1]/coeff[0]]
        elif len(pts) == 3:
            coeff = [ys[0]-2*ys[1]+ys[2], 2*(ys[1]-ys[0]), ys[0]]
            roots = solveQuadratic(*coeff)
        else:
            coeff = [-ys[0]+3*ys[1]-3*ys[2]+ys[3], 3*ys[0]-6*ys[1]+3*ys[2], 3*(ys[1]-ys[0]), ys[0]]
            roots = solveCubic(*coeff)
        for t in roots:
            # Boundary vertices/tangencies make a section ambiguous: don't guess.
            if abs(t) < 1e-8 or abs(t-1) < 1e-8:
                raise ValueError('Section touches a segment endpoint; choose another y')
            if not 0 < t < 1:
                continue
            degree = len(pts)-1
            dy = sum(coeff[i]*(len(coeff)-1-i)*t**(len(coeff)-2-i) for i in range(len(coeff)-1))
            if abs(dy) < 1e-7:
                raise ValueError('Tangent section')
            x = sum(math.comb(degree,i)*(1-t)**(degree-i)*t**i*p[0] for i,p in enumerate(pts))
            self.hits.append((x, 1 if dy > 0 else -1))

    def _lineTo(self, p): self.segment([self._getCurrentPoint(), p])
    def _curveToOne(self, a,b,c): self.segment([self._getCurrentPoint(),a,b,c])
    def _qCurveToOne(self, a,b): self.segment([self._getCurrentPoint(),a,b])
    def _closePath(self):
        if self._getCurrentPoint() != self.start:
            self._lineTo(self.start)
    def _endPath(self): raise ValueError('Open contour')

    def intervals(self):
        winding, start, spans = 0, None, []
        hits = sorted(self.hits)
        # coincident crossings cannot safely identify a designated stem
        if any(abs(a[0]-b[0]) < 1e-7 for a,b in zip(hits,hits[1:])):
            raise ValueError('Coincident crossings')
        for x,d in hits:
            old = winding
            winding += d
            if not old and winding: start = x
            if old and not winding: spans.append([start,x])
        if winding: raise ValueError('Unclosed cross-section')
        return spans


class Font:
    def __init__(self, entry, base, blob=None):
        self.entry = dict(entry)
        self.path = (base / entry['path']).resolve()
        self.blob = self.path.read_bytes() if blob is None else blob
        self.digest = hashlib.sha256(self.blob).hexdigest()
        if self.digest != entry['sha256']:
            raise ValueError(f"Hash mismatch: {entry['id']}")
        # Every measurement and illustration uses this single verified byte snapshot.
        try:
            self.font = TTFont(io.BytesIO(self.blob))
            self.gs = self.font.getGlyphSet()
            self.cmap = self.font.getBestCmap() or {}
            self.upm = self.font['head'].unitsPerEm
            if not 16 <= self.upm <= 16384:
                raise ValueError('Invalid unitsPerEm')
        except Exception as error:
            raise ValueError(f"Unsupported/corrupt font {entry['id']}: {type(error).__name__}") from error

    def name(self, c):
        if ord(c) not in self.cmap: raise ValueError(f'Missing U+{ord(c):04X}')
        return self.cmap[ord(c)]

    def advance(self, c): return self.font['hmtx'][self.name(c)][0]/self.upm

    def stem(self, c, y):
        pen = SectionPen(self.gs, y*self.upm)
        self.gs[self.name(c)].draw(pen)
        spans = pen.intervals()
        if len(spans) != 2:
            raise ValueError(f'Expected two distinct stem intervals; found {len(spans)}')
        return (spans[0][1]-spans[0][0])/self.upm

    def angle(self, c):
        pen = DecomposingRecordingPen(self.gs)
        self.gs[self.name(c)].draw(pen)
        candidates, current = [], None
        for op, pts in pen.value:
            if op == 'moveTo': current = pts[0]
            elif op in {'lineTo', 'curveTo', 'qCurveTo'}:
                end = pts[-1]
                if end is None: raise ValueError('Implicit quadratic contour unsupported for angle')
                dx,dy = end[0]-current[0], end[1]-current[1]
                length = math.hypot(dx,dy)
                if abs(dy) >= .5*self.upm and abs(dx) >= .15*self.upm and length:
                    deviation = max([abs(dx*(p[1]-current[1])-dy*(p[0]-current[0]))/length for p in pts]+[0])
                    if deviation <= .25:  # font units; curved edges are not angles
                        candidates.append((length, math.degrees(math.atan2(abs(dy),abs(dx)))))
                current = end
        if not candidates: raise ValueError('No supported long straight slash edge')
        return max(candidates)[1]

    def bounds(self, c):
        pen = BoundsPen(self.gs)
        self.gs[self.name(c)].draw(pen)
        return tuple(v/self.upm for v in pen.bounds) if pen.bounds else (0,0,0,0)

    def svg(self, c, section=None, frame=None):
        name = self.name(c)
        pen = SVGPathPen(self.gs)
        self.gs[name].draw(pen)
        advance = self.advance(c)
        xmin,ymin,xmax,ymax = frame or shared_frame([self],[c],section)
        line = '' if section is None else f'<path d="M {xmin} {-section} H {xmax}" stroke="#d85d37" stroke-width="0.004"/>'
        return f'<svg viewBox="{xmin} {-ymax} {xmax-xmin} {ymax-ymin}" role="img" aria-label="U+{ord(c):04X} actual font outline"><path d="{pen.getCommands()}" transform="scale({1/self.upm},{-1/self.upm})" fill="#172d3b" fill-rule="nonzero"/>{line}<path d="M 0 {-ymax} V {-ymin} M {advance} {-ymax} V {-ymin}" stroke="#a8bbc4" stroke-width="0.002" stroke-dasharray="0.012 0.012"/></svg>'


def shared_frame(fonts, chars, section=None):
    # Em coordinates give all comparison roles the same scale, even across UPMs.
    xmin,ymin,xmax,ymax = 0, -.15, .6, .8
    for font in fonts:
        for c in chars:
            if ord(c) not in font.cmap:
                continue
            x0,y0,x1,y1 = font.bounds(c)
            xmin,ymin = min(xmin,x0),min(ymin,y0)
            xmax,ymax = max(xmax,x1,font.advance(c)),max(ymax,y1)
    if section is not None:
        ymin,ymax = min(ymin,section),max(ymax,section)
    return xmin-.1,ymin-.1,xmax+.1,ymax+.1


def applies(rule, entry):
    return all(entry.get(k) in values for k,values in rule['scope'].items())


def finding(rule, font_id, status, observed, reason, expected=None):
    return dict(rule_id=rule['id'], font=font_id, status=status,
                approval=rule['approval'], targets=rule['targets'], expected=expected or rule['expected'],
                observed=observed, reason=reason,
                decision='Open - review with Greg; retain requested proposal. No waiver or rule edit applied.')


def measure_targets(font, targets, method, y=None):
    values, missing = {}, {}
    for c in targets:
        try:
            values[c] = font.advance(c) if method == 'advance' else font.stem(c,y) if method == 'stem' else font.angle(c)
        except ValueError as error:
            missing[c] = str(error)
    return values, missing


def weight_rows(rule, eligible, proposed_ids=()):
    rows = []
    groups = sorted({(f.entry['width'],f.entry['variant']) for f in eligible if f.entry['role'] in {'current','proposed'} or f.entry['id'] in proposed_ids})
    target = rule['targets'][0]
    for width,variant in groups:
        group = [f for f in eligible if (f.entry['width'],f.entry['variant']) == (width,variant)]
        current = {w:[f for f in group if f.entry['role']=='current' and f.entry['weight']==w] for w in ('Light','Regular','Black')}
        contexts = [('family',None)] + [(f.entry['id'],f) for f in group if f.entry['role']=='proposed' or f.entry['id'] in proposed_ids]
        for identity,proposed in contexts:
            values,missing,members = {},{},{}
            for weight,choices in current.items():
                selected = [proposed] if proposed and proposed.entry['weight']==weight else choices
                if len(selected) != 1:
                    missing[weight] = 'Need exactly one current default reference (or the explicit proposed replacement)'
                    continue
                f = selected[0]
                members[weight] = f.entry['id']
                try: values[weight] = f.stem(target,rule['y_em'])
                except ValueError as error: missing[weight] = str(error)
            order = ('Light','Regular','Black')
            breaches = any(values[left] + (j-i)*rule['tolerance'] >= values[right]
                           for i,left in enumerate(order) for j,right in enumerate(order)
                           if i < j and left in values and right in values)
            status = 'advisory' if breaches else 'unmeasured' if missing else 'pass'
            reason = f'{target} left stem at y={rule["y_em"]} em; '+('proposed replacement against current references' if proposed else 'current family references')+'; not perceived weight.'
            if missing: reason += ' Incomplete references/geometry: '+str(missing)
            row = finding(rule,identity,status,values,reason)
            row.update(context={'width':width,'variant':variant}, members=members, unmeasured_targets=missing)
            row['exceptions'] = [e for e in rule.get('_exceptions',[]) if any(f.entry['id'] in members.values() and applies(e,f.entry) for f in group)]
            rows.append(row)
    if not groups:
        rows.append(finding(rule,'family','unmeasured',{},'No current or proposed font matches this relationship scope.'))
    return rows


def evaluate(rules, fonts, proposed_ids=()):
    result = []
    for r in rules['rules']:
        eligible = [f for f in fonts.values() if applies(r,f.entry)]
        if r['method'] == 'weight-order':
            result.extend(weight_rows(dict(r,_exceptions=[e for e in rules['exceptions'] if e['rule']==r['id']]),eligible,proposed_ids))
            continue
        for f in eligible:
            method = r['method']
            if method == 'visual':
                row = finding(r,f.entry['id'],'visual-review',None,'Human optical/form judgment required; no numeric inference.')
            else:
                values,missing = measure_targets(f,r['targets'],method,r.get('y_em'))
                expected = None
                if method == 'advance':
                    try: reference = f.advance(r['reference'])
                    except ValueError as error:
                        reference = None
                        missing['reference '+r['reference']] = str(error)
                    breaches = reference is not None and any(abs(v-reference)>r['tolerance'] for v in values.values())
                    reason = 'Sampled spacing glyph advances in em; reference '+r['reference']
                    if reference is not None:
                        expected = f"Equal to {r['reference']} advance ({reference:.6f} em), tolerance {r['tolerance']} em"
                else:
                    breaches = len(values)>=2 and max(values.values())-min(values.values())>r['tolerance']
                    reason = f"Leftmost of two filled intervals at y={r['y_em']} em. Proposed tolerance {r['tolerance']} em." if method=='stem' else 'Longest supported straight edge per designated slash; acute angle to baseline, degrees.'
                if missing: reason += ' Unmeasured targets: '+str(missing)
                status = 'advisory' if breaches else 'unmeasured' if missing else 'pass'
                row = finding(r,f.entry['id'],status,values,reason,expected)
                row['unmeasured_targets'] = missing
            row['exceptions'] = [e for e in rules['exceptions'] if e['rule']==r['id'] and applies(e,f.entry)]
            result.append(row)
    return result


STYLE = '''body{margin:0;background:#edf1f2;color:#172d3b;font:16px/1.55 -apple-system,BlinkMacSystemFont,Arial,sans-serif}main{max-width:1100px;margin:auto;padding:52px 38px}h1{font-size:44px;line-height:1.1;max-width:900px}h2{font-size:25px}h3{margin:0 0 12px}p{max-width:85ch}.eyebrow{letter-spacing:.16em;font-size:12px;font-weight:700;text-transform:uppercase;color:#45636e}.card,.sheet{background:white;border-top:5px solid #527a80;margin:28px 0;padding:30px}.advisory{border-color:#cc633f}.badge{display:inline-block;background:#e8eef0;padding:3px 9px;font-size:12px;margin:3px}.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}.specimen{border:1px solid #dce4e7;padding:16px}.specimen svg{display:block;width:100%;height:240px}.muted{color:#546b76;font-size:13px}.issue{border-left:4px solid #cc633f;padding:10px 18px;margin:20px 0;background:#fff6ef}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;border-bottom:1px solid #dce4e7;padding:10px;vertical-align:top}.notes{height:160px;background:repeating-linear-gradient(white,white 31px,#dce4e7 32px)}@media print{body{background:white}main{padding:0}.sheet{break-before:page;break-inside:avoid}.card{break-inside:avoid}h1{font-size:32px}.specimen svg{height:190px}.notes{height:100px}}'''


def page(title,body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+html.escape(title)+'</title><style>'+STYLE+'</style><main>'+body+'</main></html>\n'


def esc(v): return html.escape(str(v))


def observed_text(value):
    if isinstance(value,dict):
        return ' · '.join(f'{k}: {v:.6f}' if isinstance(v,(int,float)) else f'{k}: {v}' for k,v in value.items())
    return 'Not numerically measured' if value is None else str(value)


def panel(font,c,label,section=None,frame=None):
    if font is None:
        return f'<div class="specimen"><h3>{esc(label)}</h3><p class="muted">No approved or proposed drawing supplied. Do not infer approval.</p></div>'
    try:
        drawing=font.svg(c,section,frame)
        advance=f'{font.advance(c):.6f} em'
    except ValueError as e:
        drawing='<p>Unsupported: '+esc(e)+'</p>'
        advance='unmeasured (missing glyph)'
    return f'<div class="specimen"><h3>{esc(label)}</h3>{drawing}<p class="muted">{esc(font.entry["id"])} · {esc(font.entry["weight"])} / {esc(font.entry["width"])}<br>Advance: {advance} · SHA {font.digest[:16]}</p></div>'


def guide(rules,fonts,rows,note_rows=()):
    body='<p class="eyebrow">Monofuki / family design / v0.1 beta</p><h1>A small, visible set of family decisions.</h1><p>All design findings are advisory. Proposed geometry stays available even when a rule disagrees. Candidate tolerances are experiments, not approvals. Existing build integrity checks still apply.</p>'
    body+='<p>Specimens below are actual outlines extracted from the hash-verified fonts. Dashed lines mark advances; orange lines mark the defined stem section. Ink area is not a measure of perceived weight.</p>'
    for r in rules['rules']:
        body+=f'<section class="card"><p class="eyebrow">{esc(r["id"])} / {esc(r["approval"])}</p><h2>{esc(r["title"])}</h2><p>{esc(r["expected"])}</p><p class="muted">Scope: {esc(r["scope"])}. Method: {esc(r["method"])}. Tolerance: {esc(r.get("tolerance","visual only"))}.</p><p>{esc(r["provenance"])}</p>'
        body+='<div class="pair">'
        eligible = [f for f in fonts.values() if applies(r,f.entry)]
        chosen = [f for f in eligible if f.entry.get('role') == 'current'] or eligible[:3]
        chosen = sorted(chosen,key=lambda f: ('Light','Regular','Black').index(f.entry['weight']))
        examples = r['examples'][:2] if r['method'] in {'stem','angle'} else r['examples'][:1]
        frame = shared_frame(chosen[:3],examples,r.get('y_em'))
        for f in chosen[:3]:
            for c in examples:
                body+=panel(f,c,f.entry['id']+f' / U+{ord(c):04X}',r.get('y_em'),frame)
        if not chosen:
            body+='<p>No supplied font matches this scope; geometry unmeasured.</p>'
        body+='</div><table><tr><th>Font</th><th>Result</th><th>Observed / reason</th></tr>'
        for row in rows:
            if row['rule_id']==r['id']:
                body+=f'<tr><td>{esc(row["font"])}</td><td>{esc(row["status"])}</td><td>{esc(observed_text(row["observed"]))}<br>{esc(row["reason"])}</td></tr>'
        body+='</table></section>'
    body+='<section class="card"><h2>Current design notes</h2><p>Repository src/design-rules/current-notes.json holds editable current intent. Font source implements it; worksheets and markup are evidence, not the approval authority. Notes never veto an experiment.</p>'
    for n in note_rows:
        if fonts[n['font']].entry['role']=='current':
            body+='<p><strong>'+esc(n['id']+' / '+n['kind']+' / '+n['status'])+'</strong><br>'+esc(n['note'])+'<br>Implementation note: '+esc(n['implementation'])+'<br>'+esc('; '.join(n['reasons']))+'</p>'
    body+='</section>'
    body+='<section class="card"><h2>Exceptions and coverage notes</h2><pre>'+esc(json.dumps(rules['exceptions'],indent=2))+'</pre><p>Exceptions remain visible and never suppress findings. No pending exception is an approved waiver.</p><h2>Unmeasured</h2><p>Optical weight, counters, joins, terminals, curve quality, spacing in shaped strings, italic geometry, full Unicode/Nerd coverage, and proportional variants need separate review. These probes do not establish whole-font compliance.</p></section>'
    return page('Monofuki family design v0.1',body)


def worksheets(requests,fonts,rows,note_rows=()):
    body='<p class="eyebrow">Monofuki / design iteration</p><h1>'+esc(requests['title'])+'</h1><p>'+esc(requests['notice'])+'</p><p>All rule issues are advisory. Keep the proposal visible; Greg decides whether to revise the drawing, retain an exception, or approve a rule change. No decision is applied here.</p>'
    if not requests['items']:
        body+='<p>No worksheet items supplied.</p>'
    for item in requests['items']:
        c=item['character']
        frame=shared_frame([fonts[item[role]] for role in ('approved','current','proposed','previous') if item.get(role)],[c])
        body+=f'<section class="sheet"><p class="eyebrow">U+{ord(c):04X} / {esc(item["label"])}</p><h2>{esc(item["request"])}</h2><div class="pair">'
        recorded=lambda fid: any(n['kind']=='choice' and n['font']==fid and n['character']==c for n in note_rows)
        reconsider=lambda fid: any(n['kind']=='choice' and n['status']=='reconsider-note' and n['font']==fid and n['character']==c for n in note_rows)
        for role in ('approved','current','proposed','previous'):
            fid=item.get(role)
            if role == 'approved' and fid and fid == item.get('current'):
                continue
            label = ('RECORDED CHOICE / CURRENT' if recorded(fid) else 'CURRENT / REFERENCE (choice not recorded)') if role == 'current' and fid == item.get('approved') else ('RECORDED CHOICE REFERENCE' if recorded(fid) else 'REFERENCE (choice not recorded)') if role == 'approved' else role.upper()
            if recorded(fid) and reconsider(fid): label+=' / RECONSIDER NOTE'
            if role == 'proposed' and not fid and item.get('approved'):
                continue
            body+=panel(fonts.get(fid),c,label+(' - '+fid if fid else ' - not supplied'),frame=frame)
        body+='</div>'
        for n in note_rows:
            if n['character']==c and n['font'] in {item.get('current'),item.get('proposed'),item.get('approved')}:
                label='APPROVED EXCEPTION' if n['kind']=='approved-exception' else 'CURRENT CHOICE' if n['kind']=='choice' else 'OPEN QUESTION'
                body+='<div class="issue"><strong>'+esc(n['id']+' / '+n['font']+' / '+label+' / '+n['status'])+'</strong><p>Current note: '+esc(n['note'])+'<br>Rationale: '+esc(n['rationale'])+'<br>Implementation (separate from intent): '+esc(n['implementation'])+'<br>Evidence: '+esc('; '.join(n['evidence']))+'<br>Reconsider: '+esc('; '.join(n['reasons']) or 'No basis change detected.')+'</p></div>'
        relevant=[r for r in rows if (r['rule_id'] in item['rule_ids'] or (c in r['targets'] and r['status'] != 'pass')) and worksheet_row_applies(r,item,fonts)]
        for row in relevant:
            scoped=[n for n in row['current_notes'] if n['character']==c and n['font'] in {item.get('current'),item.get('proposed')} and (row['font']=='family' or n['font']==row['font'])]
            interpretation=design_notes.interpretation(scoped,'unresolved-advisory' if row['status']=='advisory' else row['status'])
            if interpretation in {'approved-exception','reconsider-note'}: interpretation+=f' (U+{ord(c):04X} only; finding retained)'
            body+='<div class="issue"><strong>'+esc(row['rule_id']+' / '+row['font']+' / '+row['status']+' / '+interpretation)+'</strong><p>Expected: '+esc(row['expected'])+'<br>Observed/proposed: '+esc(observed_text(row['observed']))+'<br>Reason: '+esc(row['reason'])+'<br>Decision: '+esc(row['decision'])+'</p></div>'
        if not relevant: body+='<div class="issue">No evaluated rule result for this item. Coverage remains open.</div>'
        body+='<p><strong>Review / drawing notes</strong></p><div class="notes"></div></section>'
    return page(requests['title'],body)


def worksheet_row_applies(row, item, fonts):
    selected = [fonts[item[role]] for role in ('current','proposed') if item.get(role)]
    if row['font'] in {f.entry['id'] for f in selected}:
        return True
    if row['font'] == 'family':
        context = row.get('context')
        return context is not None and any(all(f.entry[k]==v for k,v in context.items()) for f in selected)
    return False


def load_inputs(path):
    entries = validate_entries(read_json(path))
    return {e['id']:Font(e,Path(path).resolve().parent) for e in entries}


def guard_outputs(out, names, protected):
    protected = [Path(p).resolve() for p in protected]
    for name in names:
        target = out/name
        if target.is_symlink():
            raise ValueError('Refusing symlink output: '+str(target))
        for source in protected:
            if target.resolve() == source or (target.exists() and source.exists() and target.samefile(source)):
                raise ValueError('Output aliases an input: '+str(target))


def write_outputs(out, outputs, protected):
    guard_outputs(out,outputs,protected)
    out.mkdir(parents=True,exist_ok=True)
    # Prepare the entire set first. Atomic replacement never follows an output link.
    # The receipt is last, so --verify detects an interrupted multi-file replacement.
    with tempfile.TemporaryDirectory(prefix='.family-design-',dir=out) as tmp:
        for name,content in outputs.items():
            path=Path(tmp)/name
            path.write_bytes(content if isinstance(content,bytes) else content.encode())
        guard_outputs(out,outputs,protected)
        for name in outputs:
            os.replace(Path(tmp)/name,out/name)


def render_outputs(rules,fonts,requests=None,notes=None):
    validate_rules(rules)
    notes=design_notes.validate(read_json(NOTES) if notes is None else notes,rules)
    if requests is not None:
        validate_requests(requests,fonts,rules)
    proposed_ids={item['proposed'] for item in requests['items'] if item.get('proposed')} if requests is not None else set()
    rows=evaluate(rules,fonts,proposed_ids)
    selected={item[role] for item in requests['items'] for role in ('current','proposed','approved') if item.get(role)} if requests is not None else set()
    note_rows=design_notes.assessments(notes,fonts,rules,selected)
    design_notes.annotate(rows,note_rows)
    report={'version':'0.1','policy':'advisory','input_hashes':{k:f.digest for k,f in fonts.items()},'rules_sha256':digest(rules),'generator_sha256':digest({p.name:sha(p) for p in (Path(__file__),Path(design_notes.__file__))}),'notes_sha256':digest(notes),'current_notes':note_rows,'input_metadata':{k:{field:value for field,value in f.entry.items() if field!='path'} for k,f in fonts.items()},'requests_sha256':digest(requests) if requests is not None else None,'findings':rows}
    outputs={'report.json':json.dumps(report,indent=2,ensure_ascii=False)+'\n','guide.html':guide(rules,fonts,rows,note_rows)}
    md=['# Monofuki family design v0.1','', 'Current intent is recorded in [current design notes](../../../src/design-rules/current-notes.json); worksheets are generated evidence, never sole authority. Notes are editable and advisory.','', 'Generated from `src/design-rules/family-v0.1.yaml`. All findings are advisory.', '', '[Illustrated guide](guide.html) · [Evidence report](report.json)', '']
    for r in rules['rules']:
        md += ['## '+r['id']+' — '+r['title'],'',r['expected'],'',f"Approval: {r['approval']}. Scope: `{r['scope']}`. Method: {r['method']}. Tolerance: {r.get('tolerance', 'visual only')}.",'',r['provenance'],'']
    md+=['## Exceptions','', '```json', json.dumps(rules['exceptions'],indent=2), '```','', 'Numeric passes cover only the designated samples and sections. Optical review, italic, shaping, full repertoire and proportional geometry are not measured.','']
    outputs['guide.md']='\n'.join(md)
    if requests is not None:
        outputs['worksheet.html']=worksheets(requests,fonts,rows,note_rows)
        report['worksheet_coverage']=[dict(character=item['character'],role=role,font=item[role],status='supported' if ord(item['character']) in fonts[item[role]].cmap else 'unmeasured-missing-glyph') for item in requests['items'] for role in ('approved','current','proposed','previous') if item.get(role)]
        outputs['report.json']=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    else:
        outputs['worksheet.html']=page('No worksheet requests supplied','<h1>No worksheet requests supplied</h1><p>This run contains no proposed drawings. Earlier worksheets are not part of this run.</p>')
        report['worksheet_coverage']=[]
    report['scope_coverage']=[dict(rule_id=r['id'],matched_fonts=[f.entry['id'] for f in fonts.values() if applies(r,f.entry)]) for r in rules['rules']]
    report['source_digest']=digest({key:report[key] for key in ('rules_sha256','generator_sha256','input_metadata','requests_sha256','notes_sha256')})
    outputs['report.json']=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    outputs['output-manifest.json']=json.dumps({'version':1,'source_digest':report['source_digest'],'files':{name:hashlib.sha256(content.encode()).hexdigest() for name,content in outputs.items()}},indent=2)+'\n'
    return outputs,report


def generate(rules,fonts,out,requests=None,protected=(),notes=None):
    outputs,report=render_outputs(rules,fonts,requests,notes)
    write_outputs(out,outputs,[RULES,NOTES,*protected,*(f.path for f in fonts.values())])
    return outputs,report


def beta(history_root,out,rules,protected=(),notes=None):
    config=read_json(BETA)
    fields(config,{'fonts','requests'},{'provenance'},'Beta config')
    validate_entries({'fonts':config['fonts']})
    entries=[dict(e,path=str(history_root/e['path'])) for e in config['fonts']]
    fonts={e['id']:Font(e,Path('/')) for e in entries}
    original_inputs=[f.path for f in fonts.values()]
    demo=out/'synthetic-H-advance.otf'
    source=fonts['Black03']
    f=TTFont(io.BytesIO(source.blob))
    name=f.getBestCmap()[ord('H')]
    width,lsb=f['hmtx'][name]
    f['hmtx'][name]=(width+40,lsb)
    f.recalcTimestamp=False
    buffer=io.BytesIO()
    f.save(buffer)
    blob=buffer.getvalue()
    entry=dict(id='EXAMPLE-Black03-H-plus40',path=str(demo.resolve()),sha256=hashlib.sha256(blob).hexdigest(),weight='Black',width='mono',role='proposed',variant='default')
    if entry['id'] in fonts:
        raise ValueError('Beta input uses reserved synthetic example ID')
    entries.append(entry)
    fonts[entry['id']]=Font(entry,Path('/'),blob)
    request=config['requests']
    outputs,report=render_outputs(rules,fonts,request,notes)
    extras={'synthetic-H-advance.otf':blob,'inputs.json':json.dumps({'fonts':entries},indent=2)+'\n','requests.json':json.dumps(request,indent=2)+'\n'}
    write_outputs(out,dict(extras,**outputs),[RULES,BETA,NOTES,*protected,*original_inputs])
    return outputs,report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rules',type=Path,default=RULES)
    p.add_argument('--notes',type=Path,default=NOTES)
    sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('beta',help='Verify pinned Light04/Black03 references and generate labelled example')
    b.add_argument('--history-root',type=Path,required=True)
    b.add_argument('--out',type=Path,default=ROOT/'.font-build/family-design')
    g=sub.add_parser('generate',help='Check fonts; generate guide/report and a worksheet or explicit empty sheet')
    g.add_argument('--inputs',type=Path,required=True)
    g.add_argument('--requests',type=Path)
    g.add_argument('--out',type=Path,required=True)
    g.add_argument('--verify',action='store_true',help='Compare generated text against existing output without writing')
    n=sub.add_parser('note-basis',help='Print an optional narrow comparison basis; never writes or approves notes')
    n.add_argument('--inputs',type=Path,required=True)
    n.add_argument('--font',required=True)
    n.add_argument('--character',action='append',required=True)
    n.add_argument('--rule-id',action='append',default=[])
    args=p.parse_args(argv)
    try:
        rules=load_rules(args.rules)
        notes=design_notes.validate(read_json(args.notes),rules)
        if args.command=='note-basis':
            fonts=load_inputs(args.inputs);font=fonts[args.font]
            characters(args.character,'Note characters')
            if not set(args.rule_id)<={r['id'] for r in rules['rules']}: raise ValueError('Unknown basis rule')
            scope={k:font.entry[k] for k in ('weight','width','variant')};scope['characters']=args.character
            print(json.dumps(design_notes.capture_basis(scope,args.rule_id,font,rules),indent=2,ensure_ascii=False))
            return 0
        if args.command=='beta': outputs,report=beta(args.history_root.resolve(),args.out,rules,[args.rules,args.notes],notes)
        else:
            fonts=load_inputs(args.inputs)
            requests=read_json(args.requests) if args.requests else None
            protected=[args.rules,args.notes,args.inputs,*([args.requests] if args.requests else [])]
            if args.verify:
                outputs,report=render_outputs(rules,fonts,requests,notes)
                stale=[name for name,content in outputs.items() if not (args.out/name).exists() or (args.out/name).read_text()!=content]
                if stale: raise ValueError('Stale generated files: '+', '.join(stale))
            else: outputs,report=generate(rules,fonts,args.out,requests,protected,notes)
        counts={s:sum(r['status']==s for r in report['findings']) for s in ('pass','advisory','unmeasured','visual-review')}
        print(json.dumps({'policy':'advisory','counts':counts,'out':str(args.out)},sort_keys=True))
        return 0  # All design issues, including unmeasured/visual, stay advisory.
    except (ValueError,KeyError,OSError,json.JSONDecodeError) as e:
        print('Input/generation error: '+str(e),file=sys.stderr)
        return 2  # Invalid inputs/tool errors are not design-rule violations.


if __name__=='__main__': sys.exit(main())
