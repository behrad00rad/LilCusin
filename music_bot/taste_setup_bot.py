from aiogram.types import InlineKeyboardButton as Button,InlineKeyboardMarkup,Message
from .taste_setup import read_setup,save_setup,needed,STYLES,MOODS,ARTISTS
from .i18n import tr

async def show_setup(message,chat_service,*,restart=False):
    user_id=message.chat.id
    if not restart and not await needed(chat_service.database,user_id):return False
    state=await read_setup(chat_service.database,user_id)
    if restart:
        await save_setup(chat_service.database,user_id,style=state['style'],mood=state['mood'],artist=state['artist'],completed=False,step=0)
        state['step']=0
    text,keyboard=question(state)
    await message.answer(text,reply_markup=keyboard)
    return True

def question(state):
    step=state['step'] if state['step'] in (0,1,2) else 0
    keys=[]
    if step==0:
        choices=[Button(text=tr('style_'+key),callback_data='taste:style:'+key) for key in STYLES]
    elif step==1:
        choices=[Button(text=tr('mood_'+key),callback_data='taste:mood:'+key) for key in MOODS]
    else:
        choices=[Button(text=name,callback_data='taste:artist:'+str(index)) for index,name in enumerate(ARTISTS.get(state['style'],ARTISTS['pop']))]
        choices.append(Button(text=tr('setup_surprise'),callback_data='taste:artist:auto'))
    keys=[choices[i:i+2] for i in range(0,len(choices),2)]
    keys.append([Button(text=tr('skip'),callback_data='taste:skip')])
    return '🦉 '+tr('step',n=step+1)+'\n\n'+tr('setup_q'+str(step+1)),InlineKeyboardMarkup(inline_keyboard=keys)

async def setup_callback(query,chat_service):
    if not isinstance(query.message,Message) or query.message.chat.type!='private' or query.message.chat.id!=query.from_user.id or query.from_user.is_bot:
        await query.answer(tr('private'));return
    state=await read_setup(chat_service.database,query.from_user.id)
    if state['completed']:
        await query.answer(tr('stale'));return
    parts=(query.data or '').split(':')
    action=parts[1] if len(parts)>1 else ''
    value=parts[2] if len(parts)>2 else None
    complete=action=='skip'
    if action=='style' and state['step']==0 and value in STYLES:state.update(style=value,step=1)
    elif action=='mood' and state['step']==1 and value in MOODS:state.update(mood=value,step=2)
    elif action=='artist' and state['step']==2 and value in ('0','1','auto'):
        state['artist']=None if value=='auto' else ARTISTS.get(state['style'],ARTISTS['pop'])[int(value)]
        complete=True
    elif not complete:
        await query.answer(tr('stale'));return
    await save_setup(chat_service.database,query.from_user.id,style=state['style'],mood=state['mood'],artist=state['artist'],completed=complete,step=3 if complete else state['step'])
    await query.answer()
    if complete:
        await query.message.edit_text(tr('setup_saved'))
        from .chat_ui import show_recommendations
        await show_recommendations(query.message,chat_service,query.from_user.id)
    else:
        text,keyboard=question(state)
        await query.message.edit_text(text,reply_markup=keyboard)
