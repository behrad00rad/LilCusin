"""Request-local translations shared by Telegram and the Mini App."""
from contextvars import ContextVar
import json
from pathlib import Path
from .preferences import normalize_language, LANGUAGES

language = ContextVar('lilcusin_language', default='en')
CATALOGUE = json.loads((Path(__file__).with_name('web')/'locales.json').read_text(encoding='utf-8'))


def tr(key, **values):
    current = CATALOGUE.get(language.get(), CATALOGUE['en'])
    text = current.get(key, CATALOGUE['en'].get(key, key))
    return text.format(**values) if values else text


def menu_labels(*keys):
    from . import messages
    return ({CATALOGUE[code].get('bot_'+key, '') for code in LANGUAGES for key in keys}
            | {vars(messages).get(key, '') for key in keys}) - {''}


def menu_action(text):
    actions={'MENU_SEND':'send','MENU_FOR_YOU':'recommend','MENU_PROFILE':'taste',
             'MENU_CHANNELS':'channels','MENU_SETTINGS':'settings','MENU_HELP':'help'}
    for key, action in actions.items():
        if text in menu_labels(key): return action
    return None


def localized_reason(text):
    # Provider names/titles are never translated; only our own explanation strings.
    keys=CATALOGUE['en']
    for key,value in keys.items():
        if key.startswith('reason_') and value==text: return tr(key)
    return text
