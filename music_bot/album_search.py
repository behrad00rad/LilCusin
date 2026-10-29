"""Bounded catalogue album browsing and sequential existing-service delivery."""
import asyncio
import json
import secrets
import time
from collections import OrderedDict

import aiohttp
from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup
from sqlalchemy import select
from .recognition import text
from .providers.common import TrackCandidate
from .catalog import canonical_track
from .fetch_models import AudioRequest

active=set()
controls=OrderedDict()
cache=OrderedDict()
capacity=asyncio.Semaphore(1)

async def catalogue(kind,value):
    key=(kind,str(value));now=time.monotonic()
    if key in cache and cache[key][0]>now:return cache[key][1]
    async with asyncio.timeout(12),capacity,aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        params=({'term':value,'entity':'album','attribute':'albumTerm','media':'music','limit':100} if kind=='search' else
            {'term':value,'entity':'musicArtist','media':'music','limit':30} if kind=='artists' else
            {'id':value,'entity':'album','limit':100} if kind=='artist_albums' else {'id':value,'entity':'song','limit':200})
        async with session.get('https://itunes.apple.com/'+('search' if kind in {'search','artists'} else 'lookup'),params=params,allow_redirects=False) as response:
            if response.status!=200:raise ValueError('Catalogue unavailable')
            data=bytearray()
            async for chunk in response.content.iter_chunked(32768):
                data.extend(chunk)
                if len(data)>1_000_000:raise ValueError('Response too large')
            rows=json.loads(data).get('results')
            if not isinstance(rows,list):raise ValueError('Invalid catalogue')
    cache[key]=(now+600,rows);cache.move_to_end(key)
    while len(cache)>100:cache.popitem(last=False)
    return rows

def albums(rows, query="", limit=5):
    result=[];seen=set()
    for row in rows:
        if not isinstance(row,dict):continue
        ident=row.get('collectionId')
        if (isinstance(ident,int) and ident>0 and ident not in seen and row.get('wrapperType')=='collection'
                and isinstance(row.get('artistName'),str) and isinstance(row.get('collectionName'),str)):
            seen.add(ident);result.append(dict(row))
    if query:
        from .matching import match_text
        q=match_text(query)
        result.sort(key=lambda r:(int(r.get('trackCount') or 0)<6,not match_text(r['collectionName']).startswith(q)))
    return result[:limit]

def tracks(rows,album_id):
    found={};album=None
    for row in rows:
        if not isinstance(row,dict) or row.get('collectionId')!=album_id:continue
        if row.get('wrapperType')=='collection':album=row
        if (row.get('kind')=='song' and isinstance(row.get('trackId'),int)
                and isinstance(row.get('artistName'),str) and isinstance(row.get('trackName'),str)):
            found.setdefault(row['trackId'],row)
    ordered=sorted(found.values(),key=lambda r:(int(r.get('discNumber') or 1),int(r.get('trackNumber') or 0)))
    return album,ordered

def issue(owner,kind,rows,query=None):
    now=time.monotonic()
    for token,c in list(controls.items()):
        if c['expires']<=now:controls.pop(token,None)
    token=secrets.token_hex(6)
    controls[token]={'owner':owner,'kind':kind,'rows':rows,'expires':now+86400,'message':None,'used':set(),'query':query}
    while len(controls)>100:controls.popitem(last=False)
    return token

def button(token,action,index,label):
    return InlineKeyboardButton(text=label[:64],callback_data=f'album:{token}:{action}:{index}')

