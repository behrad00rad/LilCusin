import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

from music_bot.recognition import (Recognition, RecognitionError, RecognitionSettings,
    ShazamProvider, ShazamHTTP, RecognizedSong, youtube_id, LimitedBuffer, MAX_BYTES)
from music_bot.config import ConfigError
from music_bot.i18n import language


def message(user=123, **values):
    data = dict(chat=NS(type='private'), from_user=NS(id=user, is_bot=False),
                sender_chat=None, audio=None, voice=None, video=None, video_note=None,
                document=None, text=None, answer=AsyncMock())
    data.update(values)
    return NS(**data)


def media():
    return NS(file_id='private-id', file_unique_id='unique', file_size=100)


class RecognitionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = NS(get_file=AsyncMock(return_value=NS(file_path='private/path', file_size=100)),
                      download_file=AsyncMock())
        self.provider = NS(recognize=AsyncMock(return_value='Artist — Title'))
        self.service = Recognition(self.bot, self.provider, enabled=True)
        self.service.ffmpeg = 'test-ffmpeg'
        self.paths = []

        async def download(path, destination, **kwargs):
            destination.write(b'audio')

        async def extract(args, directory, alive):
            self.paths.append(Path(directory))
            Path(args[-1]).write_bytes(b'sample' * 300)

        self.bot.download_file.side_effect = download
        self.service.fetcher.process = AsyncMock(side_effect=extract)

    async def asyncTearDown(self):
        await self.service.close()

    async def finish(self):
        await asyncio.gather(*list(self.service.jobs.values()))

    async def test_media_inputs_cache_and_cleanup(self):
        for index, kind in enumerate(('audio', 'voice', 'video', 'video_note', 'document')):
            msg = message(user=index + 1, **{kind: media()})
            await self.service.submit(msg)
            await self.finish()
            self.assertEqual(msg.answer.await_args.args[0], 'Artist — Title')
            self.assertFalse(self.service.jobs)
        self.provider.recognize.assert_awaited_once()
        self.assertTrue(all(not p.exists() for p in self.paths))

    async def test_no_match_tries_three_offsets(self):
        self.provider.recognize.return_value = None
        msg = message(audio=media())
        await self.service.submit(msg)
        await self.finish()
        self.assertEqual(self.provider.recognize.await_count, 3)
        self.assertIn('type the song name', msg.answer.await_args.args[0])
        offsets = [call.args[0][call.args[0].index('-ss') + 1]
                   for call in self.service.fetcher.process.await_args_list]
        self.assertEqual(offsets, ['0', '30', '60'])

    def test_duration_aware_offsets_do_not_skip_past_short_clip(self):
        from music_bot.recognition import sample_offsets
        self.assertEqual(sample_offsets(6), (0,))
        self.assertEqual(sample_offsets(24), (0, 6, 12))
        self.assertEqual(sample_offsets(180), (0, 84, 168))
        self.assertEqual(sample_offsets(None), (0, 30, 60))

    async def test_match_and_cached_match_queue_audio(self):
        self.provider.recognize.return_value = RecognizedSong('Artist — Band', 'Title')
        self.service.delivery = NS(request_recognized=AsyncMock(), cached_request=AsyncMock(), bind_status=AsyncMock())
        for user in (123, 456):
            msg = message(user=user, audio=media())
            await self.service.submit(msg)
            await self.finish()
            self.service.delivery.request_recognized.assert_awaited_with(user, 'Artist — Band', 'Title')
            self.assertEqual(msg.answer.await_args.args[0], 'Artist — Band — Title')
            self.service.delivery.bind_status.assert_awaited()
        self.provider.recognize.assert_awaited_once()

    async def test_delivery_failure_keeps_recognition(self):
        from music_bot.youtube_fetch import FetchError
        self.provider.recognize.return_value = RecognizedSong('Artist', 'Title')
        self.service.delivery = NS(request_recognized=AsyncMock(side_effect=FetchError('Request limit reached.')))
        msg = message(audio=media())
        await self.service.submit(msg)
        await self.finish()
        self.assertIn('audio delivery could not start', msg.answer.await_args.args[0])
        self.assertTrue(any(call.args[0] == 'Artist — Title' for call in msg.answer.await_args_list))

    async def test_provider_failure_is_not_no_match(self):
        self.provider.recognize.side_effect = RecognitionError('provider')
        msg = message(voice=media())
        await self.service.submit(msg)
        await self.finish()
        self.assertIn('service unavailable', msg.answer.await_args.args[0])
        self.assertFalse(self.paths[0].exists())

    async def test_cancel_cleans_media_and_job(self):
        entered = asyncio.Event()
        async def block(sample):
            entered.set()
            await asyncio.Future()
        self.provider.recognize.side_effect = block
        msg = message(video=media())
        await self.service.submit(msg)
        await asyncio.wait_for(entered.wait(), 2)
        await self.service.cancel(123)
        self.assertFalse(self.service.jobs)
        self.assertFalse(self.paths[0].exists())
        msg.answer.return_value.delete.assert_awaited_once()

    async def test_immediate_cancel_before_worker_starts(self):
        msg = message(audio=media())
        await self.service.submit(msg)
        await self.service.cancel(123)
        self.assertFalse(self.service.jobs)
        self.assertFalse(self.service.pending)
        msg.answer.return_value.delete.assert_awaited_once()

    async def test_private_only_oversize_and_disabled(self):
        msg = message(audio=media())
        msg.chat.type = 'group'
        await self.service.submit(msg)
        msg.answer.assert_not_awaited()
        msg.chat.type = 'private'
        msg.audio.file_size = MAX_BYTES + 1
        await self.service.submit(msg)
        self.assertIn('20 MB', msg.answer.await_args.args[0])
        self.bot.get_file.assert_not_awaited()
        self.service.enabled = False
        await self.service.submit(msg)
        self.assertIn('not configured', msg.answer.await_args.args[0])

    async def test_rate_limit_and_admission_are_atomic(self):
        async def wait(sample):
            await asyncio.Future()
        self.provider.recognize.side_effect = wait
        msg = message(audio=media())
        await asyncio.gather(self.service.submit(msg), self.service.submit(msg))
        self.assertEqual(len(self.service.jobs), 1)
        self.assertIn('Please wait', msg.answer.await_args.args[0])

    async def test_supported_link_and_unsupported_link(self):
        msg = message(text='https://youtu.be/dQw4w9WgXcQ')
        async def fetch(video, directory, alive):
            self.assertEqual(video, 'dQw4w9WgXcQ')
            source = Path(directory) / 'source.m4a'
            source.write_bytes(b'audio')
            return source
        self.service.fetcher.fetch = AsyncMock(side_effect=fetch)
        await self.service.submit(msg)
        await self.finish()
        self.bot.get_file.assert_not_awaited()
        self.service.fetcher.fetch.assert_awaited_once()
        self.assertEqual(msg.answer.await_args.args[0], "Artist — Title")
        other = message(user=456, text='https://example.com/file.mp3')
        await self.service.submit(other)
        self.assertIn('public YouTube', other.answer.await_args.args[0])

    async def test_persian_response(self):
        token = language.set('fa')
        try:
            msg = message(text='https://example.com')
            await self.service.submit(msg)
            self.assertIn('فایل صوتی', msg.answer.await_args.args[0])
        finally:
            language.reset(token)

    async def test_provider_valid_no_match_malformed_and_error(self):
        client = NS(recognize=AsyncMock(return_value={'track': {'title': 'Title',
            'subtitle': 'Artist', 'url': 'https://www.shazam.com/track/1/title'}}))
        provider = ShazamProvider(client=client)
        self.assertIn('Artist — Title', await provider.recognize(Path('sample.wav')))
        client.recognize.return_value = {'matches': []}
        self.assertIsNone(await provider.recognize(Path('sample.wav')))
        for malformed in ({}, [], {'track': {'title': 'only'}}):
            client.recognize.return_value = malformed
            with self.assertRaisesRegex(RecognitionError, '^provider$'):
                await provider.recognize(Path('sample.wav'))
        client.recognize.side_effect = RuntimeError('private data')
        with self.assertRaisesRegex(RecognitionError, '^provider$'):
            await provider.recognize(Path('sample.wav'))

    async def test_unsafe_result_url_removed(self):
        client = NS(recognize=AsyncMock(return_value={'track': {'title': 'Title',
            'subtitle': 'Artist', 'url': 'https://www.shazam.com.evil.test/track/1'}}))
        self.assertEqual(await ShazamProvider(client=client).recognize(Path('sample.wav')), 'Artist — Title')

    async def test_shazam_cover_and_album_reach_delivery(self):
        art = 'https://is1-ssl.mzstatic.com/image/thumb/Music/test/400x400cc.jpg'
        client = NS(recognize=AsyncMock(return_value={'track': {'title': 'Title', 'subtitle': 'Artist',
            'images': {'coverart': art}, 'sections': [{'metadata': [{'title': 'Album', 'text': 'Album'}]}]}}))
        result = await ShazamProvider(client=client).recognize(Path('sample.wav'))
        self.assertEqual(result.artwork_url, art)
        self.assertEqual(result.album, 'Album')
        self.service.delivery = NS(request_recognized=AsyncMock())
        await self.service.deliver(message(), result)
        self.service.delivery.request_recognized.assert_awaited_with(123, 'Artist', 'Title', artwork_url=art, album='Album')

    async def test_shazam_cover_rejects_untrusted_hosts(self):
        from music_bot.chat_ui import safe_url
        for url in ('https://is1-ssl.mzstatic.com.evil.test/a.jpg', 'https://evil.mzstatic.com/a.jpg',
                    'https://user@is1-ssl.mzstatic.com/a.jpg', 'http://is1-ssl.mzstatic.com/a.jpg'):
            self.assertIsNone(safe_url(url, artwork=True))

    async def test_http_stream_and_endpoint(self):
        async def chunks(size):
            for chunk in (b'{"matches":', b' []}'):
                yield chunk
        response = NS(status=200, content=NS(iter_chunked=chunks))
        context = AsyncMock()
        context.__aenter__.return_value = response
        from unittest.mock import Mock
        session = NS(request=Mock(return_value=context))
        result = await ShazamHTTP(session).request('POST',
            'https://amp.shazam.com/discovery/v5/en-US/GB/web/-/tag/test')
        self.assertEqual(result, {'matches': []})
        url = session.request.call_args.args[1]
        self.assertTrue(url.startswith('https://cdn.shazam.com/'))
        self.assertIn('/iphone/-/', url)
        self.assertFalse(session.request.call_args.kwargs['allow_redirects'])
        response.status = 429
        with self.assertRaises(RecognitionError):
            await ShazamHTTP(session).request('POST', 'https://cdn.shazam.com/test')

    async def test_handlers_delegate_and_cancel(self):
        from music_bot.handlers import (audio_submission, recognize_command,
            recognize_media, text_submission, cancel)
        service = NS(enabled=True, submit=AsyncMock(), cancel=AsyncMock())
        workflow = NS(cancel=AsyncMock())
        msg = message(audio=media(), reply_to_message=None)
        service.submit.assert_not_awaited()
        await recognize_media(msg, recognition=service)
        await recognize_command(msg, recognition=service)
        service.submit.assert_awaited_with(msg, msg)
        msg.reply_to_message = message(voice=media())
        await recognize_command(msg, recognition=service)
        service.submit.assert_awaited_with(msg, msg.reply_to_message)
        msg.from_user.username, msg.from_user.full_name = 'test', 'Test'
        msg.from_user.language_code = 'en'
        msg.text = 'https://youtu.be/dQw4w9WgXcQ'
        await text_submission(msg, None, None, None, recognition=service)
        service.submit.assert_awaited_with(msg)
        await cancel(msg, workflow, recognition=service)
        service.cancel.assert_awaited_with(123)

    def test_urls(self):
        for url in ('https://youtu.be/dQw4w9WgXcQ', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                    'https://youtube.com/shorts/dQw4w9WgXcQ'):
            self.assertEqual(youtube_id(url), 'dQw4w9WgXcQ')
        for url in ('http://youtu.be/dQw4w9WgXcQ', 'https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ',
                    'https://user@youtu.be/dQw4w9WgXcQ', 'https://youtu.be:bad/id',
                    'https://127.0.0.1/a', 'file:///etc/passwd'):
            self.assertIsNone(youtube_id(url))

    def test_buffer_and_settings(self):
        with LimitedBuffer() as buffer, patch('music_bot.recognition.MAX_BYTES', 4):
            buffer.write(b'1234')
            with self.assertRaises(RecognitionError):
                buffer.write(b'5')
        with patch.dict('os.environ', {'RECOGNITION_ENABLED': 'false'}):
            self.assertFalse(RecognitionSettings.environment().enabled)
        with patch.dict('os.environ', {'RECOGNITION_ENABLED': 'wrong'}):
            with self.assertRaises(ConfigError):
                RecognitionSettings.environment()


if __name__ == '__main__':
    unittest.main()
