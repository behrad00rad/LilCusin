import asyncio,unittest,tempfile,subprocess,shutil
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from music_bot.recording_metadata import resolve_metadata, RecordingMetadata, telegram_fields
from music_bot.providers.common import TrackCandidate
from music_bot.audio_artwork import tag_metadata,embed

ART='https://lastfm.freetls.fastly.net/i/u/300x300/album.jpg'

class CanonicalEnrichmentTests(unittest.IsolatedAsyncioTestCase):
 def track(self):
  return NS(title='Viguen-Sogand ویگن ـ سوگند',artist='TaranehEnterprise',duration=255,metadata_source='youtube_recording',album=None,artwork_url=None)
 async def test_clean_query_enriches_album_art_without_rewriting_selected_identity(self):
  async def lookup(provider,method,*args):
   if provider=='musicbrainz':raise RuntimeError('fixture unavailable')
   return [TrackCandidate('Sogand','Vigen','itunes',duration=255,album='Album',artwork_url=ART)]
  providers=NS(call=AsyncMock(side_effect=lookup));track=self.track()
  result=await resolve_metadata(track,providers,canonical=RecordingMetadata('Sogand','Viguen'))
  self.assertEqual((result.title,result.artist,result.album,result.artwork_url),('Sogand','Viguen','Album',ART))
  providers.call.assert_any_await('itunes','search_titles','Viguen Sogand')
  providers.call.assert_any_await('musicbrainz','search_recordings','Viguen','Sogand')
  self.assertEqual(track.artist,'TaranehEnterprise')
 async def test_failure_ambiguity_version_and_duration_do_not_corrupt_metadata(self):
  canonical=RecordingMetadata('Sogand','Viguen')
  providers=NS(call=AsyncMock(side_effect=RuntimeError('fixture unavailable')))
  self.assertEqual(await resolve_metadata(self.track(),providers,canonical=canonical),canonical)
  for row in [None, {}, TrackCandidate('Sogand','Other','itunes',album='Wrong'),TrackCandidate('Sogand (Live)','Viguen','itunes',album='Wrong'),TrackCandidate('Sogand','Viguen','itunes',duration=600,album='Wrong')]:
   providers.call=AsyncMock(return_value=[row]);self.assertEqual(await resolve_metadata(self.track(),providers,canonical=canonical),canonical)
  # A stripped Karaoke/Cover title must not inherit the original recording's album.
  providers.call=AsyncMock(return_value=[TrackCandidate('Sogand','Viguen','itunes',album='Original')])
  karaoke=RecordingMetadata('Sogand','Viguen',versions=('karaoke',))
  self.assertEqual(await resolve_metadata(self.track(),providers,canonical=karaoke),karaoke)
 async def test_unknown_artist_stays_absent_on_failed_enrichment(self):
  result=await resolve_metadata(self.track(),NS(call=AsyncMock(return_value=[])),canonical=RecordingMetadata('Sogand',''))
  self.assertEqual(telegram_fields(result),{'title':'Sogand'})

class CanonicalTagTests(unittest.IsolatedAsyncioTestCase):
 async def test_real_m4a_title_artist_album_cover_roundtrip_and_unknown_cleanup(self):
  from mutagen.mp4 import MP4
  executable=shutil.which('ffmpeg')
  if not executable:
   from imageio_ffmpeg import get_ffmpeg_exe
   executable=get_ffmpeg_exe()
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'source.m4a'
   subprocess.run([executable,'-nostdin','-v','error','-f','lavfi','-i','anullsrc=r=8000:cl=mono','-t','0.05','-c:a','aac','-y',str(path)],check=True,capture_output=True,timeout=15)
   old=NS(title='Upload title',artist='Bad Channel',album='Old Album',display_artist=None,display_title=None)
   cover=b'\xff\xd8fixture\xff\xd9';embed(path,cover,old)
   fetcher=NS(settings=NS(max_bytes=1_000_000,disk_bytes=3_000_000))
   self.assertTrue(await tag_metadata(fetcher,RecordingMetadata('Sogand','Viguen','Album'),path,Path(folder),AsyncMock(return_value=True)))
   tags=MP4(path)
   self.assertEqual((tags['\xa9nam'],tags['\xa9ART'],tags['\xa9alb']),(['Sogand'],['Viguen'],['Album']))
   self.assertEqual(bytes(tags['covr'][0]),cover)
   self.assertTrue(await tag_metadata(fetcher,RecordingMetadata('Sogand',''),path,Path(folder),AsyncMock(return_value=True)))
   tags=MP4(path);self.assertNotIn('\xa9ART',tags);self.assertNotIn('\xa9alb',tags)
   self.assertEqual(tags['\xa9nam'],['Sogand']);self.assertEqual(bytes(tags['covr'][0]),cover)
