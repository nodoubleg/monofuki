#!/usr/bin/env python3
"""Compile the approved configuration from this run's full regular/Nerd exports."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from tuning_compiler import compile_font, config_identity, to_woff2

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path, default=ROOT/'export')
    parser.add_argument('--from-base', action='store_true', help='rebuild from the saved same-run untuned inputs')
    parser.add_argument('--settings', type=Path, default=ROOT/'src/tuning/defaults.json')
    args = parser.parse_args()
    settings = json.loads(args.settings.read_text())
    provenance = json.loads((ROOT/'src/tuning/provenance.json').read_text())
    inventory = json.loads((ROOT/'.font-build/assembled/glyph-provenance.json').read_text())
    for style, expected in provenance['expected_base_records'].items():
        actual = {g['glyph_name']:g['record_sha256'] for g in inventory['styles'][style]}
        if any(actual.get(name) != sha for name,sha in expected.items()):
            raise ValueError('Tuning source drift; review topology-specific masks before rebuilding '+style)
    geometry = json.loads(subprocess.check_output(['node', str(ROOT/'script_helper/tuning_reference.cjs'), str(args.settings)]))
    base = args.export/'tuning-base'
    base.mkdir(exist_ok=True)
    reports = {}
    for family in ('Monofuki', 'MonofukiNerdFont'):
        for style in ('Regular', 'Italic', 'Bold', 'BoldItalic'):
            suffix = style.replace('BoldItalic','Bold-Italic') if family == 'Monofuki' else style
            for ext in ('otf','ttf'):
                name = f'{family}-{suffix}.{ext}'
                source = args.export/name
                # Each caller supplies a newly built base. Never retune an output.
                if not args.from_base:
                    prior = args.export/'tuning-provenance.json'
                    if prior.exists() and json.loads(prior.read_text()).get('files',{}).get(name,{}).get('output_sha256') == hashlib.sha256(source.read_bytes()).hexdigest():
                        raise ValueError('Already tuned; rebuild bases or use --from-base')
                    shutil.copy2(source, base/name)
                data, report = compile_font((base/name).read_bytes(), geometry['styles'][style], settings, style, default=True)
                source.write_bytes(data)
                report['output_sha256'] = hashlib.sha256(data).hexdigest()
                reports[name] = report
                print(f'Tuned {name}: {report["encoded_characters"]} encoded characters', flush=True)
                if ext == 'otf':
                    (args.export/f'{family}-{suffix}.woff2').write_bytes(to_woff2(data))
            if family == 'Monofuki':
                ttf = args.export/f'{family}-{suffix}.ttf'
                hinted = args.export/f'{family}-{suffix}-hinted.ttf'
                subprocess.run(['ttfautohint', str(ttf), str(hinted)], check=True)
                (args.export/f'{family}-{suffix}-hinted.woff2').write_bytes(to_woff2(hinted.read_bytes()))
    (args.export/'tuning-provenance.json').write_text(json.dumps({'source_revision':subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'configuration_sha256':config_identity(settings)[0], 'compiler_sha256':hashlib.sha256((ROOT/'script_helper/tuning_compiler.py').read_bytes()).hexdigest(), 'transform_sha256':hashlib.sha256((ROOT/'website/tuning/app.js').read_bytes()).hexdigest(), 'reference_provenance':provenance, 'files':reports}, indent=2)+'\n')
    shutil.copy2(args.settings, args.export/'tuning-settings.json')


if __name__ == '__main__':
    main()
