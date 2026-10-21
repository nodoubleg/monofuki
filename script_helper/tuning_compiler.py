"""Shared native/browser font compiler. No server or installed fonts required.

Outlines arrive from the same JS transform used by the editor. Untouched cmap,
glyphs, marks and component notices come from the complete pinned base build.
Contextual positioning uses xPlacement only: it never changes an advance.
"""
import copy
import hashlib
import io
import json
import math
import re
import struct
from collections import defaultdict, Counter
from threading import RLock

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from fontTools.otlLib.builder import buildCoverage, buildLookup, buildSinglePosSubtable
from fontTools.ttLib.tables.otBase import ValueRecord
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.svgLib.path import parse_path

COMPILER_VERSION = 1
STYLES = ('Regular', 'Bold', 'Italic', 'BoldItalic')
SYMBOLS = '=+*/%<>!&|^~?:.-'


def config_identity(settings):
    keys = ('adjustments', 'accentAdjustments', 'glyphAlternatives', 'yJunctionRaise',
            'tailTruncation', 'gDescenderCompression', 'sevenCrossbar', 'cell', 'upm')
    value = {k: settings[k] for k in keys}
    value['experiments'] = {k: settings['experiments'][k] for k in (
        'accentEnabled', 'accentLowering', 'gAlternative', 'smartEnabled',
        'smartStrength', 'symbolEnabled', 'symbolStrength')}
    value['compiler'] = COMPILER_VERSION
    raw = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest(), value


def replay(outline, pen):
    for op, points in outline['p']:
        getattr(pen, op)(*(tuple(p) for p in points))
    if outline.get('svgCrossbar'):
        # Match the body winding so overlapping ink adds instead of cutting out.
        area = AreaPen(None)
        for op, points in outline['p']:
            getattr(area, op)(*(tuple(p) for p in points))
        bar = AreaPen(None)
        parse_path(outline['svgCrossbar'], bar)
        parse_path(outline['svgCrossbar'], ReverseContourPen(pen) if area.value * bar.value < 0 else pen)


def clamp_shift(value, b):
    return max(min(0, 14-b[0]), min(max(0, 561-b[2]), value)) if b else 0


