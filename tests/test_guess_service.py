"""Local game/API privacy tests. No provider, audio or real Telegram calls."""
import asyncio
import json
import os
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import make_mocked_request
from sqlalchemy import delete, select

from music_bot.database import Database
from music_bot.guess_game import GuessGame, GuessRound, allow_guess
from music_bot.guess_service import GuessError, GuessService, base_title, interactions, recent_right
from music_bot.models import User, Track, TrackTag, Rating, TrackExternalID, utc_now
from music_bot.comparison_invitations import ComparisonInvitation
from music_bot.taste_cards import TasteCard, SignatureSong
from music_bot.taste_sharing import FriendTasteSharing, GuiltyPleasure
from music_bot.social import SocialBlock, SavedSong, stop_interactions
from music_bot.feed_history import FeedHistory
from music_bot.taste_learning import TasteRequest, TrackPreference


class GuessServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.flag = patch.dict(os.environ, {'GUESS_GAME': '1'}); self.flag.start(); self.addCleanup(self.flag.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / 'guess.sqlite3')
        await self.db.initialize()
        self.service = GuessService(self.db)
        self.friend = 'f' * 32
        async with self.db.write() as session:
            session.add_all([User(id=key, telegram_user_id=100+key) for key in (1, 2, 3)])
            await session.flush()
            session.add(FriendTasteSharing(user_id=2, enabled=True))
            session.add(ComparisonInvitation(token=self.friend, sender_id=1, recipient_id=2,
                sender_revision=0, recipient_revision=0, card_token='fixture',
                sender_snapshot={'friendship': True}, recipient_snapshot={'friendship': True},
                state='consented', expires_at=utc_now()+timedelta(days=1)))
            for key in range(1, 61):
                session.add(Track(id=key, artist=f'Artist {key}', title=f'Song {key}',
                                  metadata_source='fixture'))
            await session.flush()
            for key in range(1, 61):
                session.add(TrackTag(track_id=key, name='english', source='fixture', weight=1))
                session.add(TrackTag(track_id=key, name='rock', source='fixture', weight=1))
            for key in range(1, 6):
                session.add(Rating(user_id=2, track_id=key, value='love'))

    async def asyncTearDown(self):
        await self.db.close(); self.temp.cleanup()

    async def start(self):
        return await self.service.start(101, self.friend)

    async def rows(self, game_id):
        async with self.db.sessions() as session:
            return list(await session.scalars(select(GuessRound).where(GuessRound.game_id == game_id).order_by(GuessRound.idx)))

    async def finish(self, start=None):
        start = start or await self.start()
        result = None
        for row in await self.rows(start['game_id']):
            result = await self.service.answer(101, start['game_id'], row.idx, row.correct_recording_id)
        return start, result

    async def test_shared_only_private_lock_alias_and_versions(self):
        async with self.db.write() as session:
            session.add(Rating(user_id=2, track_id=6, value='love'))
            session.add(GuiltyPleasure(user_id=2, track_id=6))
            (await session.get(Track, 7)).title = 'Song 6 (Live)'
            session.add(Rating(user_id=2, track_id=7, value='love'))
            session.add(TrackExternalID(track_id=6, provider='musicbrainz', external_identifier='private-alias'))
            session.add(TrackExternalID(track_id=8, provider='lastfm', external_identifier='private-other'))
        start = await self.start()
        self.assertEqual({row.correct_recording_id for row in await self.rows(start['game_id'])}, set(range(1, 6)))
        async with self.db.write() as session:
            (await session.get(FriendTasteSharing, 2)).enabled = False
        status = await self.service.status(101, self.friend)
        self.assertEqual(status['have'], 0)
        with self.assertRaises(GuessError):
            await self.start()

    async def test_lifetime_interactions_and_version_exclusion(self):
        async with self.db.write() as session:
            session.add_all([Rating(user_id=2, track_id=6, value='like'),
                Rating(user_id=2, track_id=7, value='neutral'), Rating(user_id=2, track_id=8, value='dislike'),
                GuiltyPleasure(user_id=2, track_id=9), SavedSong(user_id=2, track_id=10),
                TasteRequest(user_id=2, track_id=11, request_key='old', created_at=utc_now()-timedelta(days=500)),
                FeedHistory(user_id=2, track_id=12, skipped_at=utc_now()-timedelta(days=500)),
                FeedHistory(user_id=2, track_id=13, hidden_forever=True),
                TrackPreference(user_id=2, track_id=14, feedback='known')])
            (await session.get(Track, 15)).title = 'Song 1 (Acoustic)'
            (await session.get(Track, 16)).title = 'Song 8 - Remastered'
        start = await self.start()
        rows = await self.rows(start['game_id'])
        options = [key for row in rows for key in row.option_ids]
        self.assertEqual(len(set(options)), 20)
        self.assertFalse(set(options) & set(range(6, 17)))
        async with self.db.sessions() as session:
            touched = await interactions(session, 2)
            for row in rows:
                self.assertFalse((set(row.option_ids) - {row.correct_recording_id}) & set(touched))

    async def test_nonfriend_block_optout_and_feature_off(self):
        with self.assertRaises(GuessError):
            await self.service.start(103, self.friend)
        for owner, target in ((1, 2), (2, 1)):
            async with self.db.write() as session:
                session.add(SocialBlock(owner_id=owner, target_id=target))
            self.assertFalse((await self.service.status(101, self.friend))['eligible'])
            with self.assertRaises(GuessError): await self.start()
            async with self.db.write() as session: await session.execute(delete(SocialBlock))
        async with self.db.write() as session: await allow_guess(session, 2, False)
        self.assertFalse((await self.service.status(101, self.friend))['eligible'])
        with self.assertRaises(GuessError): await self.start()
        with patch.dict(os.environ, {'GUESS_GAME': '0'}):
            with self.assertRaises(GuessError): await self.start()

    async def test_not_enough_and_base_title_grouping(self):
        self.assertEqual(base_title('Song (Live)'), base_title('Song - Remastered 2020'))
        async with self.db.write() as session:
            (await session.get(Track, 5)).title = 'Song 1 (Live)'
        with self.assertRaises(GuessError) as failure: await self.start()
        self.assertEqual(failure.exception.details, {'not_enough': {'have': 4, 'need': 5}})
        self.assertEqual((await self.service.status(101, self.friend))['have'], 4)

    async def test_hidden_answers_resume_idempotent_order_and_ownership(self):
        start = await self.start(); game_id = start['game_id']
        self.assertEqual(start, await self.start())
        self.assertNotIn('correct', json.dumps(start))
        rows = await self.rows(game_id)
        with self.assertRaises(GuessError): await self.service.answer(103, game_id, 0, rows[0].correct_recording_id)
        with self.assertRaises(GuessError): await self.service.answer(101, game_id, 2, rows[2].correct_recording_id)
        with self.assertRaises(GuessError): await self.service.answer(101, game_id, True, rows[0].correct_recording_id)
        for row in rows:
            response, replay = await asyncio.gather(*[
                self.service.answer(101, game_id, row.idx, row.correct_recording_id) for _ in range(2)])
            self.assertEqual(response, replay)
            if response['next_round']:
                self.assertNotIn('correct', json.dumps(response['next_round']))
            wrong = next(key for key in row.option_ids if key != row.correct_recording_id)
            with self.assertRaises(GuessError): await self.service.answer(101, game_id, row.idx, wrong)
        self.assertEqual(response['result']['score'], 5)
        self.assertEqual(response['result']['head_to_head'], {'you': 5, 'them': None})

    async def test_wrong_score_parallel_start_and_unfinished_recent_right(self):
        first, second = await asyncio.gather(self.start(), self.start())
        self.assertEqual(first, second)
        rows = await self.rows(first['game_id'])
        await self.service.answer(101, first['game_id'], 0, rows[0].correct_recording_id)
        async with self.db.sessions() as session:
            right = await recent_right(session, 1, 2, utc_now())
            self.assertIn(rows[0].correct_recording_id, right)
            self.assertFalse(await recent_right(session, 1, 2, utc_now()+timedelta(days=15)))
        for row in rows[1:]:
            wrong = next(key for key in row.option_ids if key != row.correct_recording_id)
            result = await self.service.answer(101, first['game_id'], row.idx, wrong)
            self.assertFalse(result['correct'])
            self.assertEqual(result['correct_recording_id'], row.correct_recording_id)
        self.assertEqual(result['result']['score'], 1)
        self.assertEqual(result['result']['rounds'], [True, False, False, False, False])
        self.assertEqual(len(result['result']['missed']), 4)
        self.assertIsNone(result['next_round'])

    async def test_rechecks_private_and_new_decoy_interaction(self):
        start = await self.start(); row = (await self.rows(start['game_id']))[0]
        decoy = next(key for key in row.option_ids if key != row.correct_recording_id)
        async with self.db.write() as session: session.add(Rating(user_id=2, track_id=decoy, value='neutral'))
        with self.assertRaises(GuessError): await self.service.answer(101, start['game_id'], 0, row.correct_recording_id)
        async with self.db.write() as session: await session.execute(delete(Rating).where(Rating.track_id == decoy))
        async with self.db.write() as session: session.add(GuiltyPleasure(user_id=2, track_id=row.correct_recording_id))
        with self.assertRaises(GuessError): await self.service.answer(101, start['game_id'], 0, row.correct_recording_id)

    async def test_daily_limit_recent_right_alternatives_and_expiry(self):
        first, _ = await self.finish()
        async with self.db.write() as session:
            session.add_all([Rating(user_id=2, track_id=key, value='love') for key in range(6, 11)])
        second = await self.start()
        self.assertEqual({row.correct_recording_id for row in await self.rows(second['game_id'])}, set(range(6, 11)))
        await self.finish(second)
        await self.finish()
        with self.assertRaises(GuessError) as failure: await self.start()
        self.assertEqual(failure.exception.status, 429)
        async with self.db.write() as session:
            for game in await session.scalars(select(GuessGame)):
                game.created_at = utc_now()-timedelta(days=2)
        fresh = await self.start()
        async with self.db.write() as session:
            (await session.get(GuessGame, fresh['game_id'])).created_at = utc_now()-timedelta(days=2)
        with self.assertRaises(GuessError) as failure:
            row = (await self.rows(fresh['game_id']))[0]
            await self.service.answer(101, fresh['game_id'], 0, row.correct_recording_id)
        self.assertEqual(failure.exception.status, 410)

    async def test_signature_songs_and_new_loves_status(self):
        await self.finish()
        async with self.db.write() as session:
            session.add(Rating(user_id=2, track_id=6, value='love'))
        status = await self.service.status(101, self.friend)
        self.assertEqual(status['new_loves_since_last_game'], 1)
        async with self.db.write() as session:
            session.add(TasteCard(user_id=2, taste_id='LC-fixture', nickname='Friend'))
            await session.flush()
            for idx, key in enumerate(range(7, 12)):
                session.add(SignatureSong(user_id=2, position=idx, track_id=key))
            (await session.get(FriendTasteSharing, 2)).enabled = False
        self.assertEqual((await self.service.status(101, self.friend))['have'], 5)
        start = await self.start()
        self.assertEqual({row.correct_recording_id for row in await self.rows(start['game_id'])}, set(range(7, 12)))

    async def test_known_language_conflict_and_no_partial_game(self):
        async with self.db.write() as session:
            await session.execute(delete(TrackTag).where(TrackTag.track_id > 5, TrackTag.name == 'english'))
            session.add_all([TrackTag(track_id=key, name='persian', source='fixture', weight=1) for key in range(6, 61)])
        with self.assertRaises(GuessError): await self.start()
        async with self.db.sessions() as session:
            self.assertEqual(list(await session.scalars(select(GuessGame))), [])

    async def test_unplayable_shared_songs_do_not_hide_playable_alternatives(self):
        async with self.db.write() as session:
            await session.execute(delete(TrackTag).where(TrackTag.track_id <= 5, TrackTag.name == 'english'))
            session.add_all([TrackTag(track_id=key, name='persian', source='fixture', weight=1) for key in range(1, 6)])
            session.add_all([Rating(user_id=2, track_id=key, value='love') for key in range(6, 11)])
        with patch('music_bot.guess_service.RNG.shuffle', side_effect=lambda values: None):
            start = await self.start()
        self.assertEqual({row.correct_recording_id for row in await self.rows(start['game_id'])}, set(range(6, 11)))

    async def test_unknown_language_decoys_keep_privacy_exclusions(self):
        async with self.db.write() as session:
            await session.execute(delete(TrackTag).where(TrackTag.name == 'english'))
            session.add_all([Rating(user_id=2, track_id=6, value='dislike'),
                             SavedSong(user_id=2, track_id=7)])
        start = await self.start()
        rows = await self.rows(start['game_id'])
        options = {key for row in rows for key in row.option_ids}
        self.assertEqual(len(options), 20)
        self.assertFalse(options & {6, 7})
        self.assertNotIn('correct_recording_id', json.dumps(start))

    async def test_unfriend_replay_denied(self):
        start = await self.start(); row = (await self.rows(start['game_id']))[0]
        async with self.db.write() as session: await stop_interactions(session, 1, 2)
        with self.assertRaises(GuessError): await self.service.answer(101, start['game_id'], 0, row.correct_recording_id)

    async def test_real_auth_middleware_and_api_projection(self):
        from music_bot.chat_service import ChatService
        from music_bot.miniapp import create_app
        from tests.test_miniapp import TOKEN, signed
        workflow = type('Workflow', (), {'providers': AsyncMock()})()
        app = create_app(TOKEN, ChatService(self.db, AsyncMock()), workflow); app.freeze()
        async def call(method, path, payload=None, auth=True):
            request = make_mocked_request(method, path, headers={'X-Telegram-Init-Data': signed(101)} if auth else {})
            request.json = AsyncMock(return_value=payload)
            match = await app.router.resolve(request)
            request._match_info = match
            return await app.middlewares[0](request, match.handler)
        try:
            self.assertEqual((await call('POST', '/api/guess/start', {'friend_id': self.friend}, False)).status, 401)
            status = await call('GET', '/api/guess/status?friend_id='+self.friend)
            self.assertEqual(status.status, 200)
            prefs = await call('GET','/api/guess/preferences')
            self.assertEqual(prefs.status,200)
            self.assertEqual(json.loads(prefs.text)['quiet_start'],22)
            self.assertEqual((await call('POST','/api/guess/preferences',{'alerts':True,'quiet_start':8,'quiet_end':8})).status,400)
            self.assertEqual((await call('POST','/api/guess/nudge',{'friend_id':self.friend})).status,409)
            response = await call('POST', '/api/guess/start', {'friend_id': self.friend})
            self.assertEqual(response.status, 200, response.text)
            data = json.loads(response.text); self.assertNotIn('correct', response.text)
            row = (await self.rows(data['game_id']))[0]
            answer = await call('POST', '/api/guess/'+data['game_id']+'/answer', {'idx': 0, 'recording_id': row.correct_recording_id})
            self.assertEqual(answer.status, 200, answer.text)
            self.assertTrue(json.loads(answer.text)['correct'])
            self.assertEqual(answer.headers['Cache-Control'], 'no-store')
        finally:
            await app.cleanup()
