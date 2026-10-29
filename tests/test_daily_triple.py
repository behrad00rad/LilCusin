import unittest
from types import SimpleNamespace as N
from music_bot.daily_pick import varied_picks,explain_caption
from music_bot.recommendations.types import Recommendation
class TripleTests(unittest.TestCase):
 def row(self,i,a,explore=False):return Recommendation(i,a,'Song',None,None,{},1,'Similar to artists you like',(),explore)
 def test_variety(self):
  rows=[self.row(1,'A'),self.row(2,'A'),self.row(3,'B'),self.row(4,'C',True)]
  self.assertEqual([r.track_id for r in varied_picks(rows)],[1,3,4])
 def test_sparse(self):self.assertEqual(len(varied_picks([self.row(1,'A')])),1)
 def test_reason_and_links(self):
  fields={'caption':'links','caption_entities':['fixture']}
  req=N(canonical_metadata={'_daily_pick':{'recommendation':{'reason':'Similar to artists you like'}}})
  result=explain_caption(fields,req,'en')
  self.assertIn('Why this pick:',result['caption']);self.assertEqual(result['caption_entities'],['fixture'])
