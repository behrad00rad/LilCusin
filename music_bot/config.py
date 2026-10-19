"""Load secrets without including their values in errors or representations."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from aiogram.utils.token import TokenValidationError, validate_token
from dotenv import load_dotenv


class ConfigError(ValueError):
    """A safe, user-readable configuration error."""


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str = field(repr=False)
    lastfm_api_key: str = field(repr=False)
    telegram_api_base_url: str = field(repr=False)
    lil_bro_bot_username: str = field(default="musicbehbot", repr=False)
    miniapp_url: str | None = field(default=None, repr=False)
    miniapp_host: str = field(default='127.0.0.1', repr=False)
    miniapp_port: int = field(default=8080, repr=False)
    search_deezer_enabled: bool = field(default=True, repr=False)


_LIL_BRO_USERNAME = re.compile(r"[A-Za-z0-9_]{5,32}\Z")


def normalized_lil_bro_username(value: str | None = None) -> str | None:
    raw = (os.environ.get("LIL_BRO_BOT_USERNAME", "musicbehbot") if value is None else value).strip()
    username = raw.removeprefix("@").strip()
    return username if _LIL_BRO_USERNAME.fullmatch(username) else None


def load_environment() -> None:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


def required_variable(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def telegram_api_base_url() -> str:
    value = (os.environ.get("TELEGRAM_API_BASE_URL", "").strip() or "https://api.telegram.org").rstrip("/")
    try:
        parsed = urlsplit(value)
        if parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password and not parsed.path and not parsed.query and not parsed.fragment:
            return value
    except ValueError:
        pass
    raise ConfigError("TELEGRAM_API_BASE_URL must be an HTTPS origin")


def load_config() -> Config:
    load_environment()
    token = required_variable("TELEGRAM_BOT_TOKEN")
    lastfm_key = required_variable("LASTFM_API_KEY")
    username = normalized_lil_bro_username()
    if username is None:
        raise ConfigError("LIL_BRO_BOT_USERNAME is invalid")
    api_base_url = telegram_api_base_url()
    try:
        validate_token(token)
    except TokenValidationError:
        raise ConfigError("Invalid TELEGRAM_BOT_TOKEN format") from None
    miniapp_url = os.environ.get('MINIAPP_URL', '').strip() or None
    if miniapp_url:
        parsed = urlsplit(miniapp_url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise ConfigError('MINIAPP_URL must be an HTTPS origin')
    try:
        port = int(os.environ.get('MINIAPP_PORT', '8080'))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ConfigError('MINIAPP_PORT must be between 1 and 65535') from None
    return Config(token, lastfm_key, api_base_url, username, miniapp_url,
                  os.environ.get('MINIAPP_HOST', '127.0.0.1'), port,
                  os.getenv('SEARCH_DEEZER_ENABLED', 'true').strip().lower() == 'true')
