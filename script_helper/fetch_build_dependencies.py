#!/usr/bin/env python3
"""Fetch checksum-pinned build inputs; print the requested local path on stdout."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'script_helper/build_dependencies.json').read_text())


def fetch(name, extract=True, manifest=None):
    spec = (manifest or MANIFEST)['assets'][name]
    cache = ROOT / '.font-build'
    cache.mkdir(exist_ok=True)
    destination = cache / spec['filename']
    if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != spec['sha256']:
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            download = Path(directory) / 'download'
            subprocess.run(['curl', '--fail', '--location', '--show-error', '--silent',
                            '--retry', '3', spec['url'], '-o', str(download)], check=True)
            if hashlib.sha256(download.read_bytes()).hexdigest() != spec['sha256']:
                raise ValueError(f'Checksum mismatch for {name}')
            download.replace(destination)
    if spec.get('archive') == 'zip' and extract:
        # Extract the verified archive afresh: edits to a cached patcher must not
        # silently change a later build. Reject archive paths outside the cache.
        target = cache / name
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            staging = Path(directory)
            with zipfile.ZipFile(destination) as archive:
                for entry in archive.infolist():
                    if ((entry.external_attr >> 16) & 0o170000) == 0o120000:
                        raise ValueError('Symlink in build archive')
                    if not (staging / entry.filename).resolve().is_relative_to(staging.resolve()):
                        raise ValueError('Unsafe archive path')
                archive.extractall(staging)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(staging, target)
        return target / 'font-patcher'
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset', choices=MANIFEST['assets'])
    print(fetch(parser.parse_args().asset))
