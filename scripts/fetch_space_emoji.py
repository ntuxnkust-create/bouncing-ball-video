#!/usr/bin/env python3
"""Fetch exact Twemoji 14.0.2 assets using normal verified HTTPS."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://raw.githubusercontent.com/twitter/twemoji/v14.0.2/'
FILES = ['2b50', '1f319', '1fa90', '1f30d', '2600', '1f30c', '1f680']


def fetch(name):
    path = ROOT/'assets/emoji'/f'{name}.png'
    data = urllib.request.urlopen(BASE+f'assets/72x72/{name}.png', timeout=30).read()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise RuntimeError('Not a PNG: '+name)
    path.write_bytes(data)
    return {'file': path.name, 'sha256': hashlib.sha256(data).hexdigest(),
            'source': BASE+f'assets/72x72/{name}.png'}


def main():
    directory = ROOT/'assets/emoji'
    directory.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch, FILES))
    (directory/'manifest.json').write_text(json.dumps(records, indent=2)+'\n')
    license_data = urllib.request.urlopen(BASE+'LICENSE-GRAPHICS', timeout=30).read()
    (directory/'LICENSE-GRAPHICS').write_bytes(license_data)
    print('Downloaded 7 consistent full-color Twemoji PNGs with attribution and SHA-256 manifest.')


if __name__ == '__main__':
    main()
