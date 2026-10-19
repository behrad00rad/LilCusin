"""Opt-in network smoke test using the ShazamIO project's public sample.

Run: python -m tests.recognition_live_check
Never loads bot credentials or polls Telegram. Temporary audio is deleted.
"""
import asyncio
import tempfile
from pathlib import Path

import aiohttp
from music_bot.recognition import Recognition, ShazamProvider, RecognitionError


async def main():
    trace = aiohttp.TraceConfig()
    async def request_end(session, context, params):
        print('HTTP status:', params.response.status)
    trace.on_request_end.append(request_end)
    async with aiohttp.ClientSession(trace_configs=[trace]) as session:
        with tempfile.TemporaryDirectory(prefix='recognition-smoke-') as directory:
            root = Path(directory)
            async with session.get('https://raw.githubusercontent.com/shazamio/ShazamIO/master/examples/data/Gloria.ogg',
                    timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    data.extend(chunk)
                    if len(data) > 5_000_000:
                        raise RuntimeError('Fixture exceeds limit')
            source = root / 'fixture.ogg'
            source.write_bytes(data)
            sample = root / 'sample.wav'
            service = Recognition(None, None, True)
            service.check()
            await service.fetcher.process([service.ffmpeg, '-nostdin', '-v', 'error',
                '-i', str(source), '-t', '12', '-vn', '-ac', '1', '-ar', '22050',
                '-codec:a', 'pcm_s16le', str(sample)], directory, service.alive)
            print('FFmpeg extracted 12-second WAV:', sample.stat().st_size > 1024)
            try:
                result = await ShazamProvider(session).recognize(sample)
                print('Live recognition:', result or 'no match')
                if not result:
                    raise SystemExit(1)
            except RecognitionError:
                print('Live recognition unavailable; no provider error details retained.')
                raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
