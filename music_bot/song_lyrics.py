"""Bounded on-demand lyrics; separate from lyric-phrase discovery."""
import asyncio
import json
import re
import time
from collections import OrderedDict

import aiohttp
from aiogram.types import BufferedInputFile
from .matching import match_text
from .recognition import text

cache = OrderedDict()
recent = OrderedDict()
capacity = asyncio.Semaphore(1)
retry_after = 0

async def lookup(artist, title):
    global retry_after
    key = (match_text(artist), match_text(title))
    now = time.monotonic()
    cached = cache.get(key)
    if cached and cached[0] > now:
        cache.move_to_end(key)
        return cached[1]
    if now < retry_after or capacity.locked():
        return ('unavailable', None)
    try:
        async with capacity, aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
            async with session.get('https://lrclib.net/api/get',
                    params={'artist_name':artist, 'track_name':title},
                    headers={'User-Agent':'LilCusin/1.0 (Telegram music bot)'}, allow_redirects=False) as response:
                if response.status == 429:
                    try: delay=float(response.headers.get('Retry-After','60'))
                    except ValueError: delay=60
                    retry_after = time.monotonic()+min(3600,max(1,delay))
                    return ('unavailable', None)
                if response.status == 404:
                    result = ('missing', None)
                elif response.status != 200:
                    return ('unavailable', None)
                else:
                    raw=bytearray()
                    async for chunk in response.content.iter_chunked(16384):
                        raw.extend(chunk)
                        if len(raw)>262144:
                            return ('unavailable', None)
                    data=json.loads(raw)
                    if (not isinstance(data,dict) or not isinstance(data.get('artistName'),str)
                            or not isinstance(data.get('trackName'),str)): return ('unavailable',None)
                    if (match_text(data.get('artistName') or '') != key[0]
                            or match_text(data.get('trackName') or '') != key[1]):
                        result=('missing',None)
                    elif data.get('instrumental') is True:
                        result=('instrumental',None)
                    elif isinstance(data.get('plainLyrics'),str) and 0<len(data['plainLyrics'].strip())<=50000:
                        result=('found',data['plainLyrics'].strip())
                    else:
                        result=('missing',None)
        cache[key]=(time.monotonic()+(3600 if result[0]=='found' else 300),result)
        cache.move_to_end(key)
        while len(cache)>128: cache.popitem(last=False)
        return result
    except (aiohttp.ClientError,TimeoutError,ValueError,TypeError):
        return ('unavailable',None)

async def show(message, service=None, payload=None):
    if (message.chat.type!='private' or not message.from_user or message.from_user.is_bot
            or message.sender_chat): return
    user=message.from_user.id;now=time.monotonic()
    if now-recent.get(user,-100)<5:
        await message.answer(text('Give me a moment before trying lyrics again.', 'برای درخواست دوبارهٔ متن آهنگ، چند لحظه صبر کن.'))
        return
    recent[user]=now;recent.move_to_end(user)
    while len(recent)>2000: recent.popitem(last=False)
    artist=title=None
    if payload and re.fullmatch(r'lyrics_[1-9][0-9]{0,17}',payload) and service is not None:
        track=await service.track(int(payload[7:]))
        if track:
            artist=track.display_artist or track.artist
            title=track.display_title or track.title
    elif payload is None:
        reply=message.reply_to_message
        audio=getattr(reply,'audio',None) if reply else None
        if audio:
            artist,title=audio.performer,audio.title
        if not artist or not title:
            parts=(message.text or '').split(maxsplit=1)
            query=parts[1] if len(parts)==2 else ''
            pair=re.split(r'\s+[—–-]\s+',query,maxsplit=1)
            if len(pair)==2: artist,title=pair
    if not artist or not title or len(artist)>200 or len(title)>300:
        await message.answer(text('Reply to a song with /lyrics, or use /lyrics Artist - Title.',
            'روی آهنگ /lyrics رو ریپلای کن، یا بنویس: /lyrics خواننده - نام آهنگ'))
        return
    pending=await message.answer(text('Looking for lyrics…','دارم متن آهنگ رو پیدا می‌کنم…'))
    try:
        state,lyrics=await lookup(artist.strip(),title.strip())
        if state=='found':
            header=artist+' — '+title+'\n\n'
            if len((header+lyrics).encode('utf-16-le'))//2<=3500:
                await message.answer(header+lyrics+'\n\nSource: LRCLIB',parse_mode=None)
            else:
                await message.answer_document(BufferedInputFile((header+lyrics+'\n\nSource: LRCLIB').encode('utf-8'),filename='lyrics.txt'),
                    caption=text('Lyrics · LRCLIB','متن آهنگ · LRCLIB'),parse_mode=None)
        elif state=='instrumental':
            await message.answer(text('This recording is listed as instrumental (no lyrics).','این نسخه بی‌کلام ثبت شده و متنی نداره.'))
        elif state=='missing':
            await message.answer(text('No matching lyrics found for this song.','متن این آهنگ پیدا نشد.'))
        else:
            await message.answer(text('Lyrics are temporarily unavailable. Please try again later.','سرویس متن آهنگ فعلاً در دسترس نیست. کمی بعد دوباره امتحان کن.'))
    finally:
        try: await pending.delete()
        except Exception: pass
