import logging
import unittest
from unittest.mock import patch

from music_bot.__main__ import SafeFormatter
from music_bot.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_missing_and_empty_names_only(self):
        for environment, missing in [
            ({}, "TELEGRAM_BOT_TOKEN"),
            ({"TELEGRAM_BOT_TOKEN": "123:fake"}, "LASTFM_API_KEY"),
            ({"TELEGRAM_BOT_TOKEN": " ", "LASTFM_API_KEY": "secret"}, "TELEGRAM_BOT_TOKEN"),
        ]:
            with self.subTest(missing=missing), patch.dict("os.environ", environment, clear=True), patch("music_bot.config.load_environment"):
                with self.assertRaises(ConfigError) as error:
                    load_config()
                self.assertEqual(str(error.exception), "Missing required environment variable: " + missing)

    def test_invalid_token_and_repr_hide_secrets(self):
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "secret", "LASTFM_API_KEY": "key"}), patch("music_bot.config.load_environment"):
            with self.assertRaises(ConfigError) as error:
                load_config()
            self.assertNotIn("secret", str(error.exception))
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "123:secret", "LASTFM_API_KEY": "key"}), patch("music_bot.config.load_environment"):
            config = load_config()
            self.assertEqual(repr(config), "Config()")

    def test_dependency_tracebacks_and_messages_not_formatted(self):
        record = logging.LogRecord("aiogram.event", logging.ERROR, "", 1, "user secret %s", ("token",), (ValueError, ValueError("private"), None))
        output = SafeFormatter().format(record)
        for private in ("secret", "token", "private"):
            self.assertNotIn(private, output)
