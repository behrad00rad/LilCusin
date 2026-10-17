import unittest
from unittest.mock import AsyncMock, patch, call
from sqlalchemy import select, func
from aiogram.types import Message

from tests.support import ServiceTestCase
from music_bot.submissions import parse_search_query, InvalidSubmission
from music_bot.providers.common import TrackCandidate, ProviderError, Failure
from music_bot.models import IdentificationFlow, SongSubmission, Track, Rating
from music_bot.workflow import Workflow, FlowError
from music_bot.interactions import parse_callback
from music_bot.handlers import text_submission


class SearchInputTests(unittest.TestCase):
    def test_masked_catalogue_titles_are_search_aliases_only(self):
        from music_bot.matching import title_query_match, identity_key, strong_match
        self.assertTrue(title_query_match('niggas in paris', 'Ni**as in Paris', exact=True))
        self.assertTrue(title_query_match('Ni**as in Paris', 'Niggas in Paris', exact=True))
        for title in ['****** in Paris', 'Ni**as in London', 'Paris', 'Ni**as in Paris Remix']:
            self.assertFalse(title_query_match('niggas in paris', title, exact=True))
        self.assertNotEqual(identity_key('Artist', 'Ni**as in Paris'), identity_key('Artist', 'Niggas in Paris'))
        self.assertFalse(strong_match('Artist', 'abcdefgh', [
            TrackCandidate(artist='Artist', title='ab**gh', source='itunes')]))

    def test_same_query_forms_for_chat_and_ui(self):
        for query, expected in [('  hello ', (None, 'hello')), ('همسفر', (None, 'همسفر')),
                                ('Radiohead - Creep', ('Radiohead','Creep'))]:
            self.assertEqual(parse_search_query(query), expected)
        for query in ['', 'a', '  ', '/start', '---', 'x'*241, None, 12]:
            with self.subTest(query=query), self.assertRaises(InvalidSubmission):
                parse_search_query(query)
        self.assertEqual(parse_callback('c:1:2:19'), ('choose',1,2,19))
        self.assertIsNone(parse_callback('c:1:2:20'))