async def search(message,service,query=None,artist_id=None):
    if (message.chat.type!='private' or not message.from_user or message.from_user.is_bot or message.sender_chat):return
    parts=(message.text or '').split(maxsplit=1) if query is None else ['/album',query]
    if len(parts)!=2 or not 1<=len(parts[1].strip())<=200:
        await message.answer(text('Search albums: /album Artist - Album','جست‌وجوی آلبوم: /album خواننده - نام آلبوم'));return
    pending=await message.answer(text('Searching albums…','دارم آلبوم‌ها رو جست‌وجو می‌کنم…'))
    try:
        query=parts[1].strip()
        rows=albums(await catalogue('artist_albums' if artist_id else 'search',artist_id or query),query,limit=50)
        if not rows:
            from .search_modes import result_keyboard
            token=issue(message.from_user.id,'modes',[],query)
            sent=await message.answer(text('No albums found. Try another search type.','آلبومی پیدا نشد. نوع جست‌وجو رو عوض کن.'),reply_markup=result_keyboard(token,0))
            controls[token]['message']=sent.message_id
            return
        token=issue(message.from_user.id,'search',rows,query)
        from .search_modes import result_keyboard
        markup=result_keyboard(token,0)
        sent=await message.answer(text('Choose an album:','یک آلبوم انتخاب کن:'),reply_markup=markup)
        controls[token]['message']=sent.message_id
    except (aiohttp.ClientError,TimeoutError,ValueError,TypeError):
        await message.answer(text('Album search is temporarily unavailable. Try again later.','جست‌وجوی آلبوم فعلاً در دسترس نیست. کمی بعد امتحان کن.'))
    finally:
        try:await pending.delete()
        except Exception:pass

async def enqueue(service,message,user,row):
    duration=row.get('trackTimeMillis')
    duration=duration/1000 if isinstance(duration,(float,int)) and duration>0 else None
    candidate=TrackCandidate(artist=row['artistName'][:200],title=row['trackName'][:200],source='itunes',
        album=(row.get('collectionName') or '')[:200] or None,duration=duration,artwork_url=row.get('artworkUrl100'))
    async with service.db.write() as session:
        track=await canonical_track(session,candidate)
        ident=track.id
    return await service.begin(message,user,ident)

async def receipt(service,request_id):
    async with service.db.sessions() as session:
        return await session.scalar(select(AudioRequest.state).where(AudioRequest.id==request_id))

async def batch(service,message,user,rows,pending):
    done=0
    try:
        async with asyncio.timeout(1800):
            for row in rows:
                await pending.edit_text(text(f'Album: {done}/{len(rows)} sent. Getting {row["trackName"][:100]}…',
                    f'آلبوم: {done} از {len(rows)} ارسال شد. دریافت {row["trackName"][:100]}…'),parse_mode=None,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text('Cancel','لغو'),callback_data='nav:cancel')]]))
                request_id=await enqueue(service,message,user,row)
                if not request_id:break
                async with asyncio.timeout(300):
                    while True:
                        state=await receipt(service,request_id)
                        if state=='done':done+=1;break
                        if state not in {'pending','sending','choice'}:break
                        await asyncio.sleep(2)
                if state!='done':break
        await pending.edit_text(text(f'Album: {done}/{len(rows)} sent. Use the track buttons for anything remaining.',
            f'آلبوم: {done} از {len(rows)} ارسال شد. برای بقیه، دکمهٔ هر آهنگ رو بزن.'))
    except asyncio.CancelledError:
        try:await pending.edit_text(text(f'Album cancelled. {done}/{len(rows)} sent.',f'آلبوم لغو شد. {done} از {len(rows)} ارسال شد.'))
        except Exception:pass
        raise
    except Exception:
        try:await pending.edit_text(text(f'Album paused. {done}/{len(rows)} confirmed. Check the current song before retrying.',
            f'آلبوم متوقف شد. ارسال {done} از {len(rows)} تأیید شد. قبل از تلاش دوباره، وضعیت آهنگ فعلی رو بررسی کن.'))
        except Exception:pass
    finally:
        getattr(service,'album_tasks',{}).pop(user,None)
        active.discard(user)

