import asyncio
import json
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from music_bot.config import ConfigError
from music_bot.lyrics_search import LyricsSearch, LyricsSettings, needs_lyrics, video_hints
from music_bot.providers.common import Failure, ProviderError, TrackCandidate
from music_bot.workflow import Workflow, FlowError
from tests.support import ServiceTestCase
from tests.test_providers import mock_session


class LyricsParsingTests(unittest.TestCase):
    def test_fallback_only_for_weak_phrase_queries(self):
        song = TrackCandidate(artist='Pop Smoke', title='Hello', source='test')
        self.assertFalse(needs_lyrics('hello', []))
        self.assertFalse(needs_lyrics('hello pop smoke', [song]))
        self.assertFalse(needs_lyrics('we could have had it all', [
            TrackCandidate(artist='Artist', title='We Could Have Had It All', source='test',listeners=50000)]))
        self.assertTrue(needs_lyrics('we could have had it all', []))
        self.assertTrue(needs_lyrics('با من بمان', []))

    def test_hints_are_bounded_and_no_unstructured_guess(self):
        self.assertEqual(video_hints([{'title':'Adele - Rolling in the Deep (Lyrics)'},
                                    {'title':'random unrelated text'}, None]),
                         [('Adele','Rolling in the Deep'),('Rolling in the Deep','Adele')])
        self.assertEqual(len(video_hints([{'artist':f'Artist {i}','track':'Song'} for i in range(10)])),3)

    def test_config_and_secret_repr(self):
        with patch.dict(os.environ,{'LYRICS_SEARCH_PROVIDER':'musixmatch','MUSIXMATCH_API_KEY':'private-value'}):
            self.assertNotIn('private-value',repr(LyricsSettings.environment()))
        for provider,key in [('invalid',''),('musixmatch','')]:
            with patch.dict(os.environ,{'LYRICS_SEARCH_PROVIDER':provider,'MUSIXMATCH_API_KEY':key}):
                with self.assertRaises(ConfigError):LyricsSettings.environment()


class LyricsProviderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.providers=AsyncMock()
        self.song=TrackCandidate(artist='Adele',title='Rolling in the Deep',source='musicbrainz')
        self.providers.call.return_value=[self.song]
        self.search=LyricsSearch(None,self.providers)
        self.search.discover=AsyncMock(return_value=[('Adele','Rolling in the Deep')])
        self.phrase='we could have had it all'

    async def test_validate_cache_and_deduplicate_concurrent_phrases(self):
        first,second=await asyncio.gather(self.search.search(self.phrase),self.search.search(self.phrase))
        self.assertEqual(first,([self.song],False))
        self.assertEqual(second,first)
        self.search.discover.assert_awaited_once()
        self.assertNotIn(self.phrase,repr(self.search.cache))
        self.assertEqual(self.providers.call.await_count,2)
        self.search.clear()
        self.assertFalse(self.search.cache)

    async def test_one_catalogue_outage_and_unverified_hint_rejection(self):
        async def call(provider,*args):
            if provider=='lastfm':raise ProviderError(Failure.AUTH)
            return [self.song,TrackCandidate(artist='Other',title='Unrelated',source='test')]
        self.providers.call.side_effect=call
        self.assertEqual(await self.search.search(self.phrase),([self.song],False))
        self.search.clear()
        self.providers.call.side_effect=None
        self.providers.call.return_value=[TrackCandidate(artist='Other',title='Unrelated',source='test')]
        self.assertEqual(await self.search.search(self.phrase),([],False))

    async def test_lyric_video_labels_and_wrong_versions_are_not_canonical_results(self):
        self.providers.call.return_value=[self.song,
            TrackCandidate(artist='Adele',title='Rolling in the Deep + Lyrics',source='lastfm'),
            TrackCandidate(artist='Adele',title='Rolling in the Deep',source='lastfm',listeners=2),
            TrackCandidate(artist='Adele',title='Rolling in the Deep live',source='test')]
        self.assertEqual(await self.search.search(self.phrase),([self.song],False))

    async def test_cache_expiry_size_and_off_mode(self):
        clock=[100]
        self.search.clock=lambda:clock[0]
        await self.search.search(self.phrase)
        clock[0]+=901
        await self.search.search(self.phrase)
        self.assertEqual(self.search.discover.await_count,2)
        for i in range(130):await self.search.search(f'other remembered words {i}')
        self.assertEqual(len(self.search.cache),128)
        off=LyricsSearch(None,self.providers,LyricsSettings('off'))
        off.discover=AsyncMock()
        self.assertEqual(await off.search(self.phrase),([],False))
        off.discover.assert_not_awaited()

    async def test_errors_cooldown_capacity_and_cancellation(self):
        self.search.discover.side_effect=ProviderError(Failure.RATE_LIMIT)
        self.assertEqual(await self.search.search(self.phrase),([],True))
        self.assertEqual(await self.search.search('a different lyric phrase'),([],True))
        self.search.discover.assert_awaited_once()
        self.search.retry_after=0
        self.search.discover.side_effect=asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):await self.search.search(self.phrase)
        self.assertEqual(self.search.capacity._value,2)
        await self.search.capacity.acquire();await self.search.capacity.acquire()
        self.assertEqual(await self.search.search(self.phrase),([],True))
        self.search.capacity.release();self.search.capacity.release()

    async def test_youtube_metadata_only_and_temporary_cleanup_on_failure(self):
        fetcher=AsyncMock()
        fetcher.base=lambda:['python','-m','yt_dlp','--ignore-config','--no-cookies']
        search=LyricsSearch(None,self.providers,fetcher=fetcher)
        directories=[]
        async def process(args,directory,alive,output):
            directories.append(Path(directory))
            self.assertTrue(await alive())
            self.assertIn('--skip-download',args)
            self.assertEqual(args[-1],'ytsearch5:'+self.phrase+' lyrics')
            self.assertNotIn('shell',args)
            (Path(directory)/'partial').write_text('temporary')
            return json.dumps({'entries':[{'title':'Adele - Rolling in the Deep (Lyrics)'}]}).encode()
        fetcher.process.side_effect=process
        self.assertEqual(await search.discover(self.phrase),
                         [('Adele','Rolling in the Deep'),('Rolling in the Deep','Adele')])
        self.assertTrue(all(not p.exists() for p in directories))
        async def cancelled(*args,**kwargs):
            directories.append(Path(args[1]))
            raise asyncio.CancelledError()
        fetcher.process.side_effect=cancelled
        with self.assertRaises(asyncio.CancelledError):await search.discover(self.phrase)
        self.assertTrue(all(not p.exists() for p in directories))

    async def test_malformed_source_data_fails_safely_without_cache(self):
        fetcher=AsyncMock()
        fetcher.base=lambda:['python','-m','yt_dlp']
        directories=[]
        async def process(args,directory,*rest,**kwargs):
            directories.append(Path(directory))
            return b'not valid JSON'
        fetcher.process.side_effect=process
        search=LyricsSearch(None,self.providers,fetcher=fetcher)
        self.assertEqual(await search.search(self.phrase),([],True))
        self.assertFalse(search.cache)
        self.assertTrue(all(not p.exists() for p in directories))

    async def test_musixmatch_searches_phrase_without_requesting_full_lyrics(self):
        session=mock_session({'message':{'header':{'status_code':200},'body':{'track_list':[
            {'track':{'artist_name':'Adele','track_name':'Rolling in the Deep'}}]}}})
        search=LyricsSearch(session,self.providers,LyricsSettings('musixmatch','hidden-key'))
        self.assertEqual(await search.search(self.phrase),([self.song],False))
        params=session.get.call_args.kwargs['params']
        self.assertEqual(params['q_lyrics'],self.phrase)
        self.assertNotIn('lyrics.get',session.get.call_args.args[0])
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])


