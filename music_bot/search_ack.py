"""Acknowledge private search text before DB setup or mutation-lock waits."""
import asyncio
import logging

from aiogram import BaseMiddleware
from aiogram.types import Message

from .i18n import language, menu_action

logger = logging.getLogger('music_bot')
COPY = {
    'received': ('Searching…', 'دارم جست‌وجو می‌کنم…'),
    'slow': ('I received your search. Processing is taking longer than usual. You can cancel below.',
             'جست‌وجویت را دریافت کردم؛ پردازشش بیشتر از معمول طول کشیده. اگر خواستی از پایین لغوش کن.'),
    'waiting': ('Your search is still processing. I will update this message when it finishes.',
                'جست‌وجویت هنوز در حال پردازش است. وقتی تمام شود همین پیام را به‌روز می‌کنم.'),
    'failed': ('I could not finish this search. Please send it again or try /cancel.',
               'نتوانستم این جست‌وجو را تمام کنم. دوباره بفرست یا /cancel را امتحان کن.'),
}


class SearchReceipt:
    def __init__(self, message, code):
        self.message, self.code = message, code
        self.claimed, self.active, self.notifier = False, True, None

    def text(self, key):
        return COPY[key][1 if self.code == 'fa' else 0]

    def claim(self):
        self.claimed = True
        self.code = language.get()
        return self.message

    async def stop(self):
        self.active = False
        if self.notifier is not None:
            self.notifier.cancel()
            await asyncio.gather(self.notifier, return_exceptions=True)

    async def notify(self, delays):
        from .chat_ui import cancel_keyboard
        for delay, key in zip(delays, ('slow', 'waiting')):
            await asyncio.sleep(delay)
            if not self.active:
                return
            try:
                async with asyncio.timeout(4):
                    await self.message.edit_text(self.text(key), reply_markup=cancel_keyboard())
            except Exception:
                pass  # Status updates never fail the search.

    async def discard(self):
        try:
            async with asyncio.timeout(2):
                await self.message.delete()
        except Exception:
            pass


class SearchAcknowledgement(BaseMiddleware):
    def __init__(self, *, delays=(6, 10)):
        self.delays = delays

    async def __call__(self, handler, event, data):
        if (not isinstance(event, Message) or not event.from_user or event.from_user.is_bot
                or event.chat.type != 'private' or event.chat.id != event.from_user.id
                or not (event.text or '').strip() or event.text.lstrip().startswith('/')
                or menu_action(event.text) is not None):
            return await handler(event, data)
        from .chat_ui import cancel_keyboard
        code = (event.from_user.language_code or 'en').split('-')[0]
        try:
            async with asyncio.timeout(4):
                message = await event.answer(COPY['received'][1 if code == 'fa' else 0],
                                             reply_markup=cancel_keyboard())
        except Exception as error:
            logger.warning('Search acknowledgement unavailable (%s).', type(error).__name__)
            return await handler(event, data)  # Retain the handler's normal reply attempt.
        receipt = SearchReceipt(message, code)
        data['search_receipt'] = receipt
        receipt.notifier = asyncio.create_task(receipt.notify(self.delays))
        failed = cancelled = False
        try:
            return await handler(event, data)
        except asyncio.CancelledError:
            cancelled = True
            was_active = receipt.active
            await receipt.stop()
            if was_active:
                await receipt.discard()
            raise
        except Exception as error:
            failed = True
            logger.error('Search processing failed (%s); details omitted.', type(error).__name__)
            await receipt.stop()
            try:
                async with asyncio.timeout(4):
                    await receipt.message.edit_text(receipt.text('failed'), reply_markup=None)
            except Exception:
                pass
        finally:
            await receipt.stop()
            if not receipt.claimed and not failed and not cancelled:
                await receipt.discard()
