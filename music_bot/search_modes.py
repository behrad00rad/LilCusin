"""Switch the meaning of a query without reinterpreting a selected recording."""
import re
from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup
from .recognition import text
from . import album_search as albums
busy=set()

def mode_row(prefix,selected):
    return [InlineKeyboardButton(text=('✓ ' if mode==selected else '')+text(en,fa),callback_data=f'{prefix}:{mode}')
        for mode,en,fa in [('songs','Songs','آهنگ‌ها'),('artists','Artists','خواننده‌ها'),('albums','Albums','آلبوم‌ها')]]

async def query_panel(message,result,user,workflow):
    from .workflow import owned_submission
    async with workflow.database.sessions() as session:
        submission=await owned_submission(session,result.submission_id,user)
        query=submission.raw_text if submission.submission_type=='text' else None
    if not query:return
    token=albums.issue(user,'modes',[],query)
    sent=await message.answer(text('Search as:','نوع جست‌وجو:'),reply_markup=InlineKeyboardMarkup(inline_keyboard=[mode_row('am:'+token,'songs')]))
    albums.controls[token]['message']=sent.message_id

async def original(query,workflow):
    m=re.fullmatch(r'sm:(\d+):(\d+):(songs|artists|albums)',query.data or '')
    if m:
        from .workflow import active,owned_submission,FlowError
        from .models import IdentificationFlow
        async with workflow.database.sessions() as session:
            sub=await owned_submission(session,int(m[1]),query.from_user.id)
            flow=await session.get(IdentificationFlow,int(m[1]))
            active(flow,int(m[2]))
            if flow.prompt_message_id!=query.message.message_id:raise FlowError('stale')
            value=(' '.join(filter(None,(flow.corrected_artist,flow.corrected_title))) if flow.corrected_artist is not None or flow.corrected_title else sub.raw_text)
        return value,m[3],None
    m=re.fullmatch(r'(am|artist):([a-f0-9]{12}):([a-z]+|\d{1,2})',query.data or '')
    if not m:return None
    c=albums.controls.get(m[2])
    if (not c or c['owner']!=query.from_user.id or c['message']!=query.message.message_id
            or c['expires']<=__import__('time').monotonic()):return None
    if m[1]=='artist':
        index=int(m[3]) if m[3].isdigit() else -1
        if c['kind']!='artists' or not 0<=index<len(c['rows']):return None
        row=c['rows'][index]
        return row['artistName'],'albums',row['artistId']
    if m[3] not in {'songs','artists','albums'}:return None
    return c.get('query'),m[3],None

async def callback(query,workflow,submissions,enrichment,chat_service,get_song):
    if (not query.from_user or query.from_user.is_bot or not query.message or query.message.chat.type!='private'
            or query.message.chat.id!=query.from_user.id):
        await query.answer(text('This search belongs to another chat.','این جست‌وجو برای چت دیگه‌ایه.'));return
    await query.answer()
    if (query.data or '').startswith('mp:'):
        await page_callback(query)
        return
    user=query.from_user.id
    if user in busy:return
    busy.add(user)
    try:
        resolved=await original(query,workflow)
        if not resolved or not resolved[0]:raise ValueError('stale')
        value,mode,artist_id=resolved
        context=query.message.model_copy(update={'from_user':query.from_user,'sender_chat':None,'text':value,'reply_to_message':None})
        if mode=='albums':
            await albums.search(context,get_song,value,artist_id)
        elif mode=='artists':
            rows=await albums.catalogue('artists',value)
            found=[];seen=set()
            for row in rows:
                ident=row.get('artistId') if isinstance(row,dict) else None
                if isinstance(ident,int) and isinstance(row.get('artistName'),str) and ident not in seen:
                    found.append(row);seen.add(ident)
            found=found[:30];token=albums.issue(query.from_user.id,'artists',found,value)
            keyboard=result_keyboard(token,0).inline_keyboard
            sent=await context.answer(text('Choose an artist to browse albums:','برای دیدن آلبوم‌ها یک خواننده انتخاب کن:') if found else text('No artists found. Try another search type.','خواننده‌ای پیدا نشد. نوع جست‌وجو رو عوض کن.'),reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
            albums.controls[token]['message']=sent.message_id
        else:
            from .submissions import Submitter
            from .interactions import present
            saved=await submissions.submit_search(Submitter(query.from_user.id,getattr(query.from_user,'username',None),
                getattr(query.from_user,'full_name',None),getattr(query.from_user,'language_code',None)),value)
            pending=await context.answer(text('Searching songs…','دارم آهنگ‌ها رو جست‌وجو می‌کنم…'))
            result=await workflow.start(saved.id,query.from_user.id,fast=chat_service is not None)
            await present(context,result,query.from_user.id,workflow,enrichment,chat_service,status_message=pending)
    except Exception:
        await query.message.answer(text('Search could not complete. Try again or send a fresh query.','جست‌وجو انجام نشد. دوباره امتحان کن یا یک جست‌وجوی تازه بفرست.'))

    finally:
        busy.discard(user)

def paging(token,offset,more=True):
    c=albums.controls[token];row=[]
    if more and offset:row.append(InlineKeyboardButton(text=text('Previous','قبلی'),callback_data=f'mp:{token}:more:{max(0,offset-5)}'))
    if more and offset+5<len(c['rows']):row.append(InlineKeyboardButton(text=text('More','بیشتر'),callback_data=f'mp:{token}:more:{offset+5}'))
    rows=[row] if row else []
    rows.append([InlineKeyboardButton(text=text('Close','بستن'),callback_data=f'mp:{token}:close:0')])
    return rows

def result_keyboard(token,offset):
    c=albums.controls[token];artist=c['kind']=='artists'
    rows=[mode_row('am:'+token,'artists' if artist else 'albums')]
    for index in range(offset,min(offset+5,len(c['rows']))):
        r=c['rows'][index]
        rows.append([InlineKeyboardButton(text=(r['artistName'] if artist else r['collectionName']+' — '+r['artistName'])[:64],
            callback_data=f'artist:{token}:{index}' if artist else f'album:{token}:open:{index}')])
    rows.extend(paging(token,offset))
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def page_callback(query):
    m=re.fullmatch(r'mp:([a-f0-9]{12}):(more|close):(\d{1,3})',query.data or '')
    c=albums.controls.get(m[1]) if m else None
    if (not c or c['owner']!=query.from_user.id or c['message']!=query.message.message_id
            or c['expires']<=__import__('time').monotonic()):
        await query.message.answer(text('This search expired. Send a fresh query.','این جست‌وجو منقضی شده. دوباره جست‌وجو کن.'));return
    if m[2]=='close':
        albums.controls.pop(m[1],None)
        try:await query.message.delete()
        except Exception:
            try:await query.message.edit_reply_markup(reply_markup=None)
            except Exception:pass
        return
    offset=int(m[3])
    if c['kind'] not in {'search','artists'} or offset%5 or not 0<=offset<len(c['rows']):return
    try:await query.message.edit_reply_markup(reply_markup=result_keyboard(m[1],offset))
    except Exception:pass
