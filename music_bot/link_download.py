"""Owner-bound public-link output choices and bounded ephemeral downloads."""
import asyncio
import re
import secrets
import tempfile
import time
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyParameters
from .recognition import recognition_link, text
from .youtube_fetch import FetchError, YouTubeFetcher
from .tiktok_slides import SlideshowUnavailable

MAX_BYTES = 50_000_000
TIKTOK = {'tiktok.com','www.tiktok.com','vm.tiktok.com','vt.tiktok.com'}

def state(service):
    if not hasattr(service,'link_recent'):service.link_recent=OrderedDict()
    if not hasattr(service,'link_choices'):service.link_choices=OrderedDict()
    for token,entry in list(service.link_choices.items()):
        if entry['expires']<=time.monotonic():service.link_choices.pop(token,None)

async def submit(service,message):
    if (message.chat.type!='private' or not message.from_user or message.from_user.is_bot or message.sender_chat):return
    link=recognition_link(message.text)
    if not link:
        await message.answer(text('Send a supported public post link.','لینک یک پست عمومی بفرست.'))
        return
    from .tiktok_slides import photo_post
    has_pictures=await photo_post(link)
    async with service.admission:
        state(service);user=message.from_user.id;now=time.monotonic()
        if user in service.jobs or len(service.jobs)>=20 or now-service.link_recent.get(user,-3600)<30:
            await message.answer(text('Please wait for the current download, or use /cancel.','برای دانلود فعلی کمی صبر کن، یا /cancel رو بزن.'))
            return
        token=secrets.token_hex(6)
        modes=[('video',text('Video','ویدیو')),('audio',text('Audio only','فقط صدا'))]
        if has_pictures:modes.append(('pictures',text('Pictures only','فقط عکس‌ها')))
        markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=label,callback_data=f'linkmode:{token}:{mode}') for mode,label in modes],
            [InlineKeyboardButton(text=text('Recognize music','تشخیص آهنگ'),callback_data=f'linkmode:{token}:recognize')]])
        prompt=await message.answer(text('What would you like to do with this link? (Downloads up to 50 MB)',
            'با این لینک چی کار کنیم؟ (دانلود تا ۵۰ مگابایت)'),reply_markup=markup)
        service.link_choices[token]={'owner':user,'message':prompt.message_id,'source':message,'link':link,'expires':now+900,'used':set(),'allowed':{mode for mode,label in modes}|{'recognize'}}
        while len(service.link_choices)>100:service.link_choices.popitem(last=False)
        service.link_recent[user]=now;service.link_recent.move_to_end(user)
        while len(service.link_recent)>10000:service.link_recent.popitem(last=False)

async def choose(query,service):
    match=re.fullmatch(r'linkmode:([a-f0-9]{12}):(video|audio|pictures|recognize)',query.data or '')
    if (not match or service is None or not query.from_user or query.from_user.is_bot or not query.message
            or query.message.chat.type!='private' or query.message.chat.id!=query.from_user.id):
        await query.answer(text('This choice is no longer available.','این انتخاب دیگه در دسترس نیست.'));return
    await query.answer()
    async with service.admission:
        state(service);entry=service.link_choices.get(match[1]);user=query.from_user.id;mode=match[2]
        if not entry or entry['owner']!=user or entry['message']!=query.message.message_id:
            await query.message.answer(text('This choice expired. Send the link again.','این انتخاب منقضی شده. لینک رو دوباره بفرست.'));return
        if mode not in entry['allowed']:
            await query.message.answer(text('That format is not available for this post.','این قالب برای این پست در دسترس نیست.'));return
        if mode in entry['used']:
            await query.message.answer(text('That option was already requested. Choose another format, or send the link again.','این گزینه قبلاً درخواست شده. قالب دیگه‌ای انتخاب کن، یا لینک رو دوباره بفرست.'));return
        if user in service.jobs or len(service.jobs)>=20:
            await query.message.answer(text('Please wait for the current task, or use /cancel.','برای کار فعلی کمی صبر کن، یا /cancel رو بزن.'));return
        entry['used'].add(mode)
        if mode!='recognize':
            pending=await query.message.answer(text('Downloading your selection… Use /cancel to stop.','دارم گزینهٔ انتخابی رو دانلود می‌کنم… برای لغو /cancel رو بزن.'))
            service.pending[user]=pending
            service.jobs[user]=asyncio.create_task(run(service,user,entry['source'],pending,entry['link'],mode))
    if mode=='recognize':
        # Recognition owns admission too; release it before submitting the original
        # user link. No post/video/audio download is delivered as a prerequisite.
        await service.submit(entry['source'])

