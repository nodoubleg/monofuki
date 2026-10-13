"""Fingerprint-bound decisions for generated/donor collisions with upstream."""
import hashlib
import json
import re


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def overlay_hash(record):
    # Assembly assigns IDs; ownership hashes exclude that incidental assignment.
    return sha(re.sub(r'^Encoding: (-?\d+) (-?\d+) \d+$', r'Encoding: \2 \2 0', record, flags=re.M))


def binding(style, kind, cp, candidate, overlay, revision):
    return {'style': style, 'kind': kind, 'codepoint': f'{cp:04X}',
            'glyph_name': candidate.splitlines()[0][11:],
            'candidate_revision': revision, 'candidate_sha256': sha(candidate),
            'overlay_sha256': overlay_hash(overlay)}


def accepted_action(decisions, expected):
    matches = [d for d in decisions if all(d.get(k) == v for k, v in expected.items())]
    if len(matches) != 1 or matches[0].get('action') not in ('adopt-upstream', 'keep-overlay'):
        raise ValueError(f"Unreviewed/stale upstream collision: {expected['style']} {expected['codepoint']}")
    return matches[0]['action']


def replace_identity(record, base):
    name = base.splitlines()[0]
    encoding = re.search(r'^Encoding:.*$', base, re.M)[0]
    record = re.sub(r'^StartChar:.*$', lambda _: name, record, count=1, flags=re.M)
    return re.sub(r'^Encoding:.*$', lambda _: encoding, record, count=1, flags=re.M)
