"""Isolated SQLite fixtures; no bot, network, audio or production database."""
import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from music_bot.database import Database
from music_bot.guess_game import GuessGame, GuessRound, GuessSettings, allow_guess, enabled
from music_bot.models import Track, User, utc_now
from music_bot.social import stop_interactions
from music_bot.taste_sharing import register_taste_sharing


class GuessDataTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / 'guess.sqlite3')
        await self.db.initialize()
        async with self.db.write() as session:
            session.add_all([User(id=i, telegram_user_id=100+i) for i in range(1, 4)])
            session.add_all([Track(id=i, title=f'Song {i}', artist='Fixture', metadata_source='fixture')
                             for i in range(1, 5)])

    async def asyncTearDown(self):
        await self.db.close()
        self.temp.cleanup()

    async def game(self, guesser=1, target=2, status='open'):
        async with self.db.write() as session:
            row = GuessGame(guesser_id=guesser, target_id=target, status=status,
                            finished_at=None if status == 'open' else utc_now())
            session.add(row)
            await session.flush()
            session.add(GuessRound(game_id=row.id, idx=0, correct_recording_id=1,
                                   option_ids=[2, 1, 4, 3]))
            return row.id

    async def test_flag_default_off(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(enabled())
        for value in ('1', 'true', 'ON'):
            with patch.dict(os.environ, {'GUESS_GAME': value}):
                self.assertTrue(enabled())

    async def test_default_on_and_persisted_opt_out(self):
        async with self.db.write() as session:
            self.assertTrue(await allow_guess(session, 2))
            self.assertFalse(await allow_guess(session, 2, False))
        async with self.db.sessions() as session:
            self.assertFalse(await allow_guess(session, 2))
        async with self.db.write() as session:
            self.assertTrue(await allow_guess(session, 2, True))
            with self.assertRaises(ValueError):
                await allow_guess(session, 2, 'true')

    async def test_one_open_per_direction_and_completed_history(self):
        await self.game()
        with self.assertRaises(IntegrityError):
            await self.game()
        await self.game(2, 1)
        await self.game(status='done')
        await self.game(status='expired')

    async def test_round_options_and_bounds(self):
        for options in ([1, 1, 2, 3], [1, 2, 3], [True, 2, 3, 4], [0, 2, 3, 4]):
            with self.assertRaises(ValueError):
                GuessRound(option_ids=options)
        game = await self.game()
        with self.assertRaises(IntegrityError):
            async with self.db.write() as session:
                session.add(GuessRound(game_id=game, idx=5, correct_recording_id=1,
                                       option_ids=[1, 2, 3, 4]))

    async def test_account_cascade_both_roles(self):
        for who in (1, 2):
            await self.game()
            async with self.db.write() as session:
                await allow_guess(session, who, True)
                await session.execute(delete(User).where(User.id == who))
            async with self.db.sessions() as session:
                self.assertEqual(await session.scalar(select(func.count()).select_from(GuessGame)), 0)
                self.assertEqual(await session.scalar(select(func.count()).select_from(GuessRound)), 0)
                self.assertIsNone(await session.get(GuessSettings, who))
            async with self.db.write() as session:
                session.add(User(id=who, telegram_user_id=100+who))

    async def test_unfriend_block_purge_pair_in_both_directions(self):
        await self.game()
        await self.game(2, 1, 'done')
        other = await self.game(1, 3)
        async with self.db.write() as session:
            await stop_interactions(session, 2, 1)
        async with self.db.sessions() as session:
            self.assertEqual(list(await session.scalars(select(GuessGame.id))), [other])
            self.assertEqual(await session.scalar(select(func.count()).select_from(GuessRound)), 1)
        async with self.db.write() as session:
            await stop_interactions(session, 1)
        async with self.db.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(GuessRound)), 0)

    async def test_opt_out_erases_target_games_not_guesses(self):
        await self.game()
        reverse = await self.game(2, 1)
        async with self.db.write() as session:
            await allow_guess(session, 2, False)
        async with self.db.sessions() as session:
            self.assertEqual(list(await session.scalars(select(GuessGame.id))), [reverse])

    async def test_additive_initialization_is_repeatable(self):
        game = await self.game()
        await self.db.initialize()
        async with self.db.sessions() as session:
            self.assertIsNotNone(await session.get(GuessGame, game))
            self.assertEqual(await session.scalar(select(func.count()).select_from(User)), 3)

    async def settings(self, payload=None):
        app = web.Application()
        async def body(request):
            return payload
        register_taste_sharing(app, SimpleNamespace(database=self.db), body)
        app.freeze()
        request = make_mocked_request('POST' if payload is not None else 'GET', '/api/taste-sharing')
        request['user'] = {'id': 102}
        match = await app.router.resolve(request)
        return json.loads((await match.handler(request)).text)

    async def test_settings_flag_and_boolean_validation(self):
        with patch.dict(os.environ, {'GUESS_GAME': '0'}):
            self.assertEqual(await self.settings(), {'enabled': False, 'guess_game': False})
            with self.assertRaises(web.HTTPBadRequest):
                await self.settings({'allow_guess': False})
        with patch.dict(os.environ, {'GUESS_GAME': '1'}):
            self.assertTrue((await self.settings())['allow_guess'])
            self.assertFalse((await self.settings({'allow_guess': False}))['allow_guess'])
            self.assertFalse((await self.settings())['allow_guess'])
            with self.assertRaises(web.HTTPBadRequest):
                await self.settings({'allow_guess': 'false'})

    async def test_forgetme_removes_game_rounds_and_setting(self):
        from music_bot.chat_service import ChatService
        await self.game()
        async with self.db.write() as session:
            await allow_guess(session, 1, True)
        await ChatService(self.db, AsyncMock()).forget(101)
        async with self.db.sessions() as session:
            self.assertIsNone(await session.get(User, 1))
            self.assertIsNone(await session.get(GuessSettings, 1))
            self.assertEqual(await session.scalar(select(func.count()).select_from(GuessGame)), 0)
            self.assertEqual(await session.scalar(select(func.count()).select_from(GuessRound)), 0)


if __name__ == '__main__':
    unittest.main()
