from datetime import timedelta
from types import SimpleNamespace as N
from unittest.mock import AsyncMock,patch
from sqlalchemy import select
from tests.support import ServiceTestCase
from music_bot.chat_service import ChatService
from music_bot.daily_pick import setting
from music_bot.monthly_pitch import send_pitch,pitch_text
from music_bot.models import User,ChatControl,utc_now
from music_bot.taste_setup import TasteSetup

class MonthlyPitchTests(ServiceTestCase):
 async def asyncSetUp(self):
  await super().asyncSetUp()
  self.chat=ChatService(self.database,None);await self.chat.ensure_user(self.user)
  await setting(self.database,123,True)
  async with self.database.sessions() as s:self.internal=await s.scalar(select(User.id))
  self.bot=N(get_chat_menu_button=AsyncMock(return_value=N(web_app=None)),send_message=AsyncMock(return_value=N(message_id=42)))
 async def test_once_30_days_then_eligible_again(self):
  now=utc_now()
  with patch('music_bot.monthly_pitch.utc_now',return_value=now):
   self.assertTrue(await send_pitch(self.database,self.bot,123,'en'))
   self.assertFalse(await send_pitch(self.database,self.bot,123,'en'))
  with patch('music_bot.monthly_pitch.utc_now',return_value=now+timedelta(days=29)):
   self.assertFalse(await send_pitch(self.database,self.bot,123,'en'))
  with patch('music_bot.monthly_pitch.utc_now',return_value=now+timedelta(days=31)):
   self.assertTrue(await send_pitch(self.database,self.bot,123,'en'))
  self.assertEqual(self.bot.send_message.await_count,2)
 async def test_taste_setup_avoids_pitch_and_optout_is_respected(self):
  async with self.database.write() as s:s.add(TasteSetup(user_id=self.internal,artist='Artist',completed=True))
  self.assertFalse(await send_pitch(self.database,self.bot,123,'en'))
  self.bot.send_message.assert_not_awaited()
  await setting(self.database,123,False)
  self.assertFalse(await send_pitch(self.database,self.bot,123,'en'))
 async def test_ambiguous_send_is_not_replayed_and_forget_removes_marker(self):
  self.bot.send_message.side_effect=TimeoutError()
  self.assertFalse(await send_pitch(self.database,self.bot,123,'en'))
  self.assertFalse(await send_pitch(self.database,self.bot,123,'en'))
  self.assertEqual(self.bot.send_message.await_count,1)
  await self.chat.forget(123)
  async with self.database.sessions() as s:self.assertIsNone(await s.scalar(select(ChatControl)))
 async def test_copy_is_honest_and_persian(self):
  self.assertNotIn('lately',pitch_text('en'));self.assertIn('/rate',pitch_text('en'))
  self.assertIn('سلیقه',pitch_text('fa'))
