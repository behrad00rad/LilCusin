import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace as NS
from music_bot import preflight


class PreflightTests(unittest.TestCase):
    def test_missing_and_incompatible_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'requirements.txt').write_text('aiogram==3.31.0\npydantic>=2.13.5,<2.14\n')
            (root / 'requirements-audio.txt').write_text('mutagen>=1.47,<2\n')
            def version(name):
                if name == 'mutagen':
                    raise PackageNotFoundError(name)
                return {'aiogram': '3.31.0', 'pydantic': '2.14.0'}[name]
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(preflight.dependencies(root, version),
                                 ['Incompatible dependency: pydantic', 'Missing dependency: mutagen'])

    def test_smoke_import_errors_do_not_expose_stderr(self):
        errors = preflight.smoke_imports(lambda *a, **k: NS(returncode=1, stderr=b'secret'))
        self.assertIn('Import failed: shazamio', errors)
        self.assertNotIn('secret', ' '.join(errors))

    def test_required_configuration_without_loading_private_dotenv(self):
        with patch.dict(os.environ, {}, clear=True), patch('music_bot.config.load_environment'):
            with self.assertRaises(ValueError):
                preflight.configuration()
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': '123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi',
                                    'LASTFM_API_KEY': 'test'}, clear=True), \
             patch('music_bot.config.load_environment'):
            preflight.configuration()

    def test_python_313_dependency_marker(self):
        from packaging.markers import default_environment
        environment = default_environment()
        environment['python_version'] = '3.13'
        environment['python_full_version'] = '3.13.0'
        with patch('packaging.markers.default_environment', return_value=environment), \
             patch.dict(os.environ, {}, clear=True):
            calls = []
            def version(name):
                calls.append(name)
                raise PackageNotFoundError(name)
            preflight.dependencies(version=version)
        self.assertIn('audioop-lts', calls)

    def test_main_passes_with_offline_mocks(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(preflight, 'ROOT', Path(directory)), \
             patch.object(preflight, 'dependencies', return_value=[]), \
             patch.object(preflight, 'smoke_imports', return_value=[]), \
             patch.object(preflight, 'configuration'), \
             patch.object(preflight, 'writable', return_value=True), \
             patch.object(preflight.shutil, 'which', return_value='/mock/tool'), \
             patch.object(preflight.subprocess, 'run', return_value=NS(returncode=0)), \
             patch('builtins.print') as output:
            self.assertEqual(preflight.main(), 0)
        self.assertIn('PASS', str(output.call_args_list))

    def test_directory_probe_creates_no_persistent_files(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'sentinel'
            sentinel.write_bytes(b'unchanged')
            self.assertTrue(preflight.writable(directory))
            self.assertFalse(preflight.writable(Path(directory) / 'missing'))
            self.assertEqual(list(Path(directory).iterdir()), [sentinel])
            self.assertEqual(sentinel.read_bytes(), b'unchanged')

    def test_main_fails_safely_without_configuration_or_binaries(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(preflight, 'ROOT', Path(directory)), \
             patch.object(preflight, 'dependencies', return_value=[]), \
             patch.object(preflight, 'smoke_imports', return_value=[]), \
             patch.object(preflight, 'configuration', side_effect=ValueError('secret')), \
             patch.object(preflight, 'writable', return_value=False), \
             patch.object(preflight.shutil, 'which', return_value=None), \
             patch.object(preflight.subprocess, 'run', return_value=NS(returncode=0)), \
             patch('builtins.print') as output:
            self.assertEqual(preflight.main(), 1)
        rendered = str(output.call_args_list)
        self.assertIn('ffmpeg', rendered)
        self.assertIn('Configuration invalid', rendered)
        self.assertNotIn('secret', rendered)
