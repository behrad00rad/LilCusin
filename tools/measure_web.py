"""Reproduce static body budgets; optionally inspect an explicit public origin.

python tools/measure_web.py [--origin https://your-miniapp-origin]
Excludes artwork, Telegram SDK, API bodies, headers and TLS overhead.
"""
import argparse
import gzip
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--origin')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1] / 'music_bot/web'
for name in ['index.html', 'app.js', 'social.js', 'style.css', 'locales.json', 'bot-logo.jpg', 'vazirmatn.woff2']:
    data = (root / name).read_bytes()
    result = {'asset': name, 'source_bytes': len(data), 'gzip_bytes': len(gzip.compress(data, compresslevel=6, mtime=0))}
    if args.origin:
        url = args.origin.rstrip('/') + '/' + ('' if name == 'index.html' else name)
        response = urlopen(Request(url, headers={'Accept-Encoding': 'gzip'}), timeout=15)
        result.update(wire_body_bytes=len(response.read()), encoding=response.headers.get('Content-Encoding'), cache=response.headers.get('Cache-Control'))
        etag = response.headers.get('ETag')
        if etag:
            try:
                cached = urlopen(Request(url, headers={'Accept-Encoding': 'gzip', 'If-None-Match': etag}), timeout=15)
                result['conditional_status'] = cached.status
            except HTTPError as error:
                result['conditional_status'] = error.code
    print(json.dumps(result))
