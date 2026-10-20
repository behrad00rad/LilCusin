from unittest.mock import AsyncMock

from music_bot.i18n import language
from music_bot.interactions import candidate_keyboard
from music_bot.matching import encode_track
from music_bot.models import IdentificationFlow, utc_now
from music_bot.providers.common import TrackCandidate
from music_bot.search_pages import page_result
from music_bot.workflow import FlowError, Result
from tests.support import ServiceTestCase
from datetime import timedelta


class SearchPagesTests(ServiceTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        submission = await self.submissions.submit_text(self.user, 'Artist - Song')
        self.submission_id = submission.id
        self.rows = [TrackCandidate('Song ' + str(index), 'Artist', 'lastfm',
            external_ids={'lastfm': 'https://last.fm/song/' + str(index)}) for index in range(12)]
        async with self.database.write() as session:
            session.add(IdentificationFlow(submission_id=submission.id, state='candidates', revision=1,
                candidates=[encode_track(row) for row in self.rows], prompt_message_id=77,
                expires_at=utc_now() + timedelta(minutes=10)))

    async def test_pages_keep_original_choice_indices_without_provider_calls(self):
        self.providers.call = AsyncMock()
        result = await page_result(self.workflow, 123, 77, self.submission_id, 1, 5)
        keyboard = candidate_keyboard(result, chat=True, offset=5)
        choices = [row[0].callback_data for row in keyboard.inline_keyboard if row[0].callback_data.startswith('c:')]
        self.assertEqual(choices, [f'c:{self.submission_id}:1:{index}' for index in range(5, 10)])
        self.providers.call.assert_not_awaited()
        selected = await self.workflow.select(self.submission_id, 123, 1, 7)
        self.assertEqual(selected.title, 'Song 7')
        await self.workflow.rate(self.submission_id, 123, 'love')

    async def test_wrong_owner_message_revision_and_offset_rejected(self):
        for user, message, revision, offset in [(456, 77, 1, 5), (123, 78, 1, 5),
                (123, 77, 2, 5), (123, 77, 1, 15), (123, 77, 1, -5), (123, 77, 1, 1)]:
            with self.subTest(user=user, message=message, revision=revision, offset=offset):
                with self.assertRaises(FlowError):
                    await page_result(self.workflow, user, message, self.submission_id, revision, offset)

    async def test_expired_page_rejected(self):
        async with self.database.write() as session:
            flow = await session.get(IdentificationFlow, self.submission_id)
            flow.expires_at = utc_now() - timedelta(seconds=1)
        with self.assertRaises(FlowError):
            await page_result(self.workflow, 123, 77, self.submission_id, 1, 5)

    async def test_bilingual_navigation_and_last_page(self):
        result = Result('candidates', self.submission_id, 1, self.rows)
        for locale, label in [('en', 'More songs'), ('fa', 'بیشتر')]:
            context = language.set(locale)
            try:
                first = candidate_keyboard(result, chat=True)
                self.assertEqual(first.inline_keyboard[5][0].text, label)
                last = candidate_keyboard(result, chat=True, offset=10)
                self.assertEqual(len([row for row in last.inline_keyboard if row[0].callback_data.startswith('c:')]), 2)
                self.assertFalse(any(button.text == label for row in last.inline_keyboard for button in row))
            finally:
                language.reset(context)
