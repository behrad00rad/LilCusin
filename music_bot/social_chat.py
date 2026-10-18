"""Private bot UI for comparisons, swaps and interaction controls."""
import os
import re
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton as Button, ForceReply, Message
from sqlalchemy import select, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base, User
from .social import Social, user_id
from .i18n import tr
from .taste_cards import CardError


class SwapPrompt(Base):
    __tablename__='social_note_prompts'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    swap: Mapped[str] = mapped_column(ForeignKey('song_swaps.token',ondelete='CASCADE'))
    message_id: Mapped[int]


def keyboard(rows): return InlineKeyboardMarkup(inline_keyboard=rows)
def button(key,data): return Button(text=tr(key),callback_data=data)
def song_text(songs): return '\n'.join('• '+song['artist'][:70]+' — '+song['title'][:90] for song in songs) or tr('social_none')


async def compare(message,chat,actor,token):
    result=await Social(chat.database).compare(actor,token)
    text=tr('social_compare_title',name=result['other']['nickname'])+'\n\n'+tr('social_compare_scope')
    if result['sparse']: text+='\n\n'+tr('social_sparse')
    text+='\n\n'+tr('social_shared_songs')+'\n'+song_text(result['shared_songs'])
    text+='\n\n'+tr('social_shared_artists')+'\n'+(', '.join(result['shared_artists']) or tr('social_none'))
    text+='\n\n'+tr('social_only_you')+'\n'+song_text(result['only_first'])
    text+='\n\n'+tr('social_only_other')+'\n'+song_text(result['only_second'])
    await message.answer(text,parse_mode=None,reply_markup=keyboard([
        [button('social_swap','sc:choose:'+token)],
        [button('social_block','sc:block:'+token),button('social_report','sc:report:'+token)],
        [button('invite_revoke','ci:revoke:'+token)]]))


async def choices(message,chat,actor,token,reply_to=None):
    songs=await Social(chat.database).choices(actor,token,reply_to)
    prefix='ss:pickback:'+reply_to if reply_to else 'sc:pick:'+token
    rows=[[Button(text=(song['artist']+' — '+song['title'])[:90],callback_data=prefix+':'+str(song['id']))] for song in songs]
    await message.answer(tr('social_choose'),reply_markup=keyboard(rows))


async def show(message,chat,actor,token):
    swap=await Social(chat.database).read(actor,token)
    text=tr('social_from' if swap['role']=='recipient' else 'social_to',name=swap['partner'])+'\n\n'+song_text([swap['song']])
    if swap['note']: text+='\n\n'+swap['note']
    rows=[]
    if swap['state']=='draft':
        rows=[[button('social_note','ss:note:'+token),button('social_send','ss:send:'+token)],
              [button('card_cancel','ss:cancel:'+token)]]
        text+='\n\n'+tr('social_draft')
    else:
        if swap['role']=='recipient':
            rows.append([button('social_unsave' if swap['saved'] else 'social_save','ss:'+('unsave' if swap['saved'] else 'save')+':'+token),button('social_love','ss:love:'+token)])
            rows.append([button('social_reply','ss:reply:'+token)])
        else:
            text+='\n\n'+tr('social_saved_feedback' if swap['saved'] else 'social_sent')
            if swap['loved']: text+='\n'+tr('social_loved_feedback')
            rows.append([button('social_remind','ss:remind:'+token)])
        rows.extend([[button('get_song','ss:get:'+token)],[button('social_block','sc:block:'+swap['invitation']),button('social_report','ss:report:'+token)],
                     [button('social_delete','ss:delete:'+token)]])
        text+='\n\n'+tr('social_unavailable_audio')
    await message.answer(text,parse_mode=None,reply_markup=keyboard(rows))


async def inbox(message,chat,actor):
    rows=await Social(chat.database).inbox(actor)
    keys=[[Button(text=(row['partner']+' · '+row['song']['title']+(' · '+tr('social_saved_feedback') if row['saved'] else ''))[:100],callback_data='ss:view:'+row['token'])] for row in rows]
    keys.append([button('social_settings','sc:settings')])
    await message.answer(tr('social_inbox') if rows else tr('social_inbox_empty'),reply_markup=keyboard(keys))


async def settings(message,chat,actor):
    result=await Social(chat.database).settings(actor)
    rows=[[button('social_notices_off' if result['notifications'] else 'social_notices_on','sc:notices:'+('off' if result['notifications'] else 'on'))]]
    for item in result['blocks']:
        rows.append([Button(text=(tr('social_unblock')+' · '+item['nickname'])[:100],callback_data='sc:unblock:'+item['handle'])])
    await message.answer(tr('social_settings_scope'),reply_markup=keyboard(rows))


async def saved(message,chat,actor):
    from .social import SavedSong
    from .models import Track
    async with chat.database.sessions() as session:
        internal=await user_id(session,actor)
        tracks=(await session.scalars(select(Track).join(SavedSong).where(SavedSong.user_id==internal).order_by(SavedSong.created_at.desc()).limit(50))).all()
    if not tracks: await message.answer(tr('social_no_saves'));return
    for track in tracks:
        await message.answer(song_text([dict(artist=track.artist,title=track.title)]),parse_mode=None,
            reply_markup=keyboard([[button('social_unsave','ss:forgetsave:'+str(track.id))]]))


