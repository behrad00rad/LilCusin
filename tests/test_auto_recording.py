import asyncio
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from sqlalchemy import select

from tests.support import ServiceTestCase
from music_bot.chat_service import ChatService
from music_bot.get_song import GetSong,FetchSettings
from music_bot.models import Track
from music_bot.fetch_models import AudioRequest,FetchJob,AudioSelection
from music_bot.providers.common import TrackCandidate
from music_bot.recording_fallback import automatic,automatic_match

VIDEO='4De_ERjvuUI'


class AutoRecordingTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await ChatService(self.database,None).ensure_user(self.user)
        async with self.database.write() as session:
            self.track=Track(artist='Joji',title='SLOW DANCING IN THE DARK',duration=231,metadata_source='itunes')
            session.add(self.track);await session.flush()
        self.row=TrackCandidate('SLOW DANCING IN THE DARK','Joji','youtube_music',duration=210,external_ids={'youtube':VIDEO})
        self.discovery=NS(search=AsyncMock(return_value=([self.row],False)))
        self.bot=NS(send_message=AsyncMock(return_value=NS(message_id=77)),edit_message_text=AsyncMock(),delete_message=AsyncMock(),
            me=AsyncMock(return_value=NS(username='LilCusinBot')),send_audio=AsyncMock(return_value=NS(message_id=88,audio=NS(file_id='fixture'))))
        async def audio(video,directory,alive):
            path=Path(directory)/'audio.m4a';path.write_bytes(b'fixture');return path
        self.fetcher=NS(search=AsyncMock(return_value=[]),fetch=AsyncMock(side_effect=audio),recording_search=self.discovery)
        self.delivery=GetSong(self.database,self.bot,FetchSettings(enabled=True),self.fetcher)
        self.delivery.root=Path(self.temp.name)/'fetch';self.delivery.root.mkdir()

    async def request(self,**kwargs):
        rid=await self.delivery.request(123,self.track.id,**kwargs)
        async with self.database.sessions() as session:
            req=await session.get(AudioRequest,rid)
            return req,await session.get(FetchJob,req.job_id)

    async def test_empty_strict_search_sends_matching_first_discovery_without_choice(self):
        req,job=await self.request()
        await self.delivery.execute(job.id)
        async with self.database.sessions() as session:
            saved=await session.get(FetchJob,job.id)
            self.assertEqual(saved.state,'queued');self.assertEqual(saved.video_id,VIDEO)
            self.assertEqual(saved.metadata_json['source_policy'],'automatic-first-v1')
        self.bot.send_message.assert_not_awaited()
        await self.delivery.execute(job.id)
        self.bot.send_audio.assert_awaited_once()
        self.discovery.search.assert_awaited_once()
        async with self.database.sessions() as session:
            saved=await session.get(AudioRequest,req.id)
            self.assertEqual(saved.state,'done')
            self.assertEqual(saved.canonical_metadata['source_id'],VIDEO)

    async def test_different_artist_or_version_requires_selection(self):
        self.discovery.search.return_value=([TrackCandidate('SLOW DANCING IN THE DARK (Cover)','Other Artist','youtube_music',duration=210,external_ids={'youtube':VIDEO})],False)
        req,job=await self.request()
        await self.delivery.execute(job.id)
        self.fetcher.fetch.assert_not_awaited()
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(FetchJob,job.id)).state,'choice')
            self.assertEqual((await session.get(AudioRequest,req.id)).state,'choice')

    async def test_cancel_during_discovery_never_downloads(self):
        req,job=await self.request()
        async def cancel(query):
            async with self.database.write() as session:
                (await session.get(AudioRequest,req.id)).state='cancelled'
            return [self.row],False
        self.discovery.search.side_effect=cancel
        self.assertFalse(await automatic(self.delivery,job.id))
        self.fetcher.fetch.assert_not_awaited()

    async def test_explicit_versions_and_outage_do_not_loop(self):
        req,job=await self.request(other_versions=True)
        self.assertFalse(await automatic(self.delivery,job.id))
        self.discovery.search.assert_not_awaited()
        async with self.database.write() as session:
            saved=await session.get(FetchJob,job.id)
            saved.metadata_json={}
        self.discovery.search.side_effect=TimeoutError()
        self.assertFalse(await automatic(self.delivery,job.id))
        self.assertFalse(await automatic(self.delivery,job.id))
        self.discovery.search.assert_awaited_once()

    async def test_new_rejection_during_lookup_is_respected(self):
        req,job=await self.request()
        async def reject(query):
            async with self.database.write() as session:
                session.add(AudioSelection(user_id=req.user_id,track_id=self.track.id,rejected_ids=[VIDEO]))
            return [self.row],False
        self.discovery.search.side_effect=reject
        self.assertFalse(await automatic(self.delivery,job.id))
        self.fetcher.fetch.assert_not_awaited()

    async def test_daily_presentation_metadata_is_preserved(self):
        daily={'day':'2026-10-28','recommendation':{'score':1,'reason':'fixture','sources':['fixture']}}
        req,job=await self.request(learn=False,daily_pick=daily)
        self.assertTrue(await automatic(self.delivery,job.id))
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(AudioRequest,req.id)).canonical_metadata['_daily_pick'],daily)

    async def test_match_allows_video_packaging_but_not_cover_or_large_duration_change(self):
        row={'artist':'Joji','title':'SLOW DANCING IN THE DARK','duration':210,'version':['music_video']}
        self.assertTrue(automatic_match(self.track,row))
        self.assertFalse(automatic_match(self.track,{**row,'version':['cover']}))
        self.assertFalse(automatic_match(self.track,{**row,'duration':500}))
        self.assertFalse(automatic_match(self.track,{**row,'artist':'Other Artist'}))
