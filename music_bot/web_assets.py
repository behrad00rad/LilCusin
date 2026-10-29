"""Finite, revalidated public assets; never cache authenticated API responses."""
import gzip
import hashlib
import mimetypes
from functools import lru_cache

from aiohttp import web


@lru_cache(maxsize=16)
def representation(path, mtime_ns, size, compressed):
    data = path.read_bytes()
    if compressed:
        data = gzip.compress(data, compresslevel=6, mtime=0)
    return data, '"' + hashlib.sha256(data).hexdigest() + '"'


def asset_response(request, path):
    text = path.suffix in {'.html', '.js', '.css', '.json', '.txt'}
    # Parse encoding weights explicitly: compression is optional, identity always works.
    encodings = {}
    for entry in request.headers.get('Accept-Encoding', '').lower().split(','):
        parts = entry.strip().split(';')
        try:
            encodings[parts[0]] = float(next((p.strip()[2:] for p in parts[1:] if p.strip().startswith('q=')), '1'))
        except ValueError:
            encodings[parts[0]] = 0
    compressed = text and encodings.get('gzip', encodings.get('*', 0)) > 0
    stat = path.stat()
    data, etag = representation(path, stat.st_mtime_ns, stat.st_size, compressed)
    headers = {'Cache-Control': 'public, no-cache', 'ETag': etag,
               'Vary': 'Accept-Encoding', 'Content-Type': mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}
    if text:
        headers['Content-Type'] += '; charset=utf-8'
    if compressed:
        headers['Content-Encoding'] = 'gzip'
    matches = request.headers.get('If-None-Match', '').split(',')
    if any(item.strip().removeprefix('W/') in {etag, '*'} for item in matches):
        return web.Response(status=304, headers=headers)
    headers['Content-Length'] = str(len(data))
    return web.Response(body=data if request.method != 'HEAD' else None, headers=headers)