async def note_reply(message,chat):
    if message.reply_to_message is None: return False
    async with chat.database.write() as session:
        actor=await user_id(session,message.from_user.id)
        row=await session.get(SwapPrompt,actor)
        if row is None or row.message_id!=message.reply_to_message.message_id: return False
        token=row.swap;await session.delete(row)
    try:
        await Social(chat.database).act(message.from_user.id,token,'note',message.text)
        await show(message,chat,message.from_user.id,token)
    except CardError as error: await message.answer(tr(str(error)))
    return True


async def callback(query,chat_service,get_song=None):
    if not isinstance(query.message,Message) or query.message.chat.type!='private' or query.message.chat.id!=query.from_user.id or query.from_user.is_bot:
        await query.answer(tr('social_unavailable'));return
    await query.answer()
    from .submissions import Submitter
    await chat_service.ensure_user(Submitter(query.from_user.id,query.from_user.username,query.from_user.full_name,query.from_user.language_code))
    data=query.data or '';actor=query.from_user.id;service=Social(chat_service.database)
    try:
        if data=='sc:settings': await settings(query.message,chat_service,actor);return
        if data in {'sc:notices:on','sc:notices:off'}:
            await service.settings(actor,data.endswith(':on'));await settings(query.message,chat_service,actor);return
        parts=data.split(':')
        if len(parts) not in {3,4}: raise CardError('social_invalid')
        kind,action,token=parts[:3]
        if len(parts)==4:
            if action not in {'pick','pickback'} or not re.fullmatch(r'[1-9][0-9]{0,17}',parts[3]): raise CardError('social_invalid')
            reply_to=token if action=='pickback' else None
            invitation=(await service.read(actor,token))['invitation'] if reply_to else token
            row=await service.draft(actor,invitation,int(parts[3]),reply_to)
            await show(query.message,chat_service,actor,row['token']);return
        if kind=='sc':
            if action=='compare': await compare(query.message,chat_service,actor,token)
            elif action=='choose': await choices(query.message,chat_service,actor,token)
            elif action in {'block','unblock'}:
                await service.relationship(actor,token,action);await query.message.answer(tr('social_'+action+'_done'))
            elif action=='report':
                await query.message.answer(tr('social_report_reason'),reply_markup=keyboard([[button('social_reason_'+reason,'sc:r'+reason+':'+token)] for reason in ['spam','harassment','unsafe','other']]))
            elif action.startswith('r'):
                await service.relationship(actor,token,'report',action[1:]);await query.message.answer(tr('social_report_done'))
            else: raise CardError('social_invalid')
        elif kind=='ss':
            if action=='forgetsave':
                if not token.isdigit(): raise CardError('social_invalid')
                await service.remove_save(actor,int(token));await query.message.answer(tr('social_unsave'))
            elif action=='view': await show(query.message,chat_service,actor,token)
            elif action=='reply':
                row=await service.read(actor,token);await choices(query.message,chat_service,actor,row['invitation'],token)
            elif action=='get':
                row=await service.read(actor,token)
                if row['state']!='sent': raise CardError('social_unavailable')
                if get_song is None: await query.message.answer(tr('get_song_unavailable'))
                else: await get_song.begin(query.message,actor,row['song']['id'])
            elif action=='note':
                row=await service.read(actor,token)
                if row['state']!='draft' or row['role']!='sender': raise CardError('social_unavailable')
                prompt=await query.message.answer(tr('social_note_prompt'),reply_markup=ForceReply(selective=True,input_field_placeholder=tr('social_note_placeholder')))
                async with chat_service.database.write() as session:
                    internal=await user_id(session,actor)
                    existing=await session.get(SwapPrompt,internal)
                    if existing: existing.swap=token;existing.message_id=prompt.message_id
                    else: session.add(SwapPrompt(user_id=internal,swap=token,message_id=prompt.message_id))
            elif action=='report':
                await service.read(actor,token)
                await query.message.answer(tr('social_report_reason'),reply_markup=keyboard([[button('social_reason_'+reason,'ss:r'+reason+':'+token)] for reason in ['spam','harassment','unsafe','other']]))
            elif action.startswith('r') and action not in {'remind'}:
                row=await service.read(actor,token)
                await service.relationship(actor,row['invitation'],'report',action[1:],token)
                await query.message.answer(tr('social_report_done'))
            else:
                result=await service.act(actor,token,action)
                await service.flush_notices(query.bot)
                if result['state'] in {'cancelled','deleted'}: await query.message.answer(tr('social_removed'))
                else: await show(query.message,chat_service,actor,token)
        else: raise CardError('social_invalid')
    except CardError as error: await query.message.answer(tr(str(error)))


def moderators(): return {int(value) for value in os.environ.get('LILCUSIN_MODERATOR_IDS','').split(',') if value.strip().isdigit()}


async def moderation(message,chat):
    parts=message.text.split()
    try:
        result=await Social(chat.database).moderate(message.from_user.id,moderators(),parts[1] if len(parts)>1 else None,parts[2] if len(parts)>2 else None)
        if 'reports' not in result: await message.answer(tr('social_reviewed'));return
        if not result['reports']: await message.answer(tr('social_no_reports'))
        for row in result['reports']:
            await message.answer(row['reason']+'\n'+row['note']+'\n\n/socialreports '+row['token']+' dismiss\n/socialreports '+row['token']+' suspend',parse_mode=None)
    except CardError as error: await message.answer(tr(str(error)))
