import asyncio
import unittest
from collections import OrderedDict
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
from music_bot import link_download as subject
from music_bot.recognition import Recognition

class LinkRecognitionChoiceTests(unittest.IsolatedAsyncioTestCase):
    def fixtures(self):
        service=NS(jobs={},pending={},recent=OrderedDict(),admission=asyncio.Lock(),worker=asyncio.Semaphore(1),alive=AsyncMock(return_value=True))
        message=NS(chat=NS(type='private',id=7),from_user=NS(id=7,is_bot=False),message_id=11,sender_chat=None,
            text='https://youtu.be/abcdefghijk',answer=AsyncMock(),answer_video=AsyncMock(),answer_document=AsyncMock(),
            answer_audio=AsyncMock(),answer_photo=AsyncMock(),answer_media_group=AsyncMock())
        pending=NS(message_id=99,chat=message.chat,answer=message.answer,delete=AsyncMock())
        message.answer.return_value=pending
        return service,message,pending

    async def query(self,service,message,pending,mode='video'):
        await subject.submit(service,message)
        token=next(iter(service.link_choices))
        return NS(data=f'linkmode:{token}:{mode}',from_user=message.from_user,message=pending,answer=AsyncMock())

    async def test_recognize_option_uses_original_link_without_delivering_media(self):
        service,message,pending=self.fixtures()
        async def recognize(source):
            self.assertFalse(service.admission.locked())
            self.assertIs(source,message)
        service.submit=AsyncMock(side_effect=recognize)
        query=await self.query(service,message,pending,'recognize')
        markup=message.answer.call_args.kwargs['reply_markup']
        self.assertEqual(markup.inline_keyboard[-1][0].text,'Recognize music')
        with patch.object(subject,'run',new_callable=AsyncMock) as download:
            await asyncio.wait_for(subject.choose(query,service),timeout=1)
            await subject.choose(query,service)
        service.submit.assert_awaited_once_with(message)
        download.assert_not_awaited()
        message.answer_video.assert_not_awaited();message.answer_audio.assert_not_awaited()
        self.assertFalse(service.jobs)

    async def test_direct_recognition_keeps_owner_message_and_expiry_checks(self):
        service,message,pending=self.fixtures();service.submit=AsyncMock()
        query=await self.query(service,message,pending,'recognize')
        query.from_user=NS(id=8,is_bot=False)
        await subject.choose(query,service)
        service.submit.assert_not_awaited()
        query.from_user=message.from_user;pending.message_id=100
        await subject.choose(query,service);service.submit.assert_not_awaited()
        pending.message_id=99
        next(iter(service.link_choices.values()))['expires']=0
        await subject.choose(query,service);service.submit.assert_not_awaited()

    async def test_direct_recognition_uses_real_service_admission_without_deadlock(self):
        _,message,pending=self.fixtures()
        for key in ['audio','video','voice','video_note','document']:setattr(message,key,None)
        service=Recognition(NS(),NS(),enabled=True)
        service.run=AsyncMock()
        query=await self.query(service,message,pending,'recognize')
        await asyncio.wait_for(subject.choose(query,service),timeout=1)
        await service.jobs[7]
        self.assertEqual(service.run.await_args.args[-1],'abcdefghijk')
        self.assertIsNone(service.run.await_args.args[-2])
        await service.close()