async def callback(query,service):
    import re
    match=re.fullmatch(r'album:([a-f0-9]{12}):(open|get|all):(\d{1,3})',query.data or '')
    c=controls.get(match[1]) if match else None
    if (not c or service is None or not query.from_user or query.from_user.is_bot or not query.message
            or query.message.chat.type!='private' or query.message.chat.id!=query.from_user.id
            or c['owner']!=query.from_user.id or c['message']!=query.message.message_id or c['expires']<=time.monotonic()):
        await query.answer(text('This album panel expired. Search again with /album.','این فهرست منقضی شده. با /album دوباره جست‌وجو کن.'));return
    await query.answer()
    action,index=match[2],int(match[3]);user=query.from_user.id
    if (action=='open' and c['kind']!='search' or action!='open' and c['kind']!='tracks'
            or index>=len(c['rows'])):return
    key=(action,index)
    if key in c['used']:
        await query.message.answer(text('Already requested. Use /album to start again.','قبلاً درخواست شده. برای شروع دوباره /album رو بزن.'));return
    if not hasattr(service,'album_tasks'):service.album_tasks={}
    if (user in service.album_tasks or user in active) and action!='open':
        await query.message.answer(text('An album is running. Use /cancel first.','دریافت آلبوم در حال اجراست. اول /cancel رو بزن.'));return
    c['used'].add(key)
    try:
        if action=='open':
            raw=c['rows'][index];album,ordered=tracks(await catalogue('lookup',raw['collectionId']),raw['collectionId'])
            if not ordered:
                await query.message.answer(text('No downloadable tracklist found.','فهرست آهنگ‌های این آلبوم پیدا نشد.'));return
            token=issue(user,'tracks',ordered[:40],c.get('query'))
            title=raw['collectionName'][:160]+' — '+raw['artistName'][:160]
            listing='\n'.join(f'{i+1}. {r["trackName"][:60]}' for i,r in enumerate(ordered[:40]))
            keyboard=[[button(token,'get',i,str(i+1)+'. '+r['trackName'])] for i,r in enumerate(ordered[:40])]
            complete=(len(ordered)<=40 and (not album or len(ordered)>=int(album.get('trackCount') or 0)))
            if complete:keyboard.insert(0,[button(token,'all',0,text('Download album','دریافت آلبوم'))])
            else:title+='\n'+text('Partial tracklist; download individual tracks.','فهرست ناقصه؛ آهنگ‌ها رو جداگانه دریافت کن.')
            from .chat_ui import safe_url
            cover=safe_url((album or raw).get('artworkUrl100'),artwork=True)
            if cover:
                try:
                    async with asyncio.timeout(8):
                        await query.message.answer_photo(cover.replace('100x100bb','600x600bb'),caption=title[:800],parse_mode=None)
                except Exception:pass
            if c.get('query'):
                from .search_modes import mode_row
                keyboard.append(mode_row('am:'+token,'albums'))
            from .search_modes import paging
            keyboard.extend(paging(token,0,more=False))
            sent=await query.message.answer(title+'\n\n'+listing+'\n\n'+text('Tracks use existing source checks and request limits. /cancel stops the album.',
                'آهنگ‌ها با بررسی منبع و محدودیت‌های فعلی دریافت می‌شن. /cancel آلبوم رو متوقف می‌کنه.'),parse_mode=None,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
            controls[token]['message']=sent.message_id
        elif action=='get':
            await enqueue(service,query.message,user,c['rows'][index])
        else:
            active.add(user)
            pending=await query.message.answer(text('Starting album… /cancel to stop.','دریافت آلبوم شروع می‌شه… برای لغو /cancel رو بزن.'))
            service.album_tasks[user]=asyncio.create_task(batch(service,query.message,user,list(c['rows']),pending))
    except Exception:
        if action=='all':active.discard(user)
        await query.message.answer(text('Album action could not complete. Check current deliveries before retrying.','این کار انجام نشد. قبل از تلاش دوباره، وضعیت دریافت‌های فعلی رو بررسی کن.'))
