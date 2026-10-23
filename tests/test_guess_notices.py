"""Notification side effects are AsyncMock only; no Telegram or provider calls."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
import asyncio
from aiohttp import web

from sqlalchemy import select, delete, func
from tests import test_guess_service as fixtures
from music_bot.guess_notices import (GuessNotice, GuessPair, GuessAlertSettings,
    nudge, flush, quiet_until, settings, callback)
from music_bot.guess_game import GuessGame, allow_guess
from music_bot.models import User, Rating
from music_bot.social import SocialSettings, SocialBlock, stop_interactions
from music_bot.guess_service import GuessError

NOW=datetime(2026,10,24,9,tzinfo=timezone.utc)


class GuessNoticeTests(IsolatedAsyncioTestCase):
    start=fixtures.GuessServiceTests.start
    rows=fixtures.GuessServiceTests.rows
    async def finish(self,start=None):
        start=start or await self.start()
        for row in await self.rows(start['game_id']):
            result=await self.service.answer(101,start['game_id'],row.idx,row.correct_recording_id,human=True)
        return start,result
    asyncTearDown=fixtures.GuessServiceTests.asyncTearDown

    async def asyncSetUp(self):
        await fixtures.GuessServiceTests.asyncSetUp(self)
        clock=patch('music_bot.guess_notices.utc_now',return_value=NOW);clock.start();self.addCleanup(clock.stop)
        self.bot=AsyncMock()
        async with self.db.write() as session:
            session.add(SocialSettings(user_id=2,notifications=True))

    async def due(self):
        async with self.db.write() as session:
            for row in await session.scalars(select(GuessNotice).where(GuessNotice.state=='queued')):
                row.due_at=NOW-timedelta(seconds=1)

    async def send(self):
        await self.due();await flush(self.db,self.bot,'https://mini.example')

    async def test_finish_batch_idempotency_day_limit_and_no_song_leaks(self):
        first,_=await self.finish();second,_=await self.finish()
        final=(await self.rows(second['game_id']))[-1]
        await self.service.answer(101,second['game_id'],4,final.correct_recording_id)
        async with self.db.sessions() as session:
            row=await session.scalar(select(GuessNotice));self.assertEqual(row.games,2)
        with patch('music_bot.guess_notices.quiet_until',side_effect=[None,NOW+timedelta(hours=1)]):
            await self.send()
        self.bot.send_message.assert_not_awaited()
        await self.send();self.bot.send_message.assert_awaited_once()
        args=self.bot.send_message.call_args
        self.assertEqual(args.args[0],102);self.assertIn('5/5',args.args[1]);self.assertIn('2 games',args.args[1]);self.assertNotIn('song 1',args.args[1].lower())
        keys=args.kwargs['reply_markup'].inline_keyboard
        self.assertIn('guess=',keys[0][0].web_app.url);self.assertEqual(len(keys[1]),2)
        await self.finish();await self.send();self.assertEqual(self.bot.send_message.await_count,1)

    async def test_nudge_limit_quiet_hours_and_dynamic_remaining(self):
        async with self.db.write() as session:
            await session.execute(delete(Rating).where(Rating.user_id==2,Rating.track_id>2))
        self.assertTrue((await nudge(self.db,101,self.friend))['nudged'])
        self.assertTrue((await self.service.status(101,self.friend))['nudged'])
        with self.assertRaises(GuessError) as err:await nudge(self.db,101,self.friend)
        self.assertEqual(err.exception.status,429)
        night=NOW.replace(hour=21) # 00:30 Tehran
        with patch('music_bot.guess_notices.utc_now',return_value=night):
            await self.send()
        self.bot.send_message.assert_not_awaited()
        await self.send();self.assertIn('3 more songs',self.bot.send_message.call_args.args[1])
        async with self.db.write() as session:
            (await session.get(GuessPair,(1,2))).last_nudge=NOW-timedelta(days=4)
            await session.execute(delete(GuessNotice))
        await nudge(self.db,101,self.friend)

    async def test_block_unfriend_optout_and_existing_notification_permission(self):
        await self.finish()
        async with self.db.write() as session:session.add(SocialBlock(owner_id=2,target_id=1))
        await self.send();self.bot.send_message.assert_not_awaited()
        async with self.db.write() as session:
            await session.execute(delete(SocialBlock));await session.execute(delete(GuessNotice))
            (await session.get(SocialSettings,2)).notifications=False
        await self.finish();await self.send();self.bot.send_message.assert_not_awaited()
        async with self.db.write() as session:await allow_guess(session,2,False)
        async with self.db.sessions() as session:self.assertEqual(list(await session.scalars(select(GuessNotice))),[])
        async with self.db.write() as session:await stop_interactions(session,1,2)
        async with self.db.sessions() as session:self.assertEqual(list(await session.scalars(select(GuessPair))),[])

    async def test_ambiguous_send_not_retried_and_nonhuman_not_enqueued(self):
        start=await self.start()
        for row in await self.rows(start['game_id']):
            await self.service.answer(101,start['game_id'],row.idx,row.correct_recording_id,human=False)
        async with self.db.sessions() as session:self.assertIsNone(await session.scalar(select(GuessNotice)))
        await self.finish();self.bot.send_message.side_effect=RuntimeError('mock ambiguous')
        await self.send();await self.send();self.assertEqual(self.bot.send_message.await_count,1)
        async with self.db.sessions() as session:self.assertEqual((await session.scalar(select(GuessNotice))).state,'uncertain')

    async def test_mute_stop_ownership_settings_and_account_cascade(self):
        await self.finish();await self.send()
        async with self.db.sessions() as session:token=(await session.scalar(select(GuessNotice))).token
        query=SimpleNamespace(data='gg:m:'+token,from_user=SimpleNamespace(id=103,is_bot=False),message=SimpleNamespace(chat=SimpleNamespace(id=103,type='private')),answer=AsyncMock())
        await callback(query,SimpleNamespace(database=self.db))
        async with self.db.sessions() as session:self.assertFalse((await session.get(GuessPair,(1,2))).muted)
        query.from_user.id=query.message.chat.id=102
        await callback(query,SimpleNamespace(database=self.db))
        async with self.db.sessions() as session:self.assertTrue((await session.get(GuessPair,(1,2))).muted)
        query.data='gg:s:'+token;await callback(query,SimpleNamespace(database=self.db))
        self.assertFalse((await settings(self.db,102))['alerts'])
        with self.assertRaises(GuessError):await settings(self.db,102,{'alerts':True,'quiet_start':True,'quiet_end':8})
        with self.assertRaises(GuessError):await settings(self.db,102,{'alerts':True,'quiet_start':8,'quiet_end':8})
        async with self.db.write() as session:
            await session.execute(delete(Rating).where(Rating.user_id==2))
            await session.execute(delete(User).where(User.id==2))
        async with self.db.sessions() as session:
            for model in (GuessNotice,GuessPair,GuessAlertSettings,GuessGame):self.assertEqual(await session.scalar(select(func.count()).select_from(model)),0)

    def test_day_and_overnight_quiet_windows(self):
        self.assertIsNone(quiet_until(NOW))
        until=quiet_until(NOW.replace(hour=21));self.assertEqual(until.hour,8)
        self.assertIsNotNone(quiet_until(NOW,10,14))

    async def test_persian_notice_and_delayed_previous_day_cap(self):
        async with self.db.write() as session:
            (await session.get(User,2)).language_code='fa-IR'
        await self.finish();await self.send()
        self.assertIn('حدس',self.bot.send_message.call_args.args[1])
        async with self.db.write() as session:
            first=await session.scalar(select(GuessNotice))
            await session.delete(first)
            session.add(GuessNotice(guesser_id=1,target_id=2,invitation=self.friend,
                kind='finish',day='2026-10-23',score=2,due_at=NOW-timedelta(seconds=1)))
        await self.send();self.assertEqual(self.bot.send_message.await_count,1)

    async def test_notification_worker_startup_and_cleanup_are_bounded(self):
        from music_bot.guess_api import register_guess_api
        app=web.Application();started=asyncio.Event();stopped=asyncio.Event()
        async def fake_worker(*args):
            started.set()
            try:await asyncio.Event().wait()
            finally:stopped.set()
        register_guess_api(app,SimpleNamespace(database=self.db,social_bot=self.bot),AsyncMock())
        with patch('music_bot.guess_notices.worker',new=fake_worker):
            lifecycle=app.cleanup_ctx[0](app)
            await anext(lifecycle)
            await asyncio.wait_for(started.wait(),1)
            await lifecycle.aclose()
            self.assertTrue(stopped.is_set())
