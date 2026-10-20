from unittest import TestCase

from music_bot.bot_copy import text as copy
from music_bot.chat_ui import card_keyboard, parse_control
from music_bot.i18n import language


class MusicUXTests(TestCase):
    def test_direct_ratings_selected_state_and_navigation_in_both_languages(self):
        for locale in ('en', 'fa'):
            context = language.set(locale)
            try:
                keyboard = card_keyboard('a' * 32, selected='like')
                actions = {parse_control(button.callback_data)[1]: button for row in keyboard.inline_keyboard for button in row}
                for value in ('love', 'like', 'neutral', 'dislike'):
                    self.assertIn(value, actions)
                self.assertTrue(actions['like'].text.startswith('✓'))
                self.assertFalse(actions['love'].text.startswith('✓'))
                self.assertNotIn('rate', actions)
                self.assertEqual(actions['get'].text, copy('get'))
                for value in ('next', 'more', 'versions', 'save', 'known', 'notforme'):
                    self.assertIn(value, actions)
                self.assertEqual([len(row) for row in keyboard.inline_keyboard[2:4]], [2, 2])
            finally:
                language.reset(context)
