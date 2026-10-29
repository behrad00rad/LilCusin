from datetime import timedelta
from unittest.mock import patch
from sqlalchemy import select

from tests.support import ServiceTestCase
from music_bot.chat_service import ChatService
from music_bot.models import ChatControl, IdentificationFlow, utc_now
from music_bot.workflow import Result, FlowError, active
from music_bot import album_search


class SearchLifetimeTests(ServiceTestCase):
    async def test_song_result_binding_remains_valid_next_day_and_keeps_ownership(self):
        submission=await self.submissions.submit_text(self.user,'Artist - Song')
        async with self.database.write() as session:
            session.add(IdentificationFlow(submission_id=submission.id,state='candidates',revision=1,
                expires_at=utc_now()+timedelta(minutes=5)))
        now=utc_now()
        with patch('music_bot.workflow.utc_now',return_value=now):
            await self.workflow.bind_candidates(Result('candidates',submission.id,1),123,77)
        async with self.database.sessions() as session:
            flow=await session.get(IdentificationFlow,submission.id)
            self.assertEqual(flow.expires_at,now+timedelta(days=1))
            with patch('music_bot.workflow.utc_now',return_value=now+timedelta(hours=23)):
                active(flow,1)
            with patch('music_bot.workflow.utc_now',return_value=now+timedelta(hours=25)):
                with self.assertRaises(FlowError):active(flow,1)
        with self.assertRaises(FlowError):
            await self.workflow.bind_candidates(Result('candidates',submission.id,1),456,77)

    async def test_browsing_cards_last_a_day_but_confirmations_still_short(self):
        chat=ChatService(self.database,None)
        await chat.ensure_user(self.user)
        now=utc_now()
        with patch('music_bot.chat_service.utc_now',return_value=now):
            tokens={kind:await chat.create_control(123,kind=kind) for kind in ['list','card','rating','forget']}
        async with self.database.sessions() as session:
            for kind,token in tokens.items():
                row=await session.get(ChatControl,token)
                self.assertEqual(row.expires_at-now,timedelta(minutes=30) if kind=='forget' else timedelta(days=1))

    async def test_more_than_twenty_cards_do_not_evict_recent_searches(self):
        chat=ChatService(self.database,None)
        await chat.ensure_user(self.user)
        tokens=[await chat.create_control(123,kind='card') for _ in range(22)]
        async with self.database.sessions() as session:
            self.assertIsNotNone(await session.get(ChatControl,tokens[0]))

    async def test_album_artist_menus_have_24_hour_lifetime(self):
        previous=album_search.controls.copy()
        try:
            album_search.controls.clear()
            with patch.object(album_search.time,'monotonic',return_value=100):
                token=album_search.issue(123,'artists',[],query='Artist')
            self.assertEqual(album_search.controls[token]['expires'],86500)
            with patch.object(album_search.time,'monotonic',return_value=100+23*3600):
                album_search.issue(456,'albums',[])
                self.assertIn(token,album_search.controls)
            with patch.object(album_search.time,'monotonic',return_value=100+25*3600):
                album_search.issue(456,'albums',[])
                self.assertNotIn(token,album_search.controls)
        finally:
            album_search.controls.clear();album_search.controls.update(previous)
