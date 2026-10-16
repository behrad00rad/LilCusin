import asyncio
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

from music_bot.get_song import FetchSettings
from music_bot.lilbro_fetch import LilBroFetcher, LilBroInbound, Pending, LILBRO_ID, youtube_id
from music_bot.youtube_fetch import FetchError

VIDEO = 'abcdefghijk'


def message(**values):
    data = dict(from_user=NS(id=LILBRO_ID, is_bot=True), chat=NS(id=LILBRO_ID, type='private'),
        date=datetime.now(timezone.utc), message_id=12, reply_to_message=None,
        caption='https://www.youtube.com/watch?v=' + VIDEO, text=None, entities=[],
        caption_entities=[], video=NS(file_id='private-file', file_size=5, mime_type='video/mp4'),
        audio=None, document=None, has_protected_content=False)
    return NS(**(data | values))


class LilBroTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.settings = FetchSettings(timeout=1, max_bytes=1000, disk_bytes=3000)
        self.bot = NS(send_message=AsyncMock(return_value=NS(message_id=10)), get_file=AsyncMock(
            return_value=NS(file_path='private-path')), token='never-log-this', session=NS(
                api=NS(file_url=lambda token, path: 'private-file-url')))
        async def stream(*args, **kwargs):
            yield b'video'
        self.bot.session.stream_content = stream
        self.fetcher = LilBroFetcher(self.settings, self.bot)
        self.alive = AsyncMock(return_value=True)
        self.persist = AsyncMock()

    def tearDown(self):
        self.temp.cleanup()

    async def test_only_pinned_bot_private_chat_is_accepted(self):
        self.fetcher.pending = Pending(VIDEO)
        for update in [message(from_user=NS(id=99,is_bot=True)), message(chat=NS(id=-1,type='group')),
                       message(from_user=NS(id=LILBRO_ID,is_bot=False))]:
            self.assertFalse(await self.fetcher.accept(update))
        self.assertTrue(await self.fetcher.accept(message()))
        self.assertEqual(self.fetcher.pending.messages.qsize(), 1)
        await self.fetcher.accept(message(date=datetime.now(timezone.utc)-timedelta(hours=1)))
        await self.fetcher.accept(message(has_protected_content=True))
        self.assertEqual(self.fetcher.pending.messages.qsize(), 1)

    async def test_reply_or_exact_source_id_required(self):
        pending = Pending(VIDEO, request_id=10)
        self.assertTrue(self.fetcher.correlated(message(), pending))
        self.assertFalse(self.fetcher.correlated(message(caption='https://youtu.be/otherID1234'),pending))
        self.assertFalse(self.fetcher.correlated(message(reply_to_message=NS(message_id=9)),pending))
        self.assertTrue(self.fetcher.correlated(message(caption=None,reply_to_message=NS(message_id=10)),pending))
        self.assertFalse(self.fetcher.correlated(message(message_id=9),pending))
        self.assertIsNone(youtube_id('https://youtube.com.evil/watch?v='+VIDEO))
        self.assertIsNone(youtube_id('https://youtube.com@evil/watch?v='+VIDEO))

    async def test_fetch_sends_link_once_downloads_and_cleans_source(self):
        async def send(*args, **kwargs):
            await self.fetcher.accept(message())
            return NS(message_id=10)
        self.bot.send_message.side_effect = send
        result=self.folder/'audio.m4a'
        async def extract(*args):
            result.write_bytes(b'audio')
            return result
        self.fetcher.extract=AsyncMock(side_effect=extract)
        path=await self.fetcher.fetch_selected(VIDEO,self.folder,self.alive,{'duration':130},self.persist)
        self.assertEqual(path,result)
        self.assertFalse((self.folder/'input.media').exists())
        self.assertIsNone(self.fetcher.pending)
        self.bot.send_message.assert_awaited_once()
        self.assertEqual(self.bot.send_message.call_args.args[1],'https://www.youtube.com/watch?v='+VIDEO)

    async def test_restart_never_blindly_resends_ambiguous_source_request(self):
        with self.assertRaises(FetchError):
            await self.fetcher.fetch_selected(VIDEO,self.folder,self.alive,{'lilbro_request_started':True},self.persist)
        self.bot.send_message.assert_not_awaited()

    async def test_oversized_media_rejected_before_download(self):
        async def send(*args,**kwargs):
            await self.fetcher.accept(message(video=NS(file_id='x',file_size=99999999,mime_type='video/mp4')))
            return NS(message_id=10)
        self.bot.send_message.side_effect=send
        with self.assertRaises(FetchError):
            await self.fetcher.fetch_selected(VIDEO,self.folder,self.alive,{},self.persist)
        self.bot.get_file.assert_not_awaited()
        self.assertEqual(list(self.folder.iterdir()),[])

    async def test_timeout_has_bounded_send_and_no_pending_listener(self):
        self.fetcher.settings=replace(self.settings,timeout=.03)
        with self.assertRaises(FetchError):
            await self.fetcher.fetch_selected(VIDEO,self.folder,self.alive,{},self.persist)
        self.bot.send_message.assert_awaited_once()
        self.assertIsNone(self.fetcher.pending)

    async def test_cancelled_job_does_not_send(self):
        self.alive.return_value=False
        with self.assertRaises(FetchError):
            await self.fetcher.fetch_selected(VIDEO,self.folder,self.alive,{},self.persist)
        self.bot.send_message.assert_not_awaited()

    async def test_aac_is_remuxed_without_reencoding(self):
        self.fetcher.probe=AsyncMock(side_effect=[(130,[{'codec_type':'video','codec_name':'h264'},
            {'codec_type':'audio','codec_name':'aac'}]),(130,[{'codec_type':'audio','codec_name':'aac'}])])
        async def process(args,*rest,**kw):
            Path(args[-1]).write_bytes(b'audio')
        self.fetcher.process=AsyncMock(side_effect=process)
        path=await self.fetcher.extract(self.folder/'input.media',self.folder,self.alive,130)
        self.assertEqual(path.suffix,'.m4a')
        self.assertIn('copy',self.fetcher.process.call_args.args[0])
        self.assertNotIn('libmp3lame',self.fetcher.process.call_args.args[0])

    async def test_other_audio_is_converted_and_incomplete_output_rejected(self):
        self.fetcher.probe=AsyncMock(side_effect=[(130,[{'codec_type':'audio','codec_name':'opus'}]),
            (110,[{'codec_type':'audio','codec_name':'mp3'}])])
        async def process(args,*rest,**kw):Path(args[-1]).write_bytes(b'audio')
        self.fetcher.process=AsyncMock(side_effect=process)
        with self.assertRaises(FetchError):
            await self.fetcher.extract(self.folder/'input.media',self.folder,self.alive,130)
        self.assertIn('libmp3lame',self.fetcher.process.call_args.args[0])
        self.assertFalse((self.folder/'audio.mp3').exists())

    async def test_different_duration_or_silent_video_rejected(self):
        for duration,streams in [(200,[{'codec_type':'audio','codec_name':'aac'}]),
                                 (130,[{'codec_type':'video','codec_name':'h264'}])]:
            self.fetcher.probe=AsyncMock(return_value=(duration,streams))
            with self.assertRaises(FetchError):
                await self.fetcher.extract(self.folder/'input.media',self.folder,self.alive,130)

    async def test_flat_search_warns_about_suspect_saved_duration(self):
        self.fetcher.process=AsyncMock(return_value=json.dumps({'entries':[dict(id=VIDEO,
            track='DNA.',title='Kendrick Lamar - DNA.',artist='Kendrick Lamar',duration=186)]}).encode())
        rows=await self.fetcher.search(NS(artist='Kendrick Lamar',title='DNA.',duration=116),self.folder,self.alive)
        self.assertTrue(rows[0]['duration_mismatch'])
        self.assertFalse(rows[0]['exact'])
        self.assertIn('--flat-playlist',self.fetcher.process.call_args_list[0].args[0])

    async def test_provider_update_never_reaches_submission_handlers(self):
        middleware=LilBroInbound(NS(fetcher=self.fetcher))
        handler=AsyncMock()
        await middleware(handler,message(),{})
        handler.assert_not_awaited()
        other=message(from_user=NS(id=123,is_bot=False))
        await middleware(handler,other,{})
        handler.assert_awaited_once()
