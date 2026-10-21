#!/usr/bin/env python3
"""Stage the specimen site using fonts from GitHub Actions (no generated files in Git)."""
import argparse
import hashlib
import html
import json
import re
import shutil
import zipfile
from pathlib import Path

from terminal_demo import CHARACTER_SAMPLE, art_pieces
from symbols_page import render_symbols
from build_tuning_site import stage as stage_tuning

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regular', type=Path, required=True, help='downloaded regular font artifact directory')
    parser.add_argument('--nerd', type=Path, required=True, help='downloaded Nerd Font artifact directory')
    parser.add_argument('--coretext', type=Path, required=True, help='same-run macOS CoreText preview artifact')
    parser.add_argument('--output', type=Path, default=ROOT / '_site')
    parser.add_argument('--revision', required=True, help='source commit SHA of the font build')
    parser.add_argument('--build-url', required=True, help='GitHub Actions run producing these fonts')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-fA-F]{40}', args.revision):
        parser.error('revision must be a full Git commit SHA')
    output = args.output.resolve()
    # Do not permit an output path that could overwrite project source.
    protected = (ROOT / name for name in ('website', 'src', 'script_helper', '.git', '.agents', '.codex'))
    if output == ROOT or ROOT.is_relative_to(output) or any(output.is_relative_to(path) for path in protected):
        parser.error('output must be a separate generated directory')
    output.mkdir(parents=True, exist_ok=True)
    for directory in ('fonts', 'licenses', 'media', 'downloads'):
        (output / directory).mkdir(exist_ok=True)
    for name in ('style.css', 'specimen.js', 'symbols.js'):
        shutil.copy2(ROOT / 'website' / name, output / name)
    shutil.copytree(ROOT / 'website/assets', output / 'assets', dirs_exist_ok=True)
    hashes = {}
    for family, directory, styles in (
        ('Monofuki', args.regular, ('Regular', 'Italic', 'Bold', 'Bold-Italic')),
        ('MonofukiNerdFont', args.nerd, ('Regular',)),
    ):
        for style in styles:
            name = f'{family}-{style}.woff2'
            source = directory / name
            if not source.is_file() or source.stat().st_size == 0:
                parser.error(f'missing CI font: {source}')
            shutil.copy2(source, output / 'fonts' / name)
            hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    for directory in (args.regular, args.nerd):
        for name in ('LICENSE-*', '*audit*.md', 'NOTICES-*.md'):
            for license_path in directory.glob(name):
                shutil.copy2(license_path, output / 'licenses' / license_path.name)
    # Serve all exact component notices beside the font files.
    for name in ('THIRD-PARTY-NOTICES.txt', 'component-provenance.json'):
        shutil.copy2(args.nerd / name, output / 'licenses' / name)
    shutil.copytree(args.nerd / 'component-notices', output / 'licenses/component-notices', dirs_exist_ok=True)
    # Download bundles come from this same build, not historical Monofoki releases.
    for family, directory in (('Monofuki', args.regular), ('MonofukiNerdFont', args.nerd)):
        files = {p for p in directory.glob(f'{family}-*') if p.suffix in ('.otf', '.ttf', '.woff2')}
        if len(list(directory.glob(f'{family}-*.otf'))) != 4:
            parser.error(f'{family}: download bundle needs four OTF styles')
        for pattern in ('LICENSE-*', 'NOTICES-*.md', '*audit*.md', '*provenance.json', '*dependencies.json', '*additions.json', '*overlays.json', '*policy.json', '*decisions.json', 'emoji-*.json', 'tuning-settings.json', 'THIRD-PARTY-NOTICES.txt'):
            files.update(directory.glob(pattern))
        files.update(p for p in (directory / 'component-notices').rglob('*') if p.is_file())
        for required in ('THIRD-PARTY-NOTICES.txt', 'component-provenance.json', 'source-provenance.json'):
            if directory / required not in files:
                parser.error(f'{family}: missing {required}')
        with zipfile.ZipFile(output / 'downloads' / f'{family}.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(files):
                archive.writestr(str(path.relative_to(directory)), path.read_bytes())
    dependencies = json.loads((ROOT / 'script_helper/build_dependencies.json').read_text())
    catalog = json.loads((args.nerd / 'character-catalog.json').read_text())
    for variant, path in (('regular', args.regular / 'Monofuki-Regular.otf'), ('nerd', args.nerd / 'MonofukiNerdFont-Regular.otf')):
        if hashlib.sha256(path.read_bytes()).hexdigest() != catalog['font_sha256'][variant]:
            parser.error(f'character catalogue does not match {variant} font input')
    (output / 'coretext').mkdir(exist_ok=True)
    for name in ('coretext.json', 'regular-dark.png', 'regular-light.png', 'nerd-dark.png', 'nerd-light.png'):
        shutil.copy2(args.coretext / name, output / 'coretext' / name)
    shutil.copy2(args.nerd / 'character-catalog.json', output / 'character-catalog.json')
    stylesheet = (output / 'style.css').read_text()
    for name, digest in hashes.items():
        stylesheet = stylesheet.replace(f'fonts/{name}', f'fonts/{name}?v={digest}')
    for name in ('regular-dark.png', 'regular-light.png', 'nerd-dark.png', 'nerd-light.png'):
        digest = hashlib.sha256((output / 'coretext' / name).read_bytes()).hexdigest()
        stylesheet = stylesheet.replace(f'coretext/{name}', f'coretext/{name}?v={digest}')
    (output / 'style.css').write_text(stylesheet)
    gallery = []
    for key, title, description, text in art_pieces():
        gallery.append(f'<figure id="art-{key}"><pre aria-hidden="true">{html.escape(text)}</pre>'
                       f'<figcaption>{html.escape(title)}<small>{html.escape(description)}</small></figcaption></figure>')
    replacements = {'@@ART_GALLERY@@': '\n'.join(gallery), '@@CHARACTER_SAMPLE@@': html.escape(CHARACTER_SAMPLE),
                    '@@BUILD_URL@@': html.escape(args.build_url, quote=True), '@@BUILD_REVISION@@': html.escape(args.revision[:7])}
    replacements.update(render_symbols(args.nerd, args.coretext))
    text_demo = '\n\n'.join(f'{title}\n\n{text}' for _, title, _, text in art_pieces())
    (output / 'demo.txt').write_text(f'Monofuki terminal specimen\n\n{CHARACTER_SAMPLE}\n\n{text_demo}\n')
    def version_asset(match):
        attribute, url = match.groups()
        if url.startswith(('https://', 'http://', '//', '#')) or url.split('#')[0].endswith('.html'):
            return match[0]
        path = output / url
        # Media is rendered after staging; its revision still provides a new
        # cache key whenever the tape or demo changes. Other files use bytes.
        version = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not url.startswith('media/') else args.revision
        return f'{attribute}="{url}?v={version}"'
    for name in ('index.html', 'symbols.html'):
        document = (ROOT / 'website' / name).read_text()
        for marker, value in replacements.items():
            document = document.replace(marker, value)
        if re.search(r'@@[A-Z_]+@@', document):
            parser.error(f'unresolved template marker in {name}')
        document = re.sub(r'\b(href|src|poster)="([^"]+)"', version_asset, document)
        (output / name).write_text(document)
    tuning_hash = stage_tuning(output, args.regular, args.nerd, args.revision)
    (output / 'build.json').write_text(json.dumps({'revision': args.revision, 'build_url': args.build_url, 'tuning_configuration_sha256': tuning_hash,
                                                'font_sha256': hashes, 'vhs_version': '0.12.1',
                                                'nerd_fonts_version': dependencies['nerd_fonts_version'],
                                                'unicode_version': dependencies['unicode_version']}, indent=2) + '\n')
    (output / '.nojekyll').touch()
    print(f'Staged {len(hashes)} CI webfonts and {len(gallery)} shared art pieces in {output}')


if __name__ == '__main__':
    main()
