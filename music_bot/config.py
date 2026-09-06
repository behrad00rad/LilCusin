"""Load secrets without including their values in errors or representations."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from aiogram.utils.token import TokenValidationError, validate_token
from dotenv import load_dotenv


class ConfigError(ValueError):
    """A safe, user-readable configuration error."""


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str = field(repr=False)
    lastfm_api_key: str = field(repr=False)
    lil_bro_bot_username: str = field(default="musicbehbot", repr=False)


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


def load_config() -> Config:
    load_environment()
    token = required_variable("TELEGRAM_BOT_TOKEN")
    lastfm_key = required_variable("LASTFM_API_KEY")
    username = normalized_lil_bro_username()
    if username is None:
        raise ConfigError("LIL_BRO_BOT_USERNAME is invalid")
    try:
        validate_token(token)
    except TokenValidationError:
        raise ConfigError("Invalid TELEGRAM_BOT_TOKEN format") from None
    return Config(token, lastfm_key, username)
