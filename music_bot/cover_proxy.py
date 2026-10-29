"""Bounded artwork proxy for direct Mini App hosting."""
from urllib.parse import urlsplit
import re

import aiohttp
from aiohttp import web

HOSTS = {'lastfm.freetls.fastly.net', 'lastfm-img.freetls.fastly.net',
         'lastfm-img2.akamaized.net'}
TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/avif'}
LIMIT = 2097152


def valid_cover_url(raw):
    try:
        url = urlsplit(raw)
        return bool(raw and len(raw) <= 1500 and url.scheme == 'https'
                    and url.hostname in HOSTS and not url.username
                    and not url.password and not url.port and not url.query
                    and not url.fragment and not url.netloc.endswith(':')
                    and '2a96cbd8b46e442fc41c2b86b821562f' not in url.path
                    and not any(ord(c) <= 32 or ord(c) == 127 for c in raw)
                    and '\\' not in raw)
    except (ValueError, TypeError, AttributeError):
        return False


def register_cover_proxy(app, *, session_factory=aiohttp.ClientSession):
    async def cover(request):
        raw = request.query.get('url', '')
        if not valid_cover_url(raw):
            raise web.HTTPBadRequest()
        # No incoming headers, cookies or Telegram authentication are forwarded.
        async with session_factory(timeout=aiohttp.ClientTimeout(total=8),
                                   trust_env=False) as session:
            try:
                async with session.get(raw, allow_redirects=False,
                                       headers={'Accept': ', '.join(sorted(TYPES))}) as upstream:
                    mime = upstream.headers.get('Content-Type', '').split(';')[0].lower()
                    if upstream.status != 200 or mime not in TYPES:
                        raise web.HTTPNotFound()
                    if upstream.content_length is not None and upstream.content_length > LIMIT:
                        raise web.HTTPRequestEntityTooLarge(max_size=LIMIT,
                                                            actual_size=upstream.content_length)
                    data = bytearray()
                    async for chunk in upstream.content.iter_chunked(65536):
                        data.extend(chunk)
                        if len(data) > LIMIT:
                            raise web.HTTPRequestEntityTooLarge(max_size=LIMIT, actual_size=len(data))
                    return web.Response(body=bytes(data), content_type=mime,
                                        headers={'X-Content-Type-Options': 'nosniff',
                                                 'Cache-Control': ('public, max-age=31536000, immutable' if re.fullmatch(r'/i/u/(?:174s|300x300|600x600)/[a-f0-9]{32}\.(?:png|jpg|jpeg|webp)', urlsplit(raw).path) else 'public, max-age=86400'),
                                                 'Referrer-Policy': 'no-referrer'})
            except (aiohttp.ClientError, TimeoutError):
                raise web.HTTPBadGateway() from None

    app.router.add_get('/cover', cover)
