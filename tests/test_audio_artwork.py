import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

from music_bot.audio_artwork import artwork_key, prepare, embed_atomic, image_bytes, MAX_IMAGE_BYTES
from music_bot.youtube_fetch import FetchError

ART = 'https://lastfm.freetls.fastly.net/i/u/300x300/album.jpg'
JPEG = b'\xff\xd8test\xff\xd9'


class AudioArtworkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.audio = self.folder/'source.m4a'
        self.audio.write_bytes(b'original audio')
        self.track = NS(artwork_url=ART, album='Album', artist='Artist', title='Song',
                        display_artist=None, display_title=None)
        async def convert(*args):
            (self.folder/'cover.jpg').write_bytes(JPEG)
        self.fetcher = NS(process=AsyncMock(side_effect=convert), settings=NS(max_bytes=1000000, disk_bytes=3000000))
        self.alive = AsyncMock(return_value=True)

    def tearDown(self):
        self.temp.cleanup()

    async def test_reuses_canonical_art_and_produces_bounded_jpeg(self):
        with patch('music_bot.audio_artwork.image_bytes', AsyncMock(return_value=b'image')) as download, \
             patch('music_bot.audio_artwork.embed_atomic') as embed:
            thumb, key = await prepare(self.fetcher, self.track, self.audio, self.folder, self.alive)
        download.assert_awaited_once_with(ART)
        self.assertEqual(thumb, self.folder/'cover.jpg')
        self.assertEqual(key, artwork_key(self.track))
        self.assertEqual(embed.call_args.args[1], JPEG)
        self.assertFalse((self.folder/'cover.input').exists())

    async def test_invalid_artwork_url_never_downloaded(self):
        for url in ['http://127.0.0.1/private', 'https://evil.example/cover.jpg', ART+'?secret=value']:
            self.track.artwork_url = url
            with patch('music_bot.audio_artwork.image_bytes', AsyncMock()) as download:
                self.assertEqual(await prepare(self.fetcher, self.track, self.audio, self.folder, self.alive), (None, None))
                download.assert_not_awaited()

    async def test_artwork_failure_preserves_audio_and_cancellation_prevents_send(self):
        with patch('music_bot.audio_artwork.image_bytes', AsyncMock(side_effect=RuntimeError('private details'))):
            self.assertEqual(await prepare(self.fetcher, self.track, self.audio, self.folder, self.alive), (None, None))
        self.assertEqual(self.audio.read_bytes(), b'original audio')
        self.alive.return_value = False
        with patch('music_bot.audio_artwork.image_bytes', AsyncMock(return_value=b'image')):
            with self.assertRaises(FetchError):
                await prepare(self.fetcher, self.track, self.audio, self.folder, self.alive)
        self.assertFalse((self.folder/'cover.input').exists())

    def test_tagging_failure_is_atomic(self):
        def corrupt(path, *args):
            path.write_bytes(b'broken')
            raise ValueError('tag failure')
        with patch('music_bot.audio_artwork.embed', side_effect=corrupt):
            with self.assertRaises(ValueError):
                embed_atomic(self.audio, JPEG, self.track, 1000000)
        self.assertEqual(self.audio.read_bytes(), b'original audio')
        self.assertFalse((self.folder/'tagged.m4a').exists())

    async def test_download_rejects_redirects_and_oversized_streams(self):
        class Context:
            def __init__(self, value): self.value = value
            async def __aenter__(self): return self.value
            async def __aexit__(self, *args): return False
        async def stream(*args):
            yield b'x' * (MAX_IMAGE_BYTES + 1)
        for status, length in [(302, None), (200, MAX_IMAGE_BYTES+1), (200, None)]:
            response = NS(status=status, content_length=length, headers={'Content-Type': 'image/jpeg'},
                          content=NS(iter_chunked=stream))
            session = NS(get=Mock(return_value=Context(response)))
            with patch('music_bot.audio_artwork.aiohttp.ClientSession', return_value=Context(session)):
                with self.assertRaises(ValueError):
                    await image_bytes(ART)
            session.get.assert_called_once_with(ART, allow_redirects=False)