class ChatTitleSearchTests(ServiceTestCase):
    async def test_unknown_popularity_catalogue_is_not_hidden_by_twenty_ranked_versions(self):
        expected = TrackCandidate(artist='Kanye West & JAY-Z', title='Ni**as in Paris', source='itunes')
        variant = TrackCandidate(artist='Bass Boosted', title='N****s in Paris', source='itunes')
        self.providers.has_itunes = True
        async def search(provider, method, *args):
            if provider == 'itunes':
                return [expected, variant]
            if provider == 'lastfm':
                return [TrackCandidate(artist=f'Cover Artist {i}', title='Niggas in Paris',
                                       source='lastfm', listeners=10000 + i) for i in range(25)]
            return []
        self.providers.call.side_effect = search
        rows, failed = await self.workflow.search_title('niggas in paris')
        self.assertFalse(failed)
        self.assertEqual(len(rows), 20)
        self.assertIn(expected, rows[:5])

    async def test_censored_joint_artist_recording_survives_title_filter(self):
        expected = TrackCandidate(artist='Kanye West & JAY-Z', title='Ni**as in Paris', source='itunes')
        self.providers.has_itunes = True
        async def search(provider, method, *args):
            return [expected] if provider == 'itunes' else []
        self.providers.call.side_effect = search
        saved = await self.submissions.submit_search(self.user, 'niggas in paris')
        result = await self.workflow.start(saved.id, 123, fast=True)
        self.assertEqual(result.kind, 'candidates')
        self.assertIn(expected, result.candidates)
        async with self.database.sessions() as session:
            self.assertIsNone((await session.get(SongSubmission, saved.id)).track_id)

    async def test_common_title_refines_to_unreleased_artist_without_guessing(self):
        other = TrackCandidate(artist='Other Artist', title='Prayer', source='musicbrainz')
        expected = TrackCandidate(artist='Kendrick Lamar', title='Prayer', source='musicbrainz')
        async def search(provider, method, *args):
            if provider == 'lastfm':
                raise ProviderError(Failure.AUTH)
            return [expected] if method == 'search_recordings' and args == ('Kendrick Lamar', 'Prayer') else [other]
        self.providers.call.side_effect = search
        saved = await self.submissions.submit_search(self.user, 'prayer')
        first = await self.workflow.start(saved.id, 123, fast=True)
        self.assertEqual(first.candidates, [other])
        await self.workflow.bind_candidates(first, 123, 100)
        with self.assertRaises(FlowError):
            await self.workflow.correct(456, 100, 'Kendrick Lamar - Prayer', fast=True)
        refined = await self.workflow.correct(123, 100, 'Kendrick Lamar - Prayer', fast=True)
        self.assertEqual((refined.kind, refined.artist, refined.title), ('confirmed', 'Kendrick Lamar', 'Prayer'))
        with self.assertRaises(FlowError):
            await self.workflow.select(saved.id, 123, first.revision, 0)

    async def test_title_uses_ui_search_and_waits_for_choice_even_for_one_match(self):
        candidate=TrackCandidate(artist='Adele',title='Hello',source='musicbrainz')
        self.providers.call.return_value=[candidate]
        saved=await self.submissions.submit_search(self.user,'hello')
        result=await self.workflow.start(saved.id,123)
        self.providers.call.assert_has_awaits([call('lastfm','search_titles','hello'),call('musicbrainz','search_titles','hello')],any_order=True)
        self.assertEqual(result.kind,'candidates')
        async with self.database.sessions() as s:
            self.assertIsNone((await s.get(SongSubmission,saved.id)).track_id)
            self.assertEqual(await s.scalar(select(func.count()).select_from(Rating)),0)
        selected=await self.workflow.select(saved.id,123,result.revision,0)
        self.assertEqual(selected.kind,'confirmed')
        self.assertEqual(selected.artist,'Adele')

    async def test_twenty_results_are_selectable_after_new_workflow_and_owner_checked(self):
        self.providers.call.return_value=[TrackCandidate(artist=f'Artist {i}',title='Hello',source='musicbrainz') for i in range(25)]
        saved=await self.submissions.submit_search(self.user,'hello')
        result=await self.workflow.start(saved.id,123)
        self.assertEqual(len(result.candidates),20)
        with self.assertRaises(FlowError):
            await self.workflow.select(saved.id,456,result.revision,19)
        with self.assertRaises(FlowError):
            await self.workflow.select(saved.id,123,result.revision+1,19)
        recovered=Workflow(self.database,self.providers)
        confirmed=await recovered.select(saved.id,123,result.revision,19)
        self.assertEqual(confirmed.artist,'Artist 19')

    async def test_title_reply_can_replace_previous_artist_correction(self):
        saved=await self.submissions.submit_text(self.user,'Wrong Artist - Missing')
        missing=await self.workflow.start(saved.id,123)
        self.assertEqual(missing.kind,'not_found')
        await self.workflow.bind_prompt(missing,123,100)
        self.providers.call.reset_mock()
        self.providers.call.return_value=[TrackCandidate(artist='گوگوش',title='همسفر',source='musicbrainz')]
        result=await self.workflow.correct(123,100,'همسفر')
        self.providers.call.assert_has_awaits([call('lastfm','search_titles','همسفر'),call('musicbrainz','search_titles','همسفر')],any_order=True)
        self.assertEqual(result.kind,'candidates')
        async with self.database.sessions() as s:
            self.assertEqual((await s.get(IdentificationFlow,saved.id)).corrected_artist,'')

    async def test_title_search_failure_keeps_local_results_and_cancel_is_durable(self):
        async with self.database.write() as s:
            s.add(Track(artist='Adele',title='Hello',metadata_source='test'))
        self.providers.call.side_effect=ProviderError(Failure.NETWORK)
        saved=await self.submissions.submit_search(self.user,'hello')
        result=await self.workflow.start(saved.id,123)
        self.assertEqual(result.kind,'candidates')
        await self.workflow.cancel(123)
        with self.assertRaises(FlowError):
            await self.workflow.select(saved.id,123,result.revision,0)

    async def test_no_title_results_do_not_confirm_a_different_song(self):
        self.providers.call.return_value=[TrackCandidate(artist='Adele',title='Skyfall',source='musicbrainz')]
        saved=await self.submissions.submit_search(self.user,'hello')
        result=await self.workflow.start(saved.id,123)
        self.assertEqual(result.kind,'not_found')
        async with self.database.sessions() as s:
            self.assertIsNone((await s.get(SongSubmission,saved.id)).track_id)

    async def test_popular_prefix_matches_outrank_obscure_exact_titles(self):
        async with self.database.write() as s:
            s.add(Track(artist='New England',title='Hello, Hello, Hello',metadata_source='test'))
        async def search(provider,method,*args):
            if provider=='lastfm':
                return [TrackCandidate(artist='Adele',title='Hello',source='lastfm',listeners=5000000),
                        TrackCandidate(artist='Lionel Richie',title='Hello',source='lastfm',listeners=1000000),
                        TrackCandidate(artist='Popular Artist',title='Hello Again',source='lastfm',listeners=9000000)]
            return [TrackCandidate(artist='New England',title='Hello, Hello, Hello',source='musicbrainz',score=100)]
        self.providers.call.side_effect=search
        matches,failed=await self.workflow.search_title('hello')
        self.assertFalse(failed)
        self.assertEqual([row.artist for row in matches[:3]],['Popular Artist','Adele','Lionel Richie'])
        self.assertEqual(sum(row.artist.casefold()=='new england' for row in matches),1)

    async def test_partial_artist_hint_beats_literal_combined_title(self):
        async def search(provider, method, *args):
            if method == 'search_tracks':
                return [TrackCandidate(artist='Pop Smoke', title='Hello', source='lastfm'),
                        TrackCandidate(artist='Other', title='Hello', source='lastfm')]
            return [TrackCandidate(artist='Other', title='Hello Pop', source='lastfm')]
        self.providers.call.side_effect=search
        for query in ['hello pop', 'hello pop smoke', 'hello by pop smoke']:
            with self.subTest(query=query):
                matches,failed=await self.workflow.search_title(query)
                self.assertFalse(failed)
                self.assertEqual((matches[0].artist,matches[0].title),('Pop Smoke','Hello'))
                self.assertFalse(any(c.artist=='Other' and c.title=='Hello' for c in matches))

    async def test_artist_hint_survives_lastfm_outage(self):
        async def search(provider, method, *args):
            if provider=='lastfm':raise ProviderError(Failure.AUTH)
            if method=='search_titles_by_artist' and args==('pop','hello'):
                return [TrackCandidate(artist='Pop Smoke',title='Hello',source='musicbrainz')]
            return []
        self.providers.call.side_effect=search
        saved=await self.submissions.submit_search(self.user,'hello pop')
        result=await self.workflow.start(saved.id,123)
        self.assertEqual(result.kind,'candidates')
        self.assertEqual(result.candidates[0].artist,'Pop Smoke')

    async def test_one_failed_provider_does_not_hide_other_provider_results(self):
        async def search(provider,method,*args):
            if provider=='musicbrainz':raise ProviderError(Failure.NETWORK)
            return [TrackCandidate(artist='Adele',title='Hello',source='lastfm',listeners=5000000)]
        self.providers.call.side_effect=search
        matches,failed=await self.workflow.search_title('hello')
        self.assertFalse(failed)
        self.assertEqual(matches[0].artist,'Adele')

    async def test_empty_working_catalogue_is_not_a_total_outage(self):
        async def search(provider,method,*args):
            if provider=='lastfm':raise ProviderError(Failure.AUTH)
            return []
        self.providers.call.side_effect=search
        saved=await self.submissions.submit_search(self.user,'unknown title')
        result=await self.workflow.start(saved.id,123)
        self.assertEqual(result.kind,'not_found')
        self.providers.call.side_effect=ProviderError(Failure.NETWORK)
        saved=await self.submissions.submit_search(self.user,'another title')
        result=await self.workflow.start(saved.id,123)
        self.assertEqual(result.kind,'failure')

    async def test_title_handler_acknowledges_before_search(self):
        message=Message.model_validate(dict(message_id=1,date=1,text='hello',chat=dict(id=123,type='private'),
            **{'from':dict(id=123,is_bot=False,first_name='Test')}))
        self.providers.call.return_value=[]
        with patch.object(Message,'answer',new_callable=AsyncMock) as answer, \
             patch('music_bot.handlers.present',new_callable=AsyncMock) as presentation, \
             patch('music_bot.handlers.dismiss',new_callable=AsyncMock):
            original=self.workflow.search_title
            async def search(*args,**kwargs):
                answer.assert_awaited_once()
                return await original(*args,**kwargs)
            with patch.object(self.workflow,'search_title',side_effect=search):
                await text_submission(message,self.submissions,self.workflow,AsyncMock())
            self.assertEqual(presentation.call_args.args[1].kind,'not_found')