class LyricsWorkflowTests(ServiceTestCase):
    async def test_phrase_results_require_owner_choice_and_survive_restart(self):
        lyrics=AsyncMock()
        lyrics.search.return_value=([TrackCandidate(artist='Adele',title='Rolling in the Deep',source='test')],False)
        workflow=Workflow(self.database,self.providers,lyrics)
        saved=await self.submissions.submit_search(self.user,'we could have had it all')
        result=await workflow.start(saved.id,123)
        self.assertEqual(result.kind,'candidates')
        with self.assertRaises(FlowError):await workflow.select(saved.id,456,result.revision,0)
        selected=await Workflow(self.database,self.providers).select(saved.id,123,result.revision,0)
        self.assertEqual((selected.kind,selected.title),('confirmed','Rolling in the Deep'))

    async def test_forgetting_removes_phrase_and_invalidates_buttons(self):
        from music_bot.chat_service import ChatService
        from music_bot.models import SongSubmission
        lyrics=AsyncMock()
        lyrics.search.return_value=([TrackCandidate(artist='Adele',title='Rolling in the Deep',source='test')],False)
        workflow=Workflow(self.database,self.providers,lyrics)
        saved=await self.submissions.submit_search(self.user,'we could have had it all')
        result=await workflow.start(saved.id,123)
        await ChatService(self.database,AsyncMock()).forget(123)
        async with self.database.sessions() as session:
            self.assertIsNone(await session.get(SongSubmission,saved.id))
        with self.assertRaises(FlowError):await workflow.select(saved.id,123,result.revision,0)

    async def test_ordinary_title_and_artist_hint_skip_lyrics(self):
        lyrics=AsyncMock()
        self.providers.call.return_value=[TrackCandidate(artist='Pop Smoke',title='Hello',source='test')]
        workflow=Workflow(self.database,self.providers,lyrics)
        await workflow.search_title('hello')
        await workflow.search_title('hello pop smoke')
        lyrics.search.assert_not_awaited()

    async def test_optional_lyrics_failure_preserves_weak_catalogue_matches(self):
        lyrics=AsyncMock()
        lyrics.search.return_value=([],True)
        self.providers.call.return_value=[TrackCandidate(artist='Artist',title='A long phrase here extended',source='test')]
        matches,failed=await Workflow(self.database,self.providers,lyrics).search_title('a long phrase here')
        self.assertEqual(len(matches),1)
        self.assertFalse(failed)
