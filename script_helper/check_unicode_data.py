#!/usr/bin/env python3
"""Check pinned Unicode data and the Perl specimen independently of host UCD."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / 'script_helper'
catalog = json.loads((HELPERS / 'terminal_ranges.json').read_text())
directory = HELPERS / 'unicode' / catalog['unicode_version']
for line in (directory / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split()
    assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest, name
assigned = {int(line.split(';')[0], 16) for line in (directory / 'UnicodeData.txt').read_text().splitlines()
            if not line.split(';')[2] in ('Cc', 'Cf', 'Cs')}
targets = {cp for _, _, first, last in catalog['blocks'] for cp in range(first, last + 1)} & assigned
assert len(targets) == catalog['assigned_printable'] == 2113
emoji = {int(match[1], 16) for line in (directory / 'emoji-variation-sequences.txt').read_text().splitlines()
         if (match := re.match(r'^([0-9A-F]+) FE0F\s*;', line)) and int(match[1], 16) >= 128}
assert len(targets & emoji) == catalog['non_ascii_emoji_bases'] == 159
command = ['perl', str(HELPERS / 'unicode_specimen.pl'), '--names']
output = subprocess.check_output(command, text=True)
printed = {int(match[1], 16) for match in re.finditer(r'^([0-9A-F]{5})\? ', output, re.MULTILINE)}
assert printed == targets, (len(printed), len(targets))
assert output.count('\ufe0f') == 159
assert '\ufe0f' not in subprocess.check_output(command + ['--presentation', 'native'], text=True)
assert '1FBFA? [\U0001fbfa]' in output
assert '02BB7? [\u2bb7]' in output
assert '00023? [#]' in output
print('PASS Unicode 18.0.0: 2113 assigned symbols, 159 emoji sequences; Perl uses bundled data')

# Current donor additions are text symbols, not default-emoji substitutions.
from audit_emoji import properties
props = properties()
added = {int(item['codepoint'], 16) for item in json.loads((HELPERS / 'symbol_additions.json').read_text())['additions']}
assert not added & props['Emoji_Presentation'], 'Default-emoji donor addition needs explicit presentation review'
print(f"Emoji audit: {len(added & props['Emoji'])} emoji-capable donor additions; no default-emoji additions")