def ink_bounds(outline):
    # Convex hull bounds enclose the actual transformed Beziers and 7 crossbar.
    xs = [point[0] for _, points in outline['p'] for point in points]
    if outline.get('svgCrossbar'):
        xs += [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', outline['svgCrossbar'])[::2]]
    return (min(xs), max(xs)) if xs else None


def safety_envelope(outlines):
    pairs = [(g['sourceBounds'], ink_bounds(g)) for c, g in outlines.items() if g['sourceBounds'] and (c.isalnum() or c in SYMBOLS)]
    # All possible old-range shifts, using the selected transformed ink hull.
    left = min(ink[0]+clamp_shift(-45, b) for b, ink in pairs)
    right = max(ink[1]+clamp_shift(45, b) for b, ink in pairs)
    return max(14, right-575+14), min(561, 575+left-14)


def stronger_shift(raw, strength, b, envelope, ink=None):
    result = clamp_shift(raw*strength/100, b)
    if strength <= 100:
        return result
    old = clamp_shift(raw, b)
    ink = ink or (b[0], b[2])
    # Preserve the legacy range, but do not move further into its overhangs.
    low = min(old, envelope[0]-ink[0])
    high = max(old, envelope[1]-ink[1])
    return max(low, min(high, result))


def smart_shift(a, b, c, strength, envelope, ink=None):
    raw = max(-45, min(45, (a[2]+c[0]-b[0]-b[2])/4))
    return math.floor(stronger_shift(raw, strength, b, envelope, ink)+0.5)


def _u16(*values):
    return struct.pack('>'+'H'*len(values), *values)


def _coverage(names, ids):
    gids = sorted(ids[n] for n in names)
    return _u16(1, len(gids), *gids)


def _classes(classes, ids):
    values = sorted((ids[n], k) for k, names in classes.items() for n in names)
    ranges = []
    for gid, k in values:
        if ranges and ranges[-1][1]+1 == gid and ranges[-1][2] == k:
            ranges[-1][1] = gid
        else:
            ranges.append([gid, gid, k])
    return _u16(2, len(ranges), *(v for row in ranges for v in row))


class RawChain:
    """Keep large class rules as bytes; avoids millions of Python objects."""
    def __init__(self, data):
        self.data = data

    def compile(self, writer, font):
        writer.writeData(self.data)


def _extension_lookup(font, raw, kind):
    ext = ot.ExtensionPos()
    ext.Format, ext.ExtensionLookupType, ext.ExtSubTable = 1, kind, raw
    lookup = ot.Lookup()
    lookup.LookupType, lookup.LookupFlag, lookup.SubTable = 9, 0, [ext]
    lookup.SubTableCount = 1
    lookups = font['GPOS'].table.LookupList.Lookup
    index = len(lookups)
    lookups.append(lookup)
    return index


def _chain_dispatch(center, groups, rules, ids, axis):
    # Only the center is input. Neighbors remain context, even with partial
    # feature masks or default-ignorable glyphs between visible characters.
    if axis not in ('previous', 'following'):
        raise ValueError('Unknown context axis')
    header = 16
    cov = _coverage(center, ids)
    back = _classes(groups if axis == 'previous' else {}, ids)
    middle = _classes({1: center}, ids)
    ahead = _classes(groups if axis == 'following' else {}, ids)
    records = [_u16(*((1, a, 1, 0, 1, 0, lookup) if axis == 'previous'
                      else (0, 1, 1, a, 1, 0, lookup))) for a, lookup in rules]
    class_set = _u16(len(records), *(2+2*len(records)+14*i for i in range(len(records)))) + b''.join(records)
    offsets = [header]
    for part in (cov, back, middle, ahead):
        offsets.append(offsets[-1]+len(part))
    data = _u16(2, *offsets[:4], 2, 0, offsets[4])+cov+back+middle+ahead+class_set
    if len(data) >= 65536:
        raise ValueError('Context subtable exceeds 16-bit offsets')
    return RawChain(data)


def _indexed_single_pos(values, ids):
    values = sorted((ids[name], name, shift) for name, shift in values.items() if shift)
    raw_values = struct.pack('>'+'h'*len(values), *(v[2] for v in values))
    cov = _coverage([v[1] for v in values], ids)
    data = _u16(2, 8+len(raw_values), 1, len(values))+raw_values+cov
    if len(data) >= 65536:
        raise ValueError('Position subtable exceeds 16-bit offsets')
    return RawChain(data)


def _chain_coverage(before, inputs, after, records, ids):
    sub = ot.ChainContextPos()
    sub.Format = 3
    sub.BacktrackCoverage = [buildCoverage(n, ids) for n in reversed(before)]
    sub.BacktrackGlyphCount = len(before)
    sub.InputCoverage = [buildCoverage(n, ids) for n in inputs]
    sub.InputGlyphCount = len(inputs)
    sub.LookAheadCoverage = [buildCoverage(n, ids) for n in after]
    sub.LookAheadGlyphCount = len(after)
    sub.PosLookupRecord = []
    for sequence, lookup in records:
        record = ot.PosLookupRecord()
        record.SequenceIndex, record.LookupListIndex = sequence, lookup
        sub.PosLookupRecord.append(record)
    sub.PosCount = len(records)
    return sub


def add_spacing(font, outlines, experiments):
    cmap, ids = font.getBestCmap(), font.getReverseGlyphMap()
    # Existing GPOS mark positioning is retained, including all language systems.
    table = font['GPOS'].table
    lookups = table.LookupList.Lookup
    alnum = {c: g['sourceBounds'] for c, g in outlines.items() if c.isalnum() and g['sourceBounds'] and ord(c) in cmap}
    all_names = [cmap[ord(c)] for c in alnum] + [cmap[ord(c)] for c in SYMBOLS]
    envelope = safety_envelope(outlines)
    offsets = {}

    def shift_lookup(shift):
        if shift not in offsets:
            offsets[shift] = len(lookups)
            value = ValueRecord()
            value.XPlacement = shift
            lookups.append(buildLookup([buildSinglePosSubtable({n: value for n in all_names}, ids)]))
        return offsets[shift]

    features = []
    context_count = 0
    dispatch_metadata = {}
    if experiments['smartEnabled'] and experiments['smartStrength']:
        left_groups, right_groups, centers = defaultdict(list), defaultdict(list), defaultdict(list)
        for c, b in alnum.items():
            n = cmap[ord(c)]
            left_groups[b[2]].append(n)
            right_groups[b[0]].append(n)
            ink = ink_bounds(outlines[c]) if experiments['smartStrength'] > 100 else (0, 0)
            centers[(b[0], b[2], *ink)].append(n)
        previous_values, following_values = sorted(left_groups), sorted(right_groups)
        center_names = [cmap[ord(c)] for c in alnum]
        leaf_lookup, raw_cache = {}, {}
        # The formula adds these two edges first. Equal sums therefore share
        # exact results without approximating bounds, strengths, or rounding.
        sum_counts = Counter(prev+nxt for prev in previous_values for nxt in following_values)
        for total in sorted(sum_counts):
            values = {}
            for (x0, x1, ink0, ink1), names in centers.items():
                shift = smart_shift([0, 0, total, 0], [x0, 0, x1, 0], [0, 0, 0, 0],
                                    experiments['smartStrength'], envelope, (ink0, ink1))
                values.update((name, shift) for name in names)
                if shift:
                    context_count += sum_counts[total]
            raw = _indexed_single_pos(values, ids)
            if raw.data not in raw_cache:
                raw_cache[raw.data] = _extension_lookup(font, raw, 1)
            leaf_lookup[total] = raw_cache[raw.data]
        branch_cache = {}
        branching = 9

        def dispatch(values, groups, leaves, axis):
            def branch(start, end):
                if end-start == 1:
                    return leaves[start]
                selected, rules = {}, []
                size = math.ceil((end-start)/branching)
                for i, begin in enumerate(range(start, end, size), 1):
                    stop = min(begin+size, end)
                    child = branch(begin, stop)
                    selected[i] = [name for value in values[begin:stop] for name in groups[value]]
                    rules.append((i, child))
                raw = _chain_dispatch(center_names, selected, rules, ids, axis)
                if raw.data not in branch_cache:
                    branch_cache[raw.data] = _extension_lookup(font, raw, 8)
                return branch_cache[raw.data]
            return branch(0, len(values))

        roots = []
        for prev in previous_values:
            leaves = [leaf_lookup[prev+nxt] for nxt in following_values]
            roots.append(dispatch(following_values, right_groups, leaves, 'following'))
        features.append(dispatch(previous_values, left_groups, roots, 'previous'))
        dispatch_metadata = {'singlepos_lookups': len(raw_cache), 'dispatch_lookups': len(branch_cache),
                             'distinct_sums': len(leaf_lookup), 'dispatch_branching': branching}

    if experiments['symbolEnabled'] and experiments['symbolStrength']:
        names = [cmap[ord(c)] for c in SYMBOLS]
        subs = []
        # First matching rule wins: suppress every position in runs of >=5.
        for index in range(5):
            subs.append(_chain_coverage([names]*index, [names], [names]*(4-index), [], ids))
        # Exact maximal run boundaries: a longer context wins before shorter ones.
        for size in (4, 3, 2):
            for index in range(size):
                groups = defaultdict(list)
                for c in SYMBOLS:
                    raw = ((size-1)/2-index)*28
                    shift = math.floor(stronger_shift(raw, experiments['symbolStrength'], outlines[c]['sourceBounds'], envelope, ink_bounds(outlines[c]))+0.5)
                    groups[shift].append(cmap[ord(c)])
                for shift, center in groups.items():
                    records = [(0, shift_lookup(shift))] if shift else []
                    subs.append(_chain_coverage([names]*index, [center], [names]*(size-index-1), records, ids))
        features.append(len(lookups))
        lookups.append(buildLookup(subs))
    if features:
        records = table.FeatureList.FeatureRecord
        existing = next((i for i, rec in enumerate(records) if rec.FeatureTag == 'kern'), None)
        if existing is None:
            rec = ot.FeatureRecord()
            rec.FeatureTag, rec.Feature = 'kern', ot.Feature()
            rec.Feature.FeatureParams = None
            rec.Feature.LookupListIndex = features
            rec.Feature.LookupCount = len(features)
            records.append(rec)
            # OpenType feature records are sorted and all script indices remapped.
            ordered = sorted(enumerate(records), key=lambda p: p[1].FeatureTag)
            mapping = {old: new for new, (old, _) in enumerate(ordered)}
            kern_index = mapping[len(records)-1]
            table.FeatureList.FeatureRecord = [rec for _, rec in ordered]
            for sr in table.ScriptList.ScriptRecord:
                systems = ([sr.Script.DefaultLangSys] if sr.Script.DefaultLangSys else []) + [v.LangSys for v in sr.Script.LangSysRecord]
                for system in systems:
                    system.FeatureIndex = sorted([mapping[i] for i in system.FeatureIndex] + [kern_index])
                    system.FeatureCount = len(system.FeatureIndex)
                    if system.ReqFeatureIndex != 65535:
                        system.ReqFeatureIndex = mapping[system.ReqFeatureIndex]
        else:
            records[existing].Feature.LookupListIndex += features
            records[existing].Feature.LookupCount += len(features)
        table.FeatureList.FeatureCount = len(table.FeatureList.FeatureRecord)
    table.LookupList.LookupCount = len(lookups)
    return {'feature': 'kern', 'advance_delta': 0, 'smart_characters': len(alnum), 'context_rules': context_count,
            'strength_limit': 400, 'strong_safety_envelope': envelope, 'rounding_max_units': 0.5, **dispatch_metadata}


def compile_font(base_bytes, outlines, settings, style, *, default=False):
    if style not in STYLES or settings['cell'] != {'width':575, 'height':1150, 'ascent':880, 'descent':270} or settings['upm'] != 1024:
        raise ValueError('Unsupported style or cell metrics')
    for key in ('smartStrength', 'symbolStrength'):
        if type(settings['experiments'][key]) is not int or not 0 <= settings['experiments'][key] <= 400:
            raise ValueError('Invalid spacing strength')
    font = TTFont(io.BytesIO(base_bytes), recalcTimestamp=False, recalcBBoxes=False)
    font.cfg['fontTools.ttLib.tables.otBase:USE_HARFBUZZ_REPACKER'] = False
    before_cmap = copy.deepcopy(font['cmap'].compile(font))
    cmap = font.getBestCmap()
    if not set(ord(c) for c in outlines) <= set(cmap):
        raise ValueError('Tuning character absent in base font')
    cff = font['CFF '].cff.topDictIndex[0] if 'CFF ' in font else None
    bounds = []
    for c, outline in outlines.items():
        name = cmap[ord(c)]
        if font['hmtx'][name][0] != 575:
            raise ValueError('Tuning target is not a fixed-advance glyph')
        if cff:
            pen = T2CharStringPen(575, None, roundTolerance=0)
            replay(outline, pen)
            cff.CharStrings[name] = pen.getCharString(private=cff.Private, globalSubrs=font['CFF '].cff.GlobalSubrs)
        else:
            pen = TTGlyphPen(None)
            replay(outline, Cu2QuPen(pen, 0.5, reverse_direction=True))
            glyph = pen.glyph()
            if glyph.numberOfContours > 0:
                glyph.flags[0] |= 0x40  # OVERLAP_SIMPLE, including the rounded 7 bar.
            glyph.recalcBounds(font['glyf'])
            font['glyf'][name] = glyph
        pen = BoundsPen(None)
        replay(outline, pen)
        b = pen.bounds or (0, 0, 0, 0)
        font['hmtx'][name] = (575, math.floor(b[0]+0.5) if cff else font['glyf'][name].xMin if font['glyf'][name].numberOfContours else 0)
        bounds.append(b)
    # Graphics use the changed vertical cell, including seamless boxes and dots.
    # Apply only to box/block/Braille ranges; preserve all other Unicode outlines.
    from fontTools.pens.transformPen import TransformPen
    graphics = range(0x2500, 0x25A0)
    scale = 1150/1230
    transform = (1, 0, 0, scale, 0, 880-910*scale)
    glyphset = font.getGlyphSet()
    for cp in [*graphics, *range(0x2800, 0x2900)]:
        if cp not in cmap:
            continue
        name = cmap[cp]
        rec = RecordingPen()
        glyphset[name].draw(TransformPen(rec, transform))
        if cff:
            pen = T2CharStringPen(font['hmtx'][name][0], None, roundTolerance=0)
            rec.replay(pen)
            cff.CharStrings[name] = pen.getCharString(private=cff.Private, globalSubrs=font['CFF '].cff.GlobalSubrs)
        else:
            pen = TTGlyphPen(None)
            rec.replay(pen)
            glyph = pen.glyph()
            glyph.recalcBounds(font['glyf'])
            font['glyf'][name] = glyph
    font['hhea'].ascent, font['hhea'].descent, font['hhea'].lineGap = 880, -270, 0
    os2 = font['OS/2']
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = 880, -270, 0
    os2.fsSelection |= 1 << 7
    # Win clipping bounds must include tall untouched glyphs and selected marks.
    gs = font.getGlyphSet()
    for glyph in gs.values():
        pen = BoundsPen(gs)
        glyph.draw(pen)
        if pen.bounds:
            bounds.append(pen.bounds)
    font['head'].xMin = math.floor(min(b[0] for b in bounds))
    font['head'].xMax = math.ceil(max(b[2] for b in bounds))
    font['head'].yMin = math.floor(min(b[1] for b in bounds))
    font['head'].yMax = math.ceil(max(b[3] for b in bounds))
    for c, field in [('H','sCapHeight'),('x','sxHeight')]:
        pen = BoundsPen(gs); gs[cmap[ord(c)]].draw(pen)
        setattr(os2, field, round(pen.bounds[3]))
    os2.usWinAscent = max(880, math.ceil(max(b[3] for b in bounds)))
    os2.usWinDescent = max(270, math.ceil(-min(b[1] for b in bounds)))
    spacing = add_spacing(font, outlines, settings['experiments'])
    digest, config = config_identity(settings)
    family = font['name'].getDebugName(1)
    old_ps = font['name'].getDebugName(6)
    if not default:
        family += ' '+digest[:8]
        ps = ('MonofukiNF' if 'Nerd' in family else 'Monofuki')+'-'+digest[:8]+'-'+style
        subfamily = {'Regular':'Regular','Bold':'Bold','Italic':'Italic','BoldItalic':'Bold Italic'}[style]
        for record in list(font['name'].names):
            values = {1:family, 3:ps, 4:family+' '+subfamily, 6:ps, 16:family, 17:subfamily}
            if record.nameID in values:
                font['name'].setName(values[record.nameID], record.nameID, record.platformID, record.platEncID, record.langID)
        if cff:
            font['CFF '].cff.fontNames = [ps]
            cff.FamilyName, cff.FullName = family, family+' '+subfamily
    font['head'].modified = font['head'].created
    if font['cmap'].compile(font) != before_cmap:
        raise ValueError('Unicode cmap changed')
    result = io.BytesIO()
    font.save(result, reorderTables=True)
    return result.getvalue(), {'configuration_sha256':digest,'configuration':config,'family':family,'style':style,
                              'base_sha256':hashlib.sha256(base_bytes).hexdigest(),'encoded_characters':len(cmap),
                              'spacing':spacing,'cell':settings['cell'],'compiler_version':COMPILER_VERSION}


_WOFF2_LOCK = RLock()


class _BrotliQuality:
    def __init__(self, encoder, quality):
        self.encoder, self.quality = encoder, quality

    def compress(self, data, **options):
        options.setdefault('quality', self.quality)
        return self.encoder.compress(data, **options)

    def __getattr__(self, name):
        return getattr(self.encoder, name)


def to_woff2(data, quality=9):
    # fontTools 4.56 has no writer quality option. Scope a proxy to this
    # synchronous save; leave the Brotli module itself untouched and restore
    # fontTools' encoder even on errors. The lock protects native callers.
    from fontTools.ttLib import woff2
    with _WOFF2_LOCK:
        encoder = woff2.brotli
        try:
            woff2.brotli = _BrotliQuality(encoder, quality)
            font = TTFont(io.BytesIO(data), recalcTimestamp=False)
            font.flavor = 'woff2'
            result = io.BytesIO()
            font.save(result)
            return result.getvalue()
        finally:
            woff2.brotli = encoder
