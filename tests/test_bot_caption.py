import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

from music_bot.rating_links import audio_caption, bot_caption


class BotCaptionTests(unittest.IsolatedAsyncioTestCase):
    def bot(self):
        return NS(me=AsyncMock(return_value=NS(username='LilCusinBot')))

    def linked_text(self, data, entity):
        raw = data['caption'].encode('utf-16-le')
        return raw[entity.offset * 2:(entity.offset + entity.length) * 2].decode('utf-16-le')

    async def test_compact_links_use_correct_unicode_offsets(self):
        data = await audio_caption(self.bot(), 42, compact=True)
        self.assertEqual(data['caption'], '⭐ rate  📝 lyrics  🦉 lilcusin')
        self.assertEqual([self.linked_text(data,e) for e in data['caption_entities']], ['⭐ rate','📝 lyrics','🦉 lilcusin'])
        self.assertEqual([e.url for e in data['caption_entities']], [
            'https://t.me/LilCusinBot?start=rate_42', 'https://t.me/LilCusinBot?start=lyrics_42', 'https://t.me/LilCusinBot'])

    async def test_normal_and_persian_song_captions(self):
        for locale in ['en','fa']:
            data = await audio_caption(self.bot(), 9, locale=locale)
            self.assertTrue(data['caption'].endswith('🦉 lilcusin'))
            self.assertNotIn('\n', data['caption'])
            self.assertEqual([self.linked_text(data,e) for e in data['caption_entities']], ['⭐ rate','📝 lyrics','🦉 lilcusin'])

    async def test_downloaded_audio_has_bot_link_without_inventing_song_identity(self):
        data = await bot_caption(self.bot())
        self.assertEqual(data['caption'], '🦉 lilcusin')
        self.assertEqual(len(data['caption_entities']), 1)
        self.assertEqual(self.linked_text(data,data['caption_entities'][0]), '🦉 lilcusin')

    async def test_missing_or_invalid_identity_keeps_command_fallback(self):
        for bot in [None, NS(me=AsyncMock(return_value=NS(username='invalid/user'))), NS(me=AsyncMock(side_effect=TimeoutError()))]:
            data = await audio_caption(bot, 1, compact=True)
            self.assertTrue(data['caption'].endswith('🦉 lilcusin'))
            self.assertNotIn('caption_entities', data)

    async def test_lilcusin_command_routes_to_private_bot_welcome(self):
        from datetime import datetime, UTC
        from aiogram.types import Message, Chat, User
        from music_bot.handlers import router, start
        message = Message(message_id=1, date=datetime.now(UTC), chat=Chat(id=123, type='private'),
            from_user=User(id=123, first_name='Fixture', is_bot=False), text='/lilcusin')
        matched = False
        for handler in router.message.handlers:
            if handler.callback is start:
                accepted, _ = await handler.check(message, bot=self.bot())
                matched = matched or accepted
        self.assertTrue(matched)
