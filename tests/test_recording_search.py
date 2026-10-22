import asyncio
from contextlib import redirect_stdout
import io
import json
import sys
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from music_bot.recording_search import MUSIC_SEARCH, RecordingSearch, recordings, merge_recordings
from music_bot.fetch_models import AudioRequest, AudioSelection, FetchJob
from music_bot.get_song import FetchSettings, GetSong
from music_bot.models import IdentificationFlow, utc_now
from music_bot.providers.common import TrackCandidate
from music_bot.workflow import FlowError
from tests.support import ServiceTestCase

VIDEO = 'GEaFdwO9YoA'
OTHER = 'abcdefghijk'
ENTRY = dict(videoId=VIDEO, title='Starting Over', resultType='song',
             artists=[{'name':'LSD and the Search for God'}], duration_seconds=272)
CANDIDATE = recordings([ENTRY])[0]


class RecordingProviderTests(unittest.IsolatedAsyncioTestCase):
    def test_music_client_searches_songs_and_videos_including_upload_only_choices(self):
        from unittest.mock import Mock
        for query, first in [('prayer kendick','song'),('Navan live Montreal','video')]:
            client=Mock()
            client.search.side_effect=[[{**ENTRY,'resultType':'song'}],[{**ENTRY,'videoId':OTHER,'resultType':'video'}]]
            output=io.StringIO()
            with patch.dict(sys.modules,{'ytmusicapi':NS(YTMusic=lambda:client)}),patch.object(sys,'argv',['search',query]),redirect_stdout(output):
                exec(compile(MUSIC_SEARCH,'<music-search>','exec'),{})
            rows=json.loads(output.getvalue())
            self.assertEqual(rows[0]['resultType'],first)
            self.assertEqual(len(rows),2)
            self.assertEqual([c.kwargs['filter'] for c in client.search.call_args_list],['songs','videos'])
            self.assertTrue(all(c.kwargs['ignore_spelling'] is False for c in client.search.call_args_list))

    def test_structured_metadata_and_distinct_versions_keep_provider_order(self):
        rows = recordings([ENTRY, ENTRY, {**ENTRY,'videoId':OTHER,'duration_seconds':220}])
        self.assertEqual([r.external_ids['youtube'] for r in rows],[VIDEO,OTHER])
        self.assertEqual(rows[0].artist,'LSD and the Search for God')
        self.assertEqual(rows[0].duration,272)

    def test_invalid_unavailable_and_oversized_records_are_not_choices(self):
        for fields in [dict(videoId='../bad'),dict(isAvailable=False),dict(duration_seconds=901),
                       dict(duration_seconds=True),dict(duration_seconds=float('nan')),
                       dict(resultType='album'),dict(artists=[]),dict(artists=1),dict(title=''),dict(is_live=True)]:
            with self.subTest(fields=fields):
                self.assertFalse(recordings([{**ENTRY,**fields}]))

    def test_video_duration_and_upload_metadata(self):
        row=recordings([{**ENTRY,'duration_seconds':None,'duration':'4:32','resultType':'video'}])[0]
        self.assertEqual(row.duration,272)
        upload=recordings([dict(id=VIDEO,title='Live medley',uploader='Navan',duration=272)],music=False)[0]
        self.assertEqual(upload.source,'youtube_recording')

    async def test_spelling_and_provider_order_are_not_locally_filtered(self):
        client=RecordingSearch()
        client.process=AsyncMock(return_value=[ENTRY])
        rows,failed=await client.search('prayer kendick')
        self.assertEqual([(r.title,r.artist,r.external_ids) for r in rows],[(CANDIDATE.title,CANDIDATE.artist,CANDIDATE.external_ids)])
        self.assertFalse(failed)
        self.assertEqual(client.process.await_args_list[0].args[0][-1],'prayer kendick')
        self.assertIn('ignore_spelling=False',client.process.await_args_list[0].args[0][-2])

    async def test_empty_or_unavailable_music_uses_regular_youtube_without_catalogue(self):
        client=RecordingSearch()
        for first in [[],None,{'malformed':True}]:
            client.process=AsyncMock(side_effect=[first,dict(entries=[dict(id=VIDEO,title='Prayer unreleased',
                                                       uploader='Uploader',duration=220)])])
            rows,failed=await client.search('Prayer Kendrick '+str(first))
            self.assertEqual(rows[0].external_ids['youtube'],VIDEO)
            self.assertEqual(rows[0].source,'youtube_recording')
            self.assertFalse(failed)

    async def test_short_query_supplements_nonempty_music_and_exposes_popular_exact_title(self):
        primary=[{**ENTRY,'title':'Hello There'}]
        uploads=[dict(id=f'video{i:06d}',title=f'Hello other clip {i}',uploader='Other',duration=200,view_count=999999999) for i in range(15)]
        uploads.append(dict(id=VIDEO,title='Pop Smoke - Hello (Official) ft. A Boogie wit da Hoodie',uploader='POP SMOKE',duration=192,view_count=218033121))
        client=RecordingSearch();client.process=AsyncMock(side_effect=[primary,{'entries':uploads}])
        rows,failed=await client.search('hello')
        self.assertFalse(failed)
        self.assertIn(VIDEO,[row.external_ids['youtube'] for row in rows[:5]])
        self.assertEqual(rows[0].youtube_views,218033121)
        self.assertEqual(client.process.await_args_list[1].args[0][-1],'ytsearch20:hello')

    async def test_supplement_failure_keeps_successful_music_results(self):
        client=RecordingSearch();client.process=AsyncMock(side_effect=[[ENTRY],None])
        rows,failed=await client.search('starting over')
        self.assertEqual([(r.title,r.artist,r.external_ids) for r in rows],[(CANDIDATE.title,CANDIDATE.artist,CANDIDATE.external_ids)]);self.assertFalse(failed)

    async def test_long_query_avoids_extra_successful_provider_call(self):
        client=RecordingSearch();client.process=AsyncMock(return_value=[ENTRY])
        await client.search('starting over lsd live recording')
        self.assertEqual(client.process.await_count,1)

    def test_same_video_retains_music_identity_and_adds_only_numeric_upload_views(self):
        upload=recordings([dict(id=VIDEO,title='Uploader credit - Starting Over',uploader='Uploader',duration=272,view_count=12345)],music=False)[0]
        rows=merge_recordings('starting over',[CANDIDATE],[upload])
        self.assertEqual(len(rows),1);self.assertEqual(rows[0].artist,CANDIDATE.artist)
        self.assertEqual(rows[0].title,CANDIDATE.title);self.assertEqual(rows[0].youtube_views,12345)
        for value in [True,'3.5B',-1]:
            row=recordings([dict(id=VIDEO,title='Song',uploader='Artist',duration=200,view_count=value)],music=False)[0]
            self.assertIsNone(row.youtube_views)

    async def test_cache_is_bounded_detached_and_expires(self):
        now=[0]
        client=RecordingSearch(clock=lambda:now[0],ttl=5,capacity=1)
        client.process=AsyncMock(return_value=[ENTRY])
        rows,_=await client.search('one');rows[0].external_ids.clear()
        again,_=await client.search('ONE')
        self.assertEqual(again[0].external_ids['youtube'],VIDEO)
        self.assertEqual(client.process.await_count,2)
        await client.search('two');self.assertEqual(len(client.cache),1)
        now[0]=10;await client.search('two');self.assertEqual(client.process.await_count,6)

    async def test_cancel_kills_and_reaps_provider_child(self):
        started=asyncio.Event()
        async def read(*args):
            started.set();await asyncio.Event().wait()
        child=NS(stdout=NS(read=read),returncode=None,kill=lambda:setattr(child,'returncode',-9),wait=AsyncMock())
        client=RecordingSearch()
        with patch('asyncio.create_subprocess_exec',AsyncMock(return_value=child)):
            task=asyncio.create_task(client.process(['fake']))
            await started.wait();task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(child.returncode,-9)
        child.wait.assert_awaited()

    async def test_provider_concurrency_is_bounded(self):
        active=peak=0
        async def process(args):
            nonlocal active,peak
            active+=1;peak=max(peak,active)
            await asyncio.sleep(.01);active-=1;return [ENTRY]
        client=RecordingSearch(concurrency=2);client.process=process
        await asyncio.gather(*(client.search(str(i)) for i in range(6)))
        self.assertEqual(peak,2)


