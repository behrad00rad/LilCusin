import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from sqlalchemy import create_engine, select
from music_bot.recording_metadata import prepare_results, snapshot_metadata, telegram_fields, RecordingMetadata
from music_bot.providers.common import TrackCandidate
from music_bot.fetch_models import AudioSelection, AudioRequest, AudioDelivery, FetchJob
from music_bot.models import Track
from music_bot.get_song import GetSong, FetchSettings
from music_bot.migrations import migrate
from tests.support import ServiceTestCase

VIDEO='Egl_zDY4lw0'

class MetadataPersistenceTests(unittest.TestCase):
 def test_additive_migration_preserves_legacy_rows_and_is_idempotent(self):
  engine=create_engine('sqlite://')
  with engine.begin() as c:
   for table in ['audio_selections','audio_requests','audio_deliveries']:
    c.exec_driver_sql(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)')
    c.exec_driver_sql(f'INSERT INTO {table} (id) VALUES (7)')
   migrate(c);migrate(c)
   for table,column in [('audio_selections','canonical_metadata'),('audio_requests','canonical_metadata'),('audio_deliveries','send_args')]:
    self.assertEqual(c.exec_driver_sql(f'SELECT id,{column} FROM {table}').one(),(7,'{}'))
  engine.dispose()

 def test_unknown_and_label_artists_are_omitted_and_snapshot_binds_source(self):
  for artist in ['', 'Unknown artist', 'Unverified', 'Caltex Records', 'TaranehEnterprise']:
   self.assertEqual(telegram_fields(RecordingMetadata('Sogand',artist)),{'title':'Sogand'})
  snapshot={'version':1,'artist':'Viguen','title':'Sogand','source_id':VIDEO}
  self.assertIsNone(snapshot_metadata(snapshot,'another0000'))
  self.assertEqual(snapshot_metadata(snapshot,VIDEO),RecordingMetadata('Sogand','Viguen'))

class SelectedMetadataTests(ServiceTestCase):
 async def test_selected_metadata_survives_restart_without_reparsing_and_send_args_persist(self):
  raw=TrackCandidate('Viguen-Sogand ویگن ـ سوگند','TaranehEnterprise','youtube_recording',duration=255,external_ids={'youtube':VIDEO},album='Album')
  rows=prepare_results('Viguen Sogand',[raw],searched_artist='Viguen')
  self.workflow.recording_search=NS(search=AsyncMock(return_value=(rows,False)))
  submission=await self.submissions.submit_search(self.user,'Viguen Sogand')
  result=await self.workflow.start(submission.id,123,fast=True)
  chosen=await self.workflow.select(submission.id,123,result.revision,0)
  fetcher=NS(search=AsyncMock(),fetch=AsyncMock())
  bot=NS(send_audio=AsyncMock(return_value=NS(audio=NS(file_id='cached-file'),message_id=8)),me=AsyncMock(return_value=NS(username='TestMusicBot')))
  service=GetSong(self.database,bot,FetchSettings(enabled=True),fetcher)
  request_id=await service.request(123,chosen.track_id)
  async with self.database.write() as s:
   selection=await s.scalar(select(AudioSelection))
   self.assertEqual((selection.canonical_metadata['artist'],selection.canonical_metadata['title']),('Viguen','Sogand'))
   track=await s.get(Track,chosen.track_id)
   original_identity=(track.artist,track.title)
   track.display_artist,track.display_title='Bad Channel','Later upload packaging'
   # Changing a later preference must not change this already queued request.
   selection.canonical_metadata={**selection.canonical_metadata,'title':'Different selection'}
  service=GetSong(self.database,bot,FetchSettings(enabled=True),fetcher)
  async with self.database.sessions() as s:
   req=await s.get(AudioRequest,request_id);job=await s.get(FetchJob,req.job_id);track=await s.get(Track,chosen.track_id)
  await service.send(req,123,job,track,'cached-file')
  self.assertEqual(bot.send_audio.await_args.kwargs['title'],'Sogand')
  self.assertEqual(bot.send_audio.await_args.kwargs['performer'],'Viguen')
  async with self.database.sessions() as s:
   delivery=await s.scalar(select(AudioDelivery))
   self.assertEqual(delivery.send_args,{'title':'Sogand','performer':'Viguen'})
   self.assertEqual(delivery.video_id,VIDEO)
   current=await s.get(Track,chosen.track_id)
   self.assertEqual((current.artist,current.title),original_identity)
  fetcher.search.assert_not_awaited();fetcher.fetch.assert_not_awaited()

 async def test_local_file_tags_match_canonical_send_and_clean_cache_reuses_without_fetch(self):
  import shutil,subprocess
  from mutagen.mp4 import MP4
  from music_bot.fetch_models import AudioSource
  raw=TrackCandidate('Viguen-Sogand ویگن ـ سوگند','TaranehEnterprise','youtube_recording',duration=255,external_ids={'youtube':VIDEO},album='Album')
  rows=prepare_results('Viguen Sogand',[raw],searched_artist='Viguen')
  self.workflow.recording_search=NS(search=AsyncMock(return_value=(rows,False)))
  sub=await self.submissions.submit_search(self.user,'Viguen Sogand')
  result=await self.workflow.start(sub.id,123,fast=True)
  chosen=await self.workflow.select(sub.id,123,result.revision,0)
  fetcher=NS(search=AsyncMock(),fetch=AsyncMock(),settings=NS(max_bytes=1000000,disk_bytes=3000000))
  bot=NS(send_audio=AsyncMock(return_value=NS(audio=NS(file_id='clean-file'),message_id=8)),me=AsyncMock(return_value=NS(username='TestMusicBot')))
  service=GetSong(self.database,bot,FetchSettings(enabled=True),fetcher)
  rid=await service.request(123,chosen.track_id)
  async with self.database.write() as session:
   req=await session.get(AudioRequest,rid);job=await session.get(FetchJob,req.job_id);track=await session.get(Track,chosen.track_id)
   session.add(AudioSource(track_id=track.id,video_id=VIDEO,fetch_metadata={}))
  path=Path(self.temp.name)/'source.m4a'
  executable=shutil.which('ffmpeg')
  if not executable:
   from imageio_ffmpeg import get_ffmpeg_exe
   executable=get_ffmpeg_exe()
  subprocess.run([executable,'-nostdin','-v','error','-f','lavfi','-i','anullsrc=r=8000:cl=mono','-t','0.05','-c:a','aac','-y',str(path)],check=True,capture_output=True,timeout=15)
  await service.deliver(job,track,path)
  tags=MP4(path);self.assertEqual((tags['\xa9nam'],tags['\xa9ART'],tags['\xa9alb']),(['Sogand'],['Viguen'],['Album']))
  self.assertEqual((bot.send_audio.await_args.kwargs['title'],bot.send_audio.await_args.kwargs['performer']),('Sogand','Viguen'))
  second=await service.request(123,track.id)
  await service.cached_request(123,second)
  self.assertEqual(bot.send_audio.await_count,2)
  self.assertEqual(bot.send_audio.await_args.kwargs['audio'],'clean-file')
  fetcher.search.assert_not_awaited();fetcher.fetch.assert_not_awaited()
