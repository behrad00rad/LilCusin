import unittest
from music_bot.recording_metadata import clean_recording

# Raw title/channel, structured artist (when available), expected artist/title.
CASES = [
 ('Sogand', 'Viguen - Topic', 'Viguen', 'Viguen', 'Sogand'),
 ('Viguen-Sogand ویگن ـ سوگند', 'TaranehEnterprise', None, 'Viguen', 'Sogand'),
 ('Eshegh-e Moghaddas', 'Viguen - Topic', 'Viguen', 'Viguen', 'Eshegh-e Moghaddas'),
 ('سوگند – ویگن | Sogand – Vigen | Golden Persian Covers', 'Golden Persian Covers', None, 'Viguen', 'سوگند'),
 ('Avazeh Khan', 'Viguen - Topic', 'Viguen', 'Viguen', 'Avazeh Khan'),
 ('SOGAND (Oath) Vigen Arranged for Classical Guitar By: Boghrat', 'Boghrat Sadeghan', None, 'Viguen', 'SOGAND (Oath) Vigen Arranged for Classical Guitar By: Boghrat'),
 ('Mara Beboos (feat. Sogand)', 'Ali N. Askin - Topic', 'Ali N. Askin', 'Ali N. Askin', 'Mara Beboos (feat. Sogand)'),
 ('VIGEN', 'Vigen Avagyan', None, 'Viguen', 'VIGEN'),
 ('Beevafa', 'Viguen - Topic', 'Viguen', 'Viguen', 'Beevafa'),
 ('Viguen - Chera Nemiraghsi (Offical Audio & Lyrics) | ویگن - چرا نمی رقصی | Caltex Records', 'Caltex Records', None, 'Viguen', 'Chera Nemiraghsi'),
 ('Yaadegaary', 'Viguen - Topic', 'Viguen', 'Viguen', 'Yaadegaary'),
 ('Viguen - Avazeh Khan | ویگن - آواز خوان', 'persianmusictube', None, 'Viguen', 'Avazeh Khan'),
]

class SongCleanerTests(unittest.TestCase):
 def test_twelve_trace_rows(self):
  for title, channel, structured, artist, expected in CASES:
   with self.subTest(title=title):
    value=clean_recording(structured or channel,title,'youtube_music' if structured else 'youtube_recording',channel=channel,searched_artist='Viguen')
    self.assertEqual((value.artist,value.title),(artist,expected))

 def test_tight_hyphen_requires_known_artist_and_preserves_ezafe(self):
  for artist in [None,'Viguen']:
   self.assertEqual(clean_recording('Uploader','Eshegh-e Moghaddas','youtube_recording',searched_artist=artist).title,'Eshegh-e Moghaddas')
  self.assertEqual(clean_recording('Uploader','AC-DC','youtube_recording').title,'AC-DC')
  self.assertEqual(clean_recording('Uploader','Vigen-Sogand','youtube_recording',known_artists=['Viguen']).artist,'Viguen')

 def test_source_priority_and_uploader_rejection(self):
  value=clean_recording('Viguen','Other Artist - Song','youtube_music',channel='Caltex Records',searched_artist='Other Artist')
  self.assertEqual(value.artist,'Viguen')
  value=clean_recording('TaranehEnterprise','Sogand','youtube_recording')
  self.assertEqual(value.artist,'')
  value=clean_recording('TaranehEnterprise','Sogand','youtube_recording',channel='Viguen - Topic')
  self.assertEqual(value.artist,'Viguen')
  for label in ['Unverified','Caltex Records','TaranehEnterprise']:
   self.assertEqual(clean_recording(label,label+' - Sogand','youtube_recording').artist,'')

 def test_unicode_noise_and_topic_features(self):
  value=clean_recording('Uploader','Ｖｉｇｕｅｎ—Sogand (OFFICAL VIDEO) ｜ Caltex Records #old','youtube_recording',searched_artist='Viguen')
  self.assertEqual((value.artist,value.title),('Viguen','Sogand'))
  for noise in [' (Official Audio)',' (Offical Audio & Lyrics)',' (Persian Karaoke)',' (کارائوکه فارسی)',' 8K',' #old']:
   self.assertEqual(clean_recording('Uploader','Viguen - Sogand'+noise,'youtube_recording',searched_artist='Viguen').title,'Sogand')
  self.assertEqual(clean_recording('Uploader','Viguen - Sogand feat. Guest','youtube_recording').title,'Sogand')
  self.assertEqual(clean_recording('Viguen - Topic','Sogand feat. Guest','youtube_recording').title,'Sogand feat. Guest')