async def run(service,user,message,pending,link,mode='video'):
    fetcher=YouTubeFetcher(SimpleNamespace(timeout=150,max_bytes=MAX_BYTES,disk_bytes=110_000_000,max_duration=3600))
    sending=False
    try:
        async with asyncio.timeout(240),service.worker:
            with tempfile.TemporaryDirectory(prefix='lilcusin-link-') as directory:
                url=link if link.startswith('https://') else 'https://www.youtube.com/watch?v='+link
                generated=False;selected=None
                controls=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                    text=text('Recognize song','تشخیص آهنگ'),callback_data=f'recmedia:{user}')]])
                reply=ReplyParameters(message_id=message.message_id,allow_sending_without_reply=True)
                options={'reply_markup':controls,'reply_parameters':reply}
                if mode=='pictures':
                    from .tiktok_slides import fetch as fetch_slides
                    pictures=await fetch_slides(url,directory,fetcher,service.alive,mode='pictures')
                    sending=True
                    if len(pictures)==1:
                        await message.answer_photo(FSInputFile(pictures[0]),reply_parameters=reply)
                    else:
                        for offset in range(0,len(pictures),10):
                            batch=pictures[offset:offset+10]
                            if len(batch)==1:await message.answer_photo(FSInputFile(batch[0]),reply_parameters=reply)
                            else:await message.answer_media_group([InputMediaPhoto(media=FSInputFile(p)) for p in batch],reply_parameters=reply)
                    return
                try:
                    await fetcher.process(fetcher.base()+['--use-extractors',
                        'youtube.*,TikTok.*,vm.tiktok,Instagram.*,Pinterest.*,Twitter.*,Soundcloud.*,Vimeo',
                        '--max-filesize',str(MAX_BYTES),'--playlist-end','1',
                        '--match-filter','duration <=? 3600 & !is_live',
                        '-f',('bestaudio/best' if mode=='audio' else 'best[ext=mp4][filesize<50000000]/best[filesize<50000000]/best'),
                        '-o','post.%(ext)s','--',url],directory,service.alive)
                except FetchError:
                    if urlsplit(url).hostname not in TIKTOK:raise
                    for partial in Path(directory).glob('post.*'):
                        if partial.is_file():partial.unlink()
                    if mode=='pictures':raise SlideshowUnavailable('Original pictures and video unavailable.')
                    from .tiktok_slides import fetch as fetch_slides
                    selected=await fetch_slides(url,directory,fetcher,service.alive,mode=mode)
                    generated=mode=='video'
                files=[selected] if selected else [p for p in Path(directory).glob('post.*') if p.suffix.lower() in
                    {'.mp4','.webm','.mkv','.mov','.m4a','.mp3','.ogg','.wav','.flac','.aac'}]
                if len(files)!=1 or not 0<files[0].stat().st_size<=MAX_BYTES:raise FetchError('Unsupported media or size.')
                if mode=='audio':
                    audio=Path(directory)/'audio.m4a'
                    await fetcher.process(['ffmpeg','-nostdin','-v','error','-y','-protocol_whitelist','file,pipe',
                        '-i',str(files[0]),'-vn','-map','0:a:0','-c:a','aac','-b:a','128k',str(audio)],directory,service.alive)
                    if not audio.exists() or not 0<audio.stat().st_size<=MAX_BYTES:raise FetchError('Audio unavailable.')
                    sending=True
                    from .rating_links import bot_caption
                    await message.answer_audio(FSInputFile(audio),**options,
                        **await bot_caption(getattr(message, 'bot', None)))
                else:
                    if generated:options['caption']=text('Slideshow with its soundtrack (even slide timing).','اسلایدها همراه با صدا؛ زمان نمایش عکس‌ها یکسانه.')
                    sending=True
                    if files[0].suffix.lower()=='.mp4':await message.answer_video(FSInputFile(files[0]),supports_streaming=True,**options)
                    else:await message.answer_document(FSInputFile(files[0]),**options)
    except asyncio.CancelledError:raise
    except SlideshowUnavailable:
        await message.answer(text('This post did not expose the selected pictures or audio to the bot. Try again later, or send the files.',
            'این پست عکس‌ها یا صدای انتخابی رو در اختیار بات نذاشت. بعداً امتحان کن، یا فایل‌ها رو بفرست.'))
    except Exception:
        await message.answer(text('Delivery could not be confirmed. Check the chat before trying again.','نتونستم ارسال رو تأیید کنم. قبل از تلاش دوباره، چت رو بررسی کن.')
            if sending else text('Couldn’t download that format. The post must be public and the file under 50 MB. Try another option.',
                'دانلود این قالب انجام نشد. پست باید عمومی و فایل زیر ۵۰ مگابایت باشه. گزینهٔ دیگه‌ای رو امتحان کن.'))
    finally:
        service.jobs.pop(user,None);service.pending.pop(user,None)
        try:await pending.delete()
        except Exception:pass

async def recognize_download(query,service):
    owner=(query.data or '').removeprefix('recmedia:')
    if (not owner.isdecimal() or not query.from_user or query.from_user.is_bot or not query.message
            or query.message.chat.type!='private' or query.from_user.id!=int(owner) or query.message.chat.id!=int(owner)):
        await query.answer(text('This button belongs to another chat.','این دکمه برای چت دیگه‌ایه.'));return
    await query.answer()
    if service is None:return
    # Recognize the file already delivered, never re-fetch its original photo-post link.
    media=next((getattr(query.message,k,None) for k in ('audio','video','document') if getattr(query.message,k,None)),None)
    if not media:
        await query.message.answer(text('Choose Audio only, then tap Recognize song under the audio.','گزینهٔ فقط صدا رو انتخاب کن، بعد زیر فایل صوتی تشخیص آهنگ رو بزن.'));return
    if media.file_size is None or media.file_size>20_000_000:
        await query.message.answer(text('For recognition, choose Audio only and tap Recognize song under that smaller file (under 20 MB).',
            'برای تشخیص، فقط صدا رو انتخاب کن و زیر فایل کوچک‌تر (زیر ۲۰ مگابایت) تشخیص آهنگ رو بزن.'));return
    context=query.message.model_copy(update={'from_user':query.from_user,'sender_chat':None})
    await service.submit(context,query.message)
