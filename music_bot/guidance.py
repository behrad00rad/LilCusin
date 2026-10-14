"""Short, repeatable Telegram guides and a shared language picker."""
import re
from aiogram import BaseMiddleware, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton as Button, InlineKeyboardMarkup, Message
from .i18n import tr, language, menu_action
from .preferences import preferences, LANGUAGES
from .submissions import Submitter

router = Router()
APP_URL='https://lilcusin-ui.ghazanfaribehrad.workers.dev/'

@router.message(Command('setup'))
async def setup_command(message,chat_service):
    if message.chat.type=='private' and message.from_user and not message.from_user.is_bot:
        from .taste_setup_bot import show_setup
        await show_setup(message,chat_service,restart=True)

@router.callback_query(F.data.startswith('taste:'))
async def taste_callback(query,chat_service):
    from .taste_setup_bot import setup_callback
    await setup_callback(query,chat_service)


def guide_keyboard(step):
    keys=[]
    if step:
        keys.append(Button(text=tr('back'),callback_data=f'guide:{step-1}'))
    keys.append(Button(text=tr('done' if step==2 else 'next'),callback_data='guide:done' if step==2 else f'guide:{step+1}'))
    return InlineKeyboardMarkup(inline_keyboard=[keys,[Button(text=tr('language'),callback_data='guide:language'),
                                                     Button(text=tr('skip'),callback_data='guide:done')]])


async def show_guide(message, step=0):
    n=step+1
    text='🦉 '+tr('step',n=n)+'\n\n'+tr(f'g{n}_title')+'\n'+tr(f'bot_g{n}_text')
    if step==0:text+='\n\nRadiohead - Creep'
    await message.answer(text,reply_markup=guide_keyboard(step))


async def language_picker(message):
    pairs=list(LANGUAGES.items())
    keyboard=InlineKeyboardMarkup(inline_keyboard=[
        [Button(text=('✓ ' if code==language.get() else '')+label,callback_data='language:'+code)
         for code,label in pairs[i:i+2]] for i in range(0,len(pairs),2)])
    await message.answer('🌐 '+tr('language'),reply_markup=keyboard)


@router.message(Command('language'))
async def language_command(message):
    if message.chat.type=='private' and message.from_user and not message.from_user.is_bot:
        await language_picker(message)


@router.callback_query(F.data.startswith('guide:') | F.data.startswith('language:'))
async def guide_callback(query,chat_service):
    if (not isinstance(query.message,Message) or query.message.chat.type!='private'
            or query.message.chat.id!=query.from_user.id or query.from_user.is_bot):
        await query.answer(tr('private'));return
    data=query.data or ''
    if data.startswith('language:'):
        code=data.split(':',1)[1]
        if code not in LANGUAGES:await query.answer(tr('error'));return
        await preferences(chat_service.database,query.from_user.id,language=code)
        language.set(code)
        await query.answer(tr('ok'))
        from .taste_setup_bot import show_setup
        if not await show_setup(query.message,chat_service):await show_guide(query.message)
        from .chat_ui import main_menu
        await query.message.answer(tr('bot_MENU_PROMPT'),reply_markup=main_menu())
    elif data=='guide:language':
        await query.answer();await language_picker(query.message)
    elif data=='guide:done':
        await query.answer()
        from .taste_setup_bot import show_setup
        if await show_setup(query.message,chat_service):return
        from .chat_ui import main_menu
        await query.message.answer(tr('bot_g1_text')+'\n\nRadiohead - Creep',reply_markup=main_menu())
    elif re.fullmatch(r'guide:[0-2]',data):
        await query.answer();await show_guide(query.message,int(data[-1]))
    else:await query.answer(tr('stale'))


class LanguageMiddleware(BaseMiddleware):
    def __init__(self,database):self.database=database

    async def __call__(self,handler,event,data):
        user=getattr(event,'from_user',None)
        chat=event.chat if isinstance(event,Message) else getattr(getattr(event,'message',None),'chat',None)
        if not user or user.is_bot or not chat or chat.type!='private' or chat.id!=user.id:
            return await handler(event,data)
        service=data.get('chat_service')
        if service is None:return await handler(event,data)
        await service.ensure_user(Submitter(user.id,user.username,user.full_name,user.language_code))
        prefs=await preferences(self.database,user.id,user.language_code)
        context=language.set(prefs['language'])
        try:
            if not prefs['bot_guide_seen']:
                await preferences(self.database,user.id,bot_seen=True)
                if isinstance(event,Message) and not (event.text or '').startswith(('/start','/help','/language')):
                    from .taste_setup_bot import show_setup
                    if not await show_setup(event,service):await show_guide(event)
            return await handler(event,data)
        finally:language.reset(context)

async def configure_commands(bot):
    from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats
    keys={'start':'guide','recommend':'for_you','profile':'taste','taste':'taste','help':'guide',
          'language':'language','privacy':'privacy_hint','forgetme':'yes_delete','cancel':'cancel',
          'connectchannel':'connect','channels':'channels','disconnectchannel':'disconnect','setup':'setup_title'}
    for code in LANGUAGES:
        context=language.set(code)
        try:
            commands=[BotCommand(command=name,description=tr(key)[:100]) for name,key in keys.items()]
            await bot.set_my_commands(commands,scope=BotCommandScopeAllPrivateChats(),language_code=code)
            if code=='en':await bot.set_my_commands(commands,scope=BotCommandScopeAllPrivateChats())
        finally:language.reset(context)
