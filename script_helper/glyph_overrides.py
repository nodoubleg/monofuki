"""Apply individually fingerprinted SFD glyph records using symbolic dependencies."""
import hashlib
import re
from pathlib import Path

RECORD = re.compile(r'^StartChar: .*?^EndChar\n', re.M | re.S)
ENCODING = re.compile(r'^Encoding: (-?\d+) (-?\d+) (\d+)$', re.M)
REFERENCE = re.compile(r'^Refer: (\d+) (-?\d+) ', re.M)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def identity(record):
    return record.splitlines()[0][11:], tuple(map(int, ENCODING.search(record).groups()))


def apply_overrides(text, style, entries, revision, root):
    base = {identity(r)[0]: r for r in RECORD.findall(text)}
    selected = {}
    required = {'style', 'glyph_name', 'codepoint', 'operation', 'source', 'source_sha256',
                'expected_upstream_revision', 'expected_base_sha256', 'dependencies'}
    for entry in entries:
        if set(entry) != required or entry['style'] not in ('Regular', 'Italic', 'Bold', 'Bold-Italic'):
            raise ValueError('Invalid authored override fields/style')
        if entry['style'] != style:
            continue
        name = entry['glyph_name']
        if name in selected:
            raise ValueError(f'Duplicate authored glyph: {name}')
        if entry['expected_upstream_revision'] != revision:
            raise ValueError(f'{name}: upstream revision drift; review override')
        path = (root / entry['source']).resolve()
        if not path.is_relative_to((root / 'src/overrides').resolve()) or not path.is_file():
            raise ValueError(f'{name}: source must be a file under src/overrides')
        record = path.read_text()
        if RECORD.fullmatch(record) is None or len(RECORD.findall(record)) != 1:
            raise ValueError(f'{name}: source must contain exactly one SFD glyph record')
        if digest(record) != entry['source_sha256']:
            raise ValueError(f'{name}: authored source fingerprint mismatch')
        cp = -1 if entry['codepoint'] is None else int(entry['codepoint'], 16)
        if entry['codepoint'] is not None and not (0 <= cp <= 0x10FFFF and not 0xD800 <= cp <= 0xDFFF):
            raise ValueError(f'{name}: invalid Unicode scalar')
        if identity(record)[0] != name or identity(record)[1][1] != cp:
            raise ValueError(f'{name}: glyph identity/codepoint mismatch')
        if entry['operation'] == 'replace':
            if name not in base or digest(base[name]) != entry['expected_base_sha256']:
                raise ValueError(f'{name}: base glyph drift; review override')
            if identity(base[name])[1][1] != cp:
                raise ValueError(f'{name}: replacement must retain character mapping')
        elif entry['operation'] == 'add':
            if name in base or entry['expected_base_sha256'] is not None:
                raise ValueError(f'{name}: addition now collides with base')
        else:
            raise ValueError(f'{name}: operation must be add or replace')
        selected[name] = (entry, record, cp)
    if not selected:
        return text, {}, {}
    ids = {name: identity(r)[1] for name, r in base.items()}
    next_gid = max(e[2] for e in ids.values()) + 1
    next_slot = max(0x110000, max(e[0] for e in ids.values()) + 1)
    mapped = {e[1] for e in ids.values() if e[1] >= 0}
    occupied_slots = {e[0] for e in ids.values()}
    for name, (entry, record, cp) in sorted(selected.items()):
        if name not in ids:
            if cp >= 0 and (cp in mapped or cp in occupied_slots):
                raise ValueError(f'{name}: character mapping collision')
            slot = cp if cp >= 0 else next_slot
            ids[name] = (slot, cp, next_gid)
            next_gid += 1
            next_slot = max(next_slot, slot + 1)
            if cp >= 0:
                mapped.add(cp)
    replacements, provenance = {}, {}
    for name, (entry, record, cp) in sorted(selected.items()):
        dependencies = {}
        for dep in entry['dependencies']:
            if set(dep) != {'source_gid', 'glyph_name', 'expected_source_sha256'}:
                raise ValueError(f'{name}: invalid dependency fields')
            dep_name, source_gid = dep['glyph_name'], dep['source_gid']
            if source_gid in dependencies or dep_name not in ids:
                raise ValueError(f'{name}: duplicate/missing dependency')
            underlying = selected[dep_name][1] if dep_name in selected else base[dep_name]
            if digest(underlying) != dep['expected_source_sha256']:
                raise ValueError(f'{name}: dependency drift: {dep_name}')
            dependencies[source_gid] = dep_name
        if set(dependencies) != {int(gid) for gid, _ in REFERENCE.findall(record)}:
            raise ValueError(f'{name}: dependency manifest does not match references')
        def remap(match):
            dep_name = dependencies[int(match[1])]
            _, dep_cp, dep_gid = ids[dep_name]
            if int(match[2]) != dep_cp:
                raise ValueError(f'{name}: dependency character mismatch: {dep_name}')
            return f'Refer: {dep_gid} {dep_cp} '
        result = REFERENCE.sub(remap, record)
        result = ENCODING.sub('Encoding: %d %d %d' % ids[name], result)
        replacements[name] = result
        provenance[name] = {'kind': 'authored', **entry}
    for name, result in replacements.items():
        if name in base:
            text = text.replace(base[name], result, 1)
        else:
            text = text.replace('EndChars\n', result + 'EndChars\n', 1)
    count = re.search(r'^BeginChars: (\d+) (\d+)$', text, re.M)
    text = text.replace(count[0], f'BeginChars: {max(int(count[1]), next_slot)} {len(ids)}', 1)
    return text, replacements, provenance
