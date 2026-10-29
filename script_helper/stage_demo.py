"""Stage the exact selected movie and its separate recording provenance."""
import hashlib
import json
import shutil
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'website/media'


def stage_demo(destination, source=SOURCE):
    metadata = json.loads((source / 'recording.json').read_text())
    if metadata.get('schema_version') != 1 or set(metadata['files']) != {'monofuki.mp4', 'demo-poster.png'}:
        raise ValueError('Unexpected recording manifest')
    for name, expected in metadata['files'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Recording changed: {name}')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name in (*metadata['files'], 'recording.json'):
        shutil.copyfile(source / name, destination / name)
    return metadata
