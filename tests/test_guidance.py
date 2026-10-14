import asyncio
import string
from unittest import TestCase
from unittest.mock import AsyncMock,patch
from aiogram.types import Message
from sqlalchemy import select
from music_bot import messages as M
from music_bot.chat_service import ChatService
from music_bot.guidance import LanguageMiddleware, show_guide
from music_bot.i18n import language,tr,CATALOGUE,menu_action
from music_bot.preferences import preferences,UserPreferences,normalize_language
from music_bot.submissions import Submitter
from tests.support import ServiceTestCase

class TranslationTests(TestCase):
    def test_all_languages_have_matching_keys_and_placeholders(self):
        parser=string.Formatter()
        fields=lambda text:{name for _,name,_,_ in parser.parse(text) if name}
        for code,strings in CATALOGUE.items():
            self.assertEqual(set(strings),set(CATALOGUE['en']),code)
            for key,text in strings.items():self.assertEqual(fields(text),fields(CATALOGUE['en'][key]),(code,key))

    def test_telegram_auto_language_and_localized_menu(self):
        self.assertEqual(normalize_language('fa-IR'),'fa')
        self.assertEqual(normalize_language('unsupported'),'en')
        for code in CATALOGUE:
            context=language.set(code)
            try:
                self.assertEqual(menu_action(M.MENU_SEND),'send')
                self.assertEqual(M.rating_label('love',None),'♥ '+tr('love'))
                self.assertNotIn('{',M.text_received('Artist','Title'))
            finally:language.reset(context)

class PreferenceTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.chat=ChatService(self.database,AsyncMock())
        await self.chat.ensure_user(Submitter(123,language_code='fa'))

    async def test_manual_language_persists_across_telegram_language_changes(self):
        self.assertEqual((await preferences(self.database,123))['language'],'fa')
        await preferences(self.database,123,language='de',ui_done=True)
        await self.chat.ensure_user(Submitter(123,language_code='en'))
        result=await preferences(self.database,123)
        self.assertEqual(result['language'],'de');self.assertTrue(result['ui_guide_done'])
        self.assertFalse(result['bot_guide_seen'])
        await self.chat.forget(123)
        async with self.database.sessions() as session:self.assertIsNone(await session.scalar(select(UserPreferences)))

    async def test_first_message_gets_guide_once_and_keeps_original_submission(self):
        middleware=LanguageMiddleware(self.database)
        message=Message.model_validate({'message_id':1,'date':1700000000,'chat':{'id':123,'type':'private'},
            'from':{'id':123,'is_bot':False,'first_name':'Test','language_code':'fa'},'text':'Radiohead - Creep'})
        handler=AsyncMock()
        with patch('aiogram.types.Message.answer',new_callable=AsyncMock) as answer:
            await middleware(handler,message,{'chat_service':self.chat})
            self.assertIn(CATALOGUE['fa']['setup_q1'],answer.call_args.args[0])
            self.assertEqual(handler.await_count,1)
            await middleware(handler,message,{'chat_service':self.chat})
            self.assertEqual(answer.await_count,1)
        self.assertEqual(language.get(),'en')

    async def test_concurrent_languages_do_not_leak(self):
        async def render(code):
            context=language.set(code)
            try:
                await asyncio.sleep(0)
                return M.MENU_SEND
            finally:language.reset(context)
        a,b=await asyncio.gather(render('fa'),render('de'))
        self.assertEqual(a,CATALOGUE['fa']['bot_MENU_SEND']);self.assertEqual(b,CATALOGUE['de']['bot_MENU_SEND'])

    async def test_cancelled_grant_cannot_be_renewed_after_account_recreation(self):
        from music_bot.workflow import FlowError
        token=await self.chat.create_control(123,kind='miniapp')
        await self.chat.forget(123)
        await self.chat.ensure_user(Submitter(123))
        with self.assertRaises(FlowError):
            await self.chat.create_control(123,kind='miniapp',expected_token=token)

    async def test_channel_notifications_use_owner_language(self):
        from music_bot.channel_handlers import owner_language
        await preferences(self.database,123,language='fa')
        async with owner_language(self.chat,123):
            self.assertEqual(M.CHANNEL_STATUSES['connected'],CATALOGUE['fa']['connected'])
        self.assertEqual(language.get(),'en')
