"""Offline HTTP contracts for public caching, compression and bounded covers."""
import gzip
import tempfile
import unittest
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from music_bot.web_assets import asset_response, representation
from music_bot.cover_proxy import register_cover_proxy, valid_cover_url, LIMIT


class WebPerformanceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'locales.json'
        self.data = ('{"fa":"سلام", "en":"hello"}' * 500).encode()
        self.path.write_bytes(self.data)
        app = web.Application()
        async def asset(request): return asset_response(request, self.path)
        app.router.add_get('/asset', asset)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        representation.cache_clear()
        self.temp.cleanup()

    async def test_compression_negotiation_and_revalidation(self):
        response = await self.client.get('/asset', headers={'Accept-Encoding': 'gzip'}, auto_decompress=False)
        self.assertEqual(gzip.decompress(await response.read()), self.data)
        self.assertLess(int(response.headers['Content-Length']), len(self.data) // 2)
        self.assertEqual(response.headers['Cache-Control'], 'public, no-cache')
        self.assertEqual(response.headers['Vary'], 'Accept-Encoding')
        etag = response.headers['ETag']
        cached = await self.client.get('/asset', headers={'Accept-Encoding': 'gzip', 'If-None-Match': 'W/' + etag})
        self.assertEqual(cached.status, 304)
        self.assertEqual(await cached.read(), b'')
        plain = await self.client.get('/asset', headers={'Accept-Encoding': 'gzip;q=0, *;q=1'})
        self.assertNotIn('Content-Encoding', plain.headers)
        self.assertEqual(await plain.read(), self.data)
        self.assertNotEqual(plain.headers['ETag'], etag)
        head = await self.client.head('/asset', headers={'Accept-Encoding': 'identity'})
        self.assertEqual(int(head.headers['Content-Length']), len(self.data))
        self.assertEqual(await head.read(), b'')

    async def test_asset_edit_invalidates_validator(self):
        first = await self.client.get('/asset')
        self.path.write_bytes(b'{"new":true}')
        second = await self.client.get('/asset', headers={'If-None-Match': first.headers['ETag']})
        self.assertEqual(second.status, 200)
        self.assertNotEqual(first.headers['ETag'], second.headers['ETag'])
        self.assertEqual(await second.json(), {'new': True})

    async def test_cover_is_bounded_and_private_headers_never_forwarded(self):
        calls = []
        class Content:
            async def iter_chunked(self, size):
                yield b'webp'
        class Upstream:
            status = 200
            headers = {'Content-Type': 'image/webp'}
            content_length = 4
            content = Content()
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
        class Session:
            def __init__(self, **kw): calls.append(kw)
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def get(self, url, **kw): calls.append(kw); return Upstream()
        app = web.Application()
        register_cover_proxy(app, session_factory=Session)
        async with TestClient(TestServer(app)) as client:
            url = 'https://lastfm.freetls.fastly.net/i/u/174s/' + 'a' * 32 + '.webp'
            response = await client.get('/cover', params={'url': url}, headers={'Authorization': 'fixture', 'X-Telegram-Init-Data': 'fixture'})
            self.assertEqual(await response.read(), b'webp')
            self.assertIn('immutable', response.headers['Cache-Control'])
            self.assertFalse(calls[1]['allow_redirects'])
            self.assertEqual(set(calls[1]['headers']), {'Accept'})
            self.assertFalse(calls[0]['trust_env'])
            Upstream.content_length = LIMIT + 1
            self.assertEqual((await client.get('/cover', params={'url': url})).status, 413)
            Upstream.content_length = None
            async def oversized(self, size): yield b'x' * (LIMIT + 1)
            Content.iter_chunked = oversized
            self.assertEqual((await client.get('/cover', params={'url': url})).status, 413)
            self.assertEqual((await client.get('/cover', params={'url': 'https://evil.example/a.png'})).status, 400)

    def test_cover_url_guards(self):
        for raw in ['https://lastfm.freetls.fastly.net:443/a', 'http://lastfm.freetls.fastly.net/a', 'https://user@lastfm.freetls.fastly.net/a', 'https://lastfm.freetls.fastly.net/a?b=c', 'https://lastfm.freetls.fastly.net/a\\b', 'https://lastfm.freetls.fastly.net/2a96cbd8b46e442fc41c2b86b821562f.png']:
            self.assertFalse(valid_cover_url(raw), raw)
