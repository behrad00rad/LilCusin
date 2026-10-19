from unittest.mock import AsyncMock, patch
import unittest

from music_bot.cache import CachedProviders
from music_bot.catalog import canonical_track
from music_bot.models import TrackExternalID
from music_bot.providers.common import Failure, ProviderError, TrackCandidate
from music_bot.providers.deezer import DeezerClient, normalize_track
from music_bot.lyrics_search import needs_lyrics
from music_bot.matching import decode_track, encode_track
from tests.support import ServiceTestCase
from tests.test_providers import mock_session
from sqlalchemy import select


class DeezerTests(unittest.IsolatedAsyncioTestCase):
    async def test_normalization_keeps_popularity_separate_from_listener_counts(self):
        candidate=normalize_track({'id':123,'title':'Song','artist':{'name':'Artist'},'rank':650000,'duration':125,
                                   'preview':'https://unused.invalid/audio','album':{'title':'Album'}})
        self.assertEqual(candidate.deezer_rank,650000)
        self.assertIsNone(candidate.listeners)
        self.assertEqual(candidate.external_ids,{'deezer':'123'})
        self.assertEqual(decode_track(encode_track(candidate)),candidate)
        self.assertIsNone(decode_track({'artist':'Artist','title':'Song','source':'lastfm'}).deezer_rank)
        self.assertIsNone(normalize_track({'rank':'bad'}).deezer_rank)

    async def test_search_uses_only_fixed_metadata_endpoint_with_bounded_results(self):
        client=DeezerClient(mock_session({'data':[]}))
        self.assertEqual(await client.search_titles('hello'),[])
        request=client.session.get.call_args
        self.assertEqual(request.args[0],'https://api.deezer.com/search')
        self.assertEqual(request.kwargs['params'],{'q':'hello','limit':100,'order':'RANKING'})
        self.assertFalse(request.kwargs['allow_redirects'])

    async def test_one_generic_completion_finds_other_artists_versions(self):
        client=DeezerClient(None)
        original=TrackCandidate(artist='The Smiths',title='Please, Please, Please, Let Me Get What I Want (2008 Remaster)',source='deezer',deezer_rank=680000)
        cover=TrackCandidate(artist='Deftones',title='Please Please Please Let Me Get What I Want',source='deezer',deezer_rank=510000)
        client._search=AsyncMock(side_effect=[[original],[cover]])
        self.assertEqual(await client.search_titles('please please please'),[original,cover])
        self.assertEqual(client._search.await_count,2)
        self.assertEqual(client._search.await_args.args[0],'please please please let me get what i want')

    async def test_optional_completion_outage_preserves_original_results(self):
        client=DeezerClient(None)
        song=TrackCandidate(artist='Artist',title='Words Words And A Longer Song Name',source='deezer')
        client._search=AsyncMock(side_effect=[[song],ProviderError(Failure.NETWORK)])
        self.assertEqual(await client.search_titles('words words'),[song])


class PopularSearchTests(ServiceTestCase):
    async def test_popular_long_titles_appear_before_obscure_exact_titles(self):
        self.providers.has_deezer=True
        async def search(provider,method,*args):
            if provider=='lastfm':raise ProviderError(Failure.AUTH)
            if provider=='deezer':
                return [TrackCandidate(artist='Obscure',title='Please Please Please',source='deezer',deezer_rank=1000),
                        TrackCandidate(artist='The Smiths',title='Please, Please, Please, Let Me Get What I Want',source='deezer',deezer_rank=680000),
                        TrackCandidate(artist='Deftones',title='Please Please Please Let Me Get What I Want',source='deezer',deezer_rank=510000),
                        TrackCandidate(artist='Unrelated',title='Different Song',source='deezer',deezer_rank=999999)]
            return []
        self.providers.call.side_effect=search
        matches,failed=await self.workflow.search_title('please please please')
        self.assertFalse(failed)
        self.assertEqual([c.artist for c in matches],['The Smiths','Deftones','Obscure'])

    async def test_deezer_outage_keeps_lastfm_popularity_and_artist_hints(self):
        self.providers.has_deezer=True
        async def search(provider,method,*args):
            if provider=='deezer':raise ProviderError(Failure.NETWORK)
            return [TrackCandidate(artist='Adele',title='Hello',source='lastfm',listeners=5000000)]
        self.providers.call.side_effect=search
        matches,failed=await self.workflow.search_title('hello')
        self.assertFalse(failed)
        self.assertEqual(matches[0].artist,'Adele')

    async def test_popularity_cache_and_source_identity_survive_recreation(self):
        deezer=AsyncMock()
        song=TrackCandidate(artist='Artist',title='Title',source='deezer',external_ids={'deezer':'123'},deezer_rank=600000)
        deezer.search_titles.return_value=[song]
        providers=CachedProviders(self.database,AsyncMock(),AsyncMock(),deezer)
        self.assertEqual(await providers.call('deezer','search_titles','title'),[song])
        restored=CachedProviders(self.database,AsyncMock(),AsyncMock(),AsyncMock())
        self.assertEqual(await restored.call('deezer','search_titles','title'),[song])
        async with self.database.write() as session:
            track=await canonical_track(session,song)
            identifier=await session.scalar(select(TrackExternalID).where(TrackExternalID.track_id==track.id))
            self.assertEqual((identifier.provider,identifier.external_identifier),('deezer','123'))
        deezer.search_titles.assert_awaited_once()
        self.assertFalse(needs_lyrics('A Popular Song',[TrackCandidate(artist='Artist',title='A Popular Song',source='deezer',deezer_rank=600000)]))
