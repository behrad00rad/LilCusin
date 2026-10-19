import logging
import unittest
from unittest.mock import patch

from music_bot.__main__ import SafeFormatter
from music_bot.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_popularity_catalogue_can_be_disabled(self):
        environment={'TELEGRAM_BOT_TOKEN':'123:secret','LASTFM_API_KEY':'key','SEARCH_DEEZER_ENABLED':'false'}
        with patch.dict('os.environ',environment,clear=True),patch('music_bot.config.load_environment'):
            self.assertFalse(load_config().search_deezer_enabled)

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
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "secret", "LASTFM_API_KEY": "key", "TELEGRAM_API_BASE_URL": "https://relay.example"}), patch("music_bot.config.load_environment"):
            with self.assertRaises(ConfigError) as error:
                load_config()
            self.assertNotIn("secret", str(error.exception))
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "123:secret", "LASTFM_API_KEY": "key", "TELEGRAM_API_BASE_URL": "https://relay.example"}), patch("music_bot.config.load_environment"):
            config = load_config()
            self.assertEqual(repr(config), "Config()")

    def test_explicit_telegram_api_base_url_is_normalized(self):
        environment = {
            "TELEGRAM_BOT_TOKEN": "123:secret",
            "LASTFM_API_KEY": "key",
            "TELEGRAM_API_BASE_URL": "https://relay.example/",
        }
        with patch.dict("os.environ", environment, clear=True), patch("music_bot.config.load_environment"):
            self.assertEqual(load_config().telegram_api_base_url, "https://relay.example")

    def test_telegram_api_base_url_rejects_paths_and_http(self):
        environment = {
            "TELEGRAM_BOT_TOKEN": "123:secret",
            "LASTFM_API_KEY": "key",
            "TELEGRAM_API_BASE_URL": "http://relay.example/path",
        }
        with patch.dict("os.environ", environment, clear=True), patch("music_bot.config.load_environment"):
            with self.assertRaisesRegex(ConfigError, "must be an HTTPS origin"):
                load_config()

    def test_dependency_tracebacks_and_messages_not_formatted(self):
        record = logging.LogRecord("aiogram.event", logging.ERROR, "", 1, "user secret %s", ("token",), (ValueError, ValueError("private"), None))
        output = SafeFormatter().format(record)
        for private in ("secret", "token", "private"):
            self.assertNotIn(private, output)


    def test_missing_or_blank_telegram_api_origin_defaults_to_direct(self):
        for value in (None, '', '   '):
            environment = {'TELEGRAM_BOT_TOKEN': '123:secret', 'LASTFM_API_KEY': 'key'}
            if value is not None:
                environment['TELEGRAM_API_BASE_URL'] = value
            with self.subTest(value=value), patch.dict('os.environ', environment, clear=True), patch('music_bot.config.load_environment'):
                self.assertEqual(load_config().telegram_api_base_url, 'https://api.telegram.org')