class RecordingFlowTests(ServiceTestCase):
    async def search(self, query='prayer kendick', rows=None):
        self.workflow.recording_search=NS(search=AsyncMock(return_value=(rows or [CANDIDATE],False)))
        saved=await self.submissions.submit_search(self.user,query)
        result=await self.workflow.start(saved.id,123,fast=True)
        return saved,result

    async def test_recordings_bypass_catalogue_require_choice_and_do_not_rate(self):
        _,result=await self.search()
        self.assertEqual(result.kind,'candidates')
        self.assertIsNone(result.search_key)
        self.providers.call.assert_not_awaited()
        self.workflow.recording_search.search.assert_awaited_once_with('prayer kendick')

    async def test_selected_id_survives_restart_and_get_song_never_researches(self):
        saved,result=await self.search()
        chosen=await self.workflow.select(saved.id,123,result.revision,0)
        async def audio(video,directory,alive):
            path=Path(directory)/'source.m4a';path.write_bytes(b'fixture audio');return path
        fetcher=NS(search=AsyncMock(),fetch=AsyncMock(side_effect=audio))
        bot=NS(send_audio=AsyncMock(return_value=NS(audio=NS(file_id='fixture-file'),message_id=8)),
               edit_message_text=AsyncMock(),send_message=AsyncMock(),delete_message=AsyncMock())
        service=GetSong(self.database,bot,FetchSettings(enabled=True),fetcher)
        service.root=Path(self.temp.name)/'audio';service.root.mkdir()
        request=await service.request(123,chosen.track_id)
        async with self.database.sessions() as session:
            row=await session.get(AudioRequest,request)
            job=await session.get(FetchJob,row.job_id)
            self.assertEqual(job.video_id,VIDEO)
        with patch('music_bot.get_song.prepare_artwork',AsyncMock(return_value=(None,None))):
            await service.execute(job.id)
        fetcher.search.assert_not_awaited()
        self.assertEqual(fetcher.fetch.await_args.args[0],VIDEO)
        bot.send_audio.assert_awaited_once()
        async with self.database.sessions() as session:
            self.assertEqual((await session.get(AudioRequest,request)).state,'done')

    async def test_wrong_owner_expired_and_invalid_selection_cannot_pin_recording(self):
        saved,result=await self.search()
        with self.assertRaises(FlowError):
            await self.workflow.select(saved.id,999,result.revision,0)
        from datetime import timedelta
        async with self.database.write() as s:
            flow=await s.get(IdentificationFlow,saved.id);flow.expires_at=utc_now()-timedelta(seconds=1)
        with self.assertRaises(FlowError):
            await self.workflow.select(saved.id,123,result.revision,0)
        async with self.database.sessions() as s:
            self.assertFalse((await s.scalars(select(AudioSelection))).all())

    async def test_new_explicit_choice_supersedes_own_queued_request(self):
        saved,result=await self.search()
        chosen=await self.workflow.select(saved.id,123,result.revision,0)
        service=GetSong(self.database,NS(),FetchSettings(enabled=True),NS())
        first=await service.request(123,chosen.track_id)
        saved,result=await self.search(rows=[replace(CANDIDATE,external_ids={'youtube':OTHER})])
        await self.workflow.select(saved.id,123,result.revision,0)
        second=await service.request(123,chosen.track_id)
        async with self.database.sessions() as s:
            self.assertEqual((await s.get(AudioRequest,first)).state,'cancelled')
            self.assertEqual((await s.get(FetchJob,(await s.get(AudioRequest,second)).job_id)).video_id,OTHER)

    async def test_provider_outage_still_uses_existing_catalogue_recovery(self):
        self.workflow.recording_search=NS(search=AsyncMock(return_value=([],True)))
        self.workflow.search_chat_title=AsyncMock(return_value=([replace(CANDIDATE,source='lastfm',external_ids={})],False))
        saved=await self.submissions.submit_search(self.user,'song')
        result=await self.workflow.start(saved.id,123,fast=True)
        self.assertEqual(result.kind,'candidates')
        self.workflow.search_chat_title.assert_awaited_once()
