import unittest
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from music_bot.recording_metadata import prepare_results, result_metadata, result_pages, search_label
from music_bot.recording_search import RecordingSearch, recordings
from music_bot.interactions import candidate_keyboard
from music_bot.i18n import language
from music_bot.providers.common import TrackCandidate
from tests.test_song_cleaner import CASES

class SongResultTests(unittest.IsolatedAsyncioTestCase):
 def rows(self):
  return [TrackCandidate(title, structured or channel, 'youtube_music' if structured else 'youtube_recording',
      duration=255, external_ids={'youtube':f'video{i:06d}'},recording_metadata={'raw_title':title,'channel':channel})
      for i,(title,channel,structured,_,_) in enumerate(CASES)]

 def test_trace_cleanup_dedupe_and_alternatives(self):
  rows=self.rows()
  rows += [TrackCandidate('Delkash and Vigen - Bordi Az Yadam 8K (Persian Karaoke)', 'Avaz Khoneh', 'youtube_recording',duration=255),
           TrackCandidate('Vigen , iranian singer','Francois Babak','youtube_recording',duration=200)]
  result=prepare_results('Viguen Sogand',rows)
  main=[result_metadata(r) for r in result if not r.recording_metadata['demoted']]
  self.assertEqual([(r.artist,r.title) for r in main],[('Viguen','Sogand'),('Viguen','Eshegh-e Moghaddas'),('Viguen','Avazeh Khan'),('Viguen','Beevafa'),('Viguen','Chera Nemiraghsi'),('Viguen','Yaadegaary')])
  self.assertEqual(sum(result_metadata(r).title=='Sogand' for r in result),1)
  self.assertFalse(any(result_metadata(r).title in ['VIGEN','Vigen , iranian singer'] for r in result))
  demoted=[r for r in result if r.recording_metadata['demoted']]
  self.assertEqual(len(demoted),4)
  self.assertTrue(any('karaoke' in r.recording_metadata['flags'] for r in demoted))
  self.assertTrue(any('cover' in r.recording_metadata['flags'] for r in demoted))
  self.assertEqual(next(r for r in result if result_metadata(r).title=='Avazeh Khan').source,'youtube_music')
  self.assertEqual(rows[1].title,'Viguen-Sogand ویگن ـ سوگند')

 def test_title_only_and_explicit_versions_do_not_artist_filter(self):
  rows=self.rows()
  for query in ['Sogand','Viguen Sogand cover']:
   result=prepare_results(query,rows)
   self.assertTrue(any(result_metadata(r).artist=='Ali N. Askin' and not r.recording_metadata['demoted'] for r in result))

 def test_complete_song_title_does_not_become_artist_filter(self):
  rows=[TrackCandidate('There','Hello','youtube_music'),TrackCandidate('Hello There','Other','youtube_music')]
  result=prepare_results('Hello There',rows)
  self.assertTrue(all(not r.recording_metadata['demoted'] for r in result))

 def test_duration_and_bilingual_labels_keep_artist_visible(self):
  self.assertEqual(search_label('Viguen','Sogand','youtube_music',duration=255),'4:15 • Sogand — Viguen')
  self.assertEqual(search_label('Viguen','Sogand','youtube_music'),'Sogand — Viguen')
  self.assertEqual(search_label('Channel','Sogand','youtube_recording'),'Sogand')
  for locale, marker in [('en','Karaoke'),('fa','کارائوکه')]:
   value=search_label('Viguen','Sogand','youtube_music',duration=255,locale=locale,flags=['karaoke'])
   self.assertEqual(value,f'4:15 • {marker} · Sogand — Viguen')

 def test_sparse_first_page_and_callback_indices(self):
  rows=prepare_results('Viguen Sogand',self.rows()[:4])
  result=NS(candidates=rows,submission_id=1,revision=2)
  first=candidate_keyboard(result,chat=True)
  callbacks=[b.callback_data for group in first.inline_keyboard for b in group]
  self.assertEqual([c for c in callbacks if c.startswith('c:')],['c:1:2:0','c:1:2:1'])
  self.assertIn('p:1:2:5',callbacks)
  more=candidate_keyboard(result,chat=True,offset=5)
  choices=[b.callback_data for group in more.inline_keyboard for b in group if b.callback_data.startswith('c:')]
  self.assertEqual(choices,['c:1:2:2'])
  self.assertEqual(result_pages(rows)[1],6)

 def test_compilations_demoted_not_deleted_and_topic_beats_label(self):
  a=TrackCandidate('Viguen - Sogand','Uploader','youtube_recording',duration=200)
  b=replace(a,artist='Viguen - Topic')
  for incoming in [[a,b],[b,a]]:
   rows=prepare_results('Viguen Sogand',incoming,searched_artist='Viguen')
   self.assertEqual(len(rows),1);self.assertEqual(rows[0].artist,'Viguen - Topic')
  mixes=[replace(a,title='Viguen - Best Of Mix'),replace(a,title='Viguen - Long Song',duration=481)]
  rows=prepare_results('Viguen Sogand',mixes,searched_artist='Viguen')
  self.assertEqual(len(rows),2);self.assertTrue(all(r.recording_metadata['demoted'] for r in rows))

 async def test_search_merges_raw_upload_context_without_extra_calls(self):
  music=[dict(videoId='aaaaaaaaaaa',title='Sogand',resultType='song',artists=[{'name':'Viguen'}],duration_seconds=255),
         dict(videoId='bbbbbbbbbbb',title='Sogand',resultType='video',artists=[{'name':'Viguen'}],duration_seconds=255)]
  upload=dict(id='bbbbbbbbbbb',title='Viguen-Sogand ویگن ـ سوگند',uploader='TaranehEnterprise',duration=255)
  client=RecordingSearch();client.process=AsyncMock(side_effect=[music,{'entries':[upload]}])
  rows,failed=await client.search('Viguen Sogand')
  self.assertFalse(failed);self.assertEqual(len(rows),1)
  self.assertEqual((result_metadata(rows[0]).artist,result_metadata(rows[0]).title),('Viguen','Sogand'))
  self.assertEqual(client.process.await_count,2)
