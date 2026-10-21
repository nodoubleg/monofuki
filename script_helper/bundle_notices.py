#!/usr/bin/env python3
"""Bundle exact source notices and provenance, retaining each component's terms."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from fetch_build_dependencies import fetch, MANIFEST, ROOT


def bundle(output):
    output.mkdir(parents=True, exist_ok=True)
    notices = output / 'component-notices'
    notices.mkdir(exist_ok=True)
    entries = []
    def save(name, data, source, **metadata):
        path = notices / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        entries.append({'file': name, 'source': source, 'sha256': hashlib.sha256(data).hexdigest(), **metadata})
    archive = fetch('nerd-font-patcher', extract=False)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            name = Path(item.filename)
            if '..' in name.parts or name.is_absolute():
                raise ValueError('Unsafe archive notice path')
            if item.is_dir():
                continue
            if name.name.lower().startswith(('license', 'copying', 'notice', 'ofl', 'readme')):
                save('nerd-fonts/' + item.filename, z.read(item),
                     MANIFEST['assets']['nerd-font-patcher']['url'] + '#' + item.filename,
                     archive_sha256=MANIFEST['assets']['nerd-font-patcher']['sha256'])
    for key, spec in MANIFEST['assets'].items():
        if key.startswith('notice-'):
            save(spec['filename'], fetch(key).read_bytes(), spec['url'], component=spec['component'], revision=spec['revision'])
    for path in [ROOT / 'LICENSE', *sorted((ROOT / 'licenses').glob('LICENSE-*'))]:
        expected = MANIFEST['vendored_files'][str(path.relative_to(ROOT))]
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Changed vendored notice: {path}')
        save('font-families/' + path.name, data, str(path.relative_to(ROOT)))
    manifest = {'nerd_fonts_version': MANIFEST['nerd_fonts_version'],
                'nerd_fonts_revision': MANIFEST['assets']['nerd-font-patcher']['revision'],
                'credit': 'Monofuki modifications by Greg Mason (nodoubleg), 2026.',
                'modifications': 'Monofuki renames the base family, generates Braille, selects/scales/positions and merges donor glyphs, then optionally runs the complete Nerd Fonts patcher with rectangle Braille. Imported Nerd Fonts modifications are retained; see the supplied component READMEs, including Font Awesome remix and Material Design U+F1522 repair.',
                'notes': ['Each component retains its own copyright and license terms; there is no blanket claim that all icons are exclusively OFL.',
                          'The Nerd Fonts glyph README says Font Logos 1.3.0, but the actual pinned font metadata is 1.4.0; the 1.4.0 Unlicense is supplied.',
                          'Hack extraglyphs metadata identifies 3.003; both Source Foundry MIT and Bitstream Vera notices are supplied.',
                          'Codicons tagged LICENSE includes the Jason Long Git Logo CC BY 3.0 attribution in addition to CC BY 4.0.',
                          'Font Awesome OTF is SVG-derived 6.5.1.custom2 with the 7.3.1 fa-volume addition; its source license is CC BY 4.0.'],
                'files': sorted(entries, key=lambda e: e['file'])}
    (output / 'component-provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')
    parts = ['MONOFUKI THIRD-PARTY NOTICES\n\n' + manifest['credit'] + '\n\n' + manifest['modifications'], *manifest['notes']]
    for entry in manifest['files']:
        parts.append('\n' + '=' * 72 + '\n' + entry['file'] + '\nSource: ' + entry['source'] + '\nSHA-256: ' + entry['sha256'] + '\n\n' + (notices / entry['file']).read_bytes().decode('utf-8-sig', errors='replace'))
    (output / 'THIRD-PARTY-NOTICES.txt').write_text('\n\n'.join(parts) + '\n')
    print(f'Bundled {len(entries)} exact notice/readme files with source URLs and hashes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path, default=ROOT / 'export')
    bundle(parser.parse_args().output)
