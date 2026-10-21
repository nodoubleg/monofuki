#!/usr/bin/env python3
"""Fetch exact static browser compiler inputs into ignored build storage."""
import argparse
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fetch(destination):
    lock = json.loads((ROOT/'script_helper/tuning-runtime-lock.json').read_text())
    destination.mkdir(parents=True, exist_ok=True)
    for name, spec in lock['assets'].items():
        target = destination/name
        data = target.read_bytes() if target.exists() else urllib.request.urlopen(spec['url']).read()
        if hashlib.sha256(data).hexdigest() != spec['sha256']:
            raise ValueError(f'Browser runtime checksum mismatch: {name}')
        if not target.exists():
            target.write_bytes(data)
    notices = destination/'component-notices'
    notices.mkdir(exist_ok=True)
    for filename in lock['assets']:
        if filename.endswith('.whl'):
            with zipfile.ZipFile(destination/filename) as archive:
                for name in archive.namelist():
                    if '.dist-info/' in name and Path(name).name.lower() in ('license','license.txt','copying','notice'):
                        (notices/(filename.split('-')[0]+'-'+Path(name).name)).write_bytes(archive.read(name))
    return lock


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('destination', type=Path)
    fetch(p.parse_args().destination)
