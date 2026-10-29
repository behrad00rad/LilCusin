import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
from datetime import timedelta
from sqlalchemy import select
from tests.support import ServiceTestCase
from music_bot.get_song import GetSong,FetchSettings
from music_bot.models import Track,utc_now
from music_bot.fetch_models import AudioRequest,FetchJob,AudioSelection,AudioDelivery
from music_bot.providers.common import TrackCandidate
from music_bot.recording_fallback import start
from music_bot.workflow import FlowError

VIDEO='4De_ERjvuUI'
class RecordingFallbackTests(ServiceTestCase):
 async def asyncSetUp(self):
  await super().asyncSetUp()
  from music_bot.chat_service import ChatService
  await ChatService(self.database,None).ensure_user(self.user)
  async with self.database.write() as s:
   t=Track(artist='Joji',title='SLOW DANCING IN THE DARK',display_artist='Joji',display_title='SLOW DANCING IN THE DARK',duration=231,metadata_source='itunes')
   s.add(t);await s.flush();self.track_id=t.id
  self.bot=NS(edit_message_text=AsyncMock(),send_message=AsyncMock(return_value=NS(message_id=77)),delete_message=AsyncMock(),me=AsyncMock(return_value=NS(username='TestMusicBot')),send_audio=AsyncMock(return_value=NS(message_id=88,audio=NS(file_id='fixture-file'))))
  async def audio(video,folder,alive):
   path=Path(folder)/'audio.m4a';path.write_bytes(b'fixture audio');return path
  self.row=TrackCandidate('SLOW DANCING IN THE DARK','Joji','youtube_music',duration=210,external_ids={'youtube':VIDEO})
  self.discovery=NS(search=AsyncMock(return_value=([self.row],False)))
  self.fetcher=NS(search=AsyncMock(return_value=[]),fetch=AsyncMock(side_effect=audio),recording_search=self.discovery)
  self.service=GetSong(self.database,self.bot,FetchSettings(enabled=True),self.fetcher)
  self.service.root=Path(self.temp.name)/'fetch';self.service.root.mkdir()
 async def failed(self):
  rid=await self.service.request(123,self.track_id)
  async with self.database.write() as s:
   req=await s.get(AudioRequest,rid);req.status_message_id=77;job=req.job_id
  with self.assertLogs('music_bot',level='WARNING'),patch('music_bot.recording_fallback.automatic',AsyncMock(return_value=False)):
   await self.service.execute(job)
  return rid
 async def request_row(self,rid):
  async with self.database.sessions() as s:
   req=await s.get(AudioRequest,rid);job=await s.get(FetchJob,req.job_id)
  return req,job
 async def test_automatic_success_does_not_offer_or_use_discovery(self):
  self.fetcher.search.return_value=[dict(id=VIDEO,title='SLOW DANCING IN THE DARK',artist='Joji',duration=231,exact=True,score=1)]
  rid=await self.service.request(123,self.track_id);req,job=await self.request_row(rid)
  with patch('music_bot.get_song.prepare_artwork',AsyncMock(return_value=(None,None))):await self.service.execute(job.id)
  self.assertEqual((await self.request_row(rid))[0].state,'done');self.discovery.search.assert_not_awaited();self.fetcher.fetch.assert_awaited_once()
 async def test_failure_offers_owner_bound_action_then_explicit_selected_source_delivers(self):
  rid=await self.failed();self.fetcher.fetch.assert_not_awaited()
  keyboard=self.bot.edit_message_text.await_args.kwargs['reply_markup']
  self.assertTrue(any(b.callback_data=='pickreq:'+rid for row in keyboard.inline_keyboard for b in row))
  await start(self.service,123,rid,77);req,job=await self.request_row(rid)
  self.assertEqual(req.state,'choice');self.assertEqual(job.candidates[0]['id'],VIDEO);self.fetcher.fetch.assert_not_awaited()
  await self.service.choose(123,rid,77,0);req,job=await self.request_row(rid)
  with patch('music_bot.get_song.prepare_artwork',AsyncMock(return_value=(None,None))):await self.service.execute(job.id)
  self.fetcher.fetch.assert_awaited_once();self.assertEqual(self.fetcher.fetch.await_args.args[0],VIDEO)
  self.assertEqual(self.bot.send_audio.await_args.kwargs['performer'],'Joji')
  async with self.database.sessions() as s:
   delivery=await s.scalar(select(AudioDelivery));track=await s.get(Track,self.track_id)
   self.assertEqual(delivery.video_id,VIDEO);self.assertEqual(delivery.send_args['title'],'SLOW DANCING IN THE DARK');self.assertEqual(track.duration,231)
  with self.assertRaises(FlowError):await self.service.choose(123,rid,77,0)
  self.assertEqual(self.fetcher.search.await_count,1)
 async def test_empty_and_outage_are_distinct_and_retryable(self):
  for failed in [False,True]:
   rid=await self.failed();self.discovery.search.return_value=([],failed)
   await start(self.service,123,rid,77);req,job=await self.request_row(rid)
   self.assertEqual(req.state,'failed');self.assertEqual(job.metadata_json['failure_reason'],'recording_discovery_unavailable' if failed else 'recording_discovery_empty')
  self.fetcher.fetch.assert_not_awaited()
 async def test_wrong_owner_message_and_expiry_are_rejected(self):
  rid=await self.failed()
  for owner,mid in [(999,77),(123,78)]:
   with self.assertRaises(FlowError):await start(self.service,owner,rid,mid)
  async with self.database.write() as s:(await s.get(AudioRequest,rid)).created_at=utc_now()-timedelta(minutes=31)
  with self.assertRaises(FlowError):await start(self.service,123,rid,77)
  self.discovery.search.assert_not_awaited()
 async def test_cancel_and_repeated_taps_cannot_start_another_lookup_or_download(self):
  rid=await self.failed();entered=asyncio.Event();release=asyncio.Event()
  async def search(query):entered.set();await release.wait();return [self.row],False
  self.discovery.search.side_effect=search
  task=asyncio.create_task(start(self.service,123,rid,77));await entered.wait()
  with self.assertRaises(FlowError):await start(self.service,123,rid,77)
  await self.service.cancel_request(123,rid,77);release.set();await task
  self.assertEqual((await self.request_row(rid))[0].state,'cancelled');self.discovery.search.assert_awaited_once();self.fetcher.fetch.assert_not_awaited()
 async def test_raw_upload_uses_proven_catalogue_fields_not_channel(self):
  rid=await self.failed();self.discovery.search.return_value=([TrackCandidate('Joji - SLOW DANCING IN THE DARK (Video)','Random Channel','youtube_recording',duration=210,external_ids={'youtube':VIDEO})],False)
  await start(self.service,123,rid,77);await self.service.choose(123,rid,77,0)
  req,job=await self.request_row(rid);self.assertEqual(req.canonical_metadata['artist'],'Joji');self.assertEqual(req.canonical_metadata['source_id'],VIDEO)
 async def test_prompt_ack_failure_never_downloads(self):
  from aiogram.exceptions import TelegramNetworkError
  rid=await self.failed();self.bot.edit_message_text.side_effect=TelegramNetworkError(method=NS(),message='fixture outage')
  await start(self.service,123,rid,77)
  self.assertEqual((await self.request_row(rid))[0].state,'uncertain');self.fetcher.fetch.assert_not_awaited()

 async def test_expiry_during_lookup_is_terminal_and_never_downloads(self):
  rid=await self.failed()
  async def expire(query):
   async with self.database.write() as session:
    (await session.get(AudioRequest,rid)).created_at=utc_now()-timedelta(minutes=31)
   return [self.row],False
  self.discovery.search.side_effect=expire
  await start(self.service,123,rid,77)
  self.assertEqual((await self.request_row(rid))[0].state,'expired');self.fetcher.fetch.assert_not_awaited()


import unittest
class StrictMatchingRegressionTests(unittest.TestCase):
 def test_duration_mismatch_stays_rejected_in_automatic_matching(self):
  from music_bot.recording_resolver import RecordingResolver
  resolver=RecordingResolver(None)
  row=dict(id=VIDEO,artist='Artist',track='Song',title='Song',duration=210)
  track=NS(artist='Artist',title='Song',duration=231)
  self.assertEqual(resolver.rank(track,[row],[],900,structured=True),[])
  track.duration=210
  self.assertEqual(resolver.rank(track,[row],[],900,structured=True)[0]['id'],VIDEO)
