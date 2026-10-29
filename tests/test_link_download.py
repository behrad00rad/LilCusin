import asyncio
import unittest
from pathlib import Path
from collections import OrderedDict
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,patch
from music_bot import link_download as subject
from music_bot.youtube_fetch import FetchError
from music_bot.recognition import Recognition

class LinkDownloadTests(unittest.IsolatedAsyncioTestCase):
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
    async def test_choice_before_download_and_video_once(self):
        service,message,pending=self.fixtures();roots=[]
        async def process(self,args,directory,alive):
            roots.append(directory);Path(directory,'post.mp4').write_bytes(b'video')
        with patch.object(subject.YouTubeFetcher,'process',process):
            query=await self.query(service,message,pending)
            self.assertFalse(roots);self.assertFalse(service.jobs)
            self.assertEqual(len(message.answer.call_args.kwargs['reply_markup'].inline_keyboard[0]),2)
            await subject.choose(query,service);await service.jobs[7]
            await subject.choose(query,service)
        message.answer_video.assert_awaited_once();self.assertFalse(Path(roots[0]).exists())
        self.assertFalse(service.recent)
    async def test_audio_only_no_video(self):
        service,message,pending=self.fixtures();commands=[]
        async def process(self,args,directory,alive):
            commands.append(args)
            Path(directory,'post.mp4' if args[0]!='ffmpeg' else 'audio.m4a').write_bytes(b'fixture')
        with patch.object(subject.YouTubeFetcher,'process',process):
            query=await self.query(service,message,pending,'audio');await subject.choose(query,service);await service.jobs[7]
        self.assertIn('bestaudio/best',commands[0]);self.assertIn('-vn',commands[1])
        message.answer_audio.assert_awaited_once();message.answer_video.assert_not_awaited()
    async def test_original_pictures_no_video_or_audio(self):
        service,message,pending=self.fixtures();message.text='https://vm.tiktok.com/id/'
        async def photos(url,directory,fetcher,alive,mode):
            self.assertEqual(mode,'pictures')
            files=[Path(directory,f'photo{i}.jpg') for i in range(2)]
            for p in files:p.write_bytes(b'jpg')
            return files
        with patch('music_bot.tiktok_slides.fetch',photos),patch.object(subject.YouTubeFetcher,'process',new_callable=AsyncMock) as process:
            await subject.run(service,7,message,pending,message.text,'pictures')
        process.assert_not_awaited();message.answer_media_group.assert_awaited_once()
        message.answer_video.assert_not_awaited();message.answer_audio.assert_not_awaited()
    async def test_picture_choice_only_for_confirmed_photo_post(self):
        service,message,pending=self.fixtures()
        message.text='https://www.tiktok.com/@user/photo/123'
        query=await self.query(service,message,pending,'pictures')
        self.assertEqual(len(message.answer.call_args.kwargs['reply_markup'].inline_keyboard[0]),3)
        service.link_recent.clear();message.text='https://www.tiktok.com/@user/video/123'
        await subject.submit(service,message)
        self.assertEqual(len(message.answer.call_args.kwargs['reply_markup'].inline_keyboard[0]),2)
        token=next(reversed(service.link_choices))
        query.data=f'linkmode:{token}:pictures'
        await subject.choose(query,service)
        self.assertFalse(service.jobs)
    async def test_recognize_uses_delivered_media_not_original(self):
        service,message,pending=self.fixtures();service.submit=AsyncMock()
        message.video=NS(file_size=1234);message.reply_to_message=NS(text='https://vm.tiktok.com/old/')
        message.model_copy=lambda update:NS(**update)
        query=NS(data='recmedia:7',from_user=message.from_user,message=message,answer=AsyncMock())
        await subject.recognize_download(query,service)
        self.assertIs(service.submit.call_args.args[1],message)
        service.submit.reset_mock();query.from_user=NS(id=8,is_bot=False)
        await subject.recognize_download(query,service);service.submit.assert_not_awaited()
    async def test_large_file_recognition_gives_audio_option(self):
        service,message,pending=self.fixtures();service.submit=AsyncMock()
        message.video=NS(file_size=30000000)
        query=NS(data='recmedia:7',from_user=message.from_user,message=message,answer=AsyncMock())
        await subject.recognize_download(query,service)
        service.submit.assert_not_awaited();self.assertIn('Audio only',message.answer.call_args.args[0])

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
    async def test_wrong_owner_expiry_message_and_cancel(self):
        service,message,pending=self.fixtures()
        query=await self.query(service,message,pending)
        token=next(iter(service.link_choices));query.from_user=NS(id=8,is_bot=False)
        await subject.choose(query,service);self.assertFalse(service.jobs)
        query.from_user=message.from_user;pending.message_id=100
        await subject.choose(query,service);self.assertFalse(service.jobs)
        pending.message_id=99
        service.link_choices[token]['expires']=0
        await subject.choose(query,service);self.assertFalse(service.jobs)
        service.link_recent.clear();await subject.submit(service,message)
        await Recognition.cancel(service,7);self.assertFalse(service.link_choices)
    async def test_cancel_inflight_and_repeated_taps(self):
        service,message,pending=self.fixtures();entered=asyncio.Event()
        async def process(*args):entered.set();await asyncio.Event().wait()
        with patch.object(subject.YouTubeFetcher,'process',process):
            query=await self.query(service,message,pending);await subject.choose(query,service)
            task=service.jobs[7];await entered.wait();await subject.choose(query,service)
            self.assertIs(service.jobs[7],task);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(service.jobs);pending.delete.assert_awaited_once()
    async def test_oversize_and_ambiguous_send_no_retry(self):
        service,message,pending=self.fixtures()
        async def large(self,args,directory,alive):
            with open(Path(directory,'post.mp4'),'wb') as f:f.truncate(subject.MAX_BYTES+1)
        with patch.object(subject.YouTubeFetcher,'process',large):
            await subject.run(service,7,message,pending,'abcdefghijk')
        message.answer_video.assert_not_awaited()
        async def valid(self,args,directory,alive):Path(directory,'post.mp4').write_bytes(b'video')
        message.answer_video.side_effect=TimeoutError()
        with patch.object(subject.YouTubeFetcher,'process',valid):
            await subject.run(service,7,message,pending,'abcdefghijk')
        message.answer_video.assert_awaited_once();self.assertIn('confirmed',message.answer.call_args.args[0])
    async def test_unsupported_url_and_disabled_service(self):
        service,message,pending=self.fixtures();message.text='http://127.0.0.1/private'
        await subject.submit(service,message);self.assertFalse(service.jobs)
        self.assertFalse(getattr(service,'link_choices',{}))
        query=NS(data='linkmode:abcdef123456:video',from_user=message.from_user,message=pending,answer=AsyncMock())
        await subject.choose(query,None);query.answer.assert_awaited_once()
