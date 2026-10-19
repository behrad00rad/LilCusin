"""Offline deployment checks. Never constructs a Bot, Database or media worker."""
import importlib.metadata as metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def dependencies(root=ROOT, version=metadata.version):
    from packaging.requirements import Requirement
    errors = []
    files = ['requirements.txt', 'requirements-audio.txt']
    if (os.getenv('GET_SONG_PROVIDER', '').strip().lower() == 'lilbro'
            and os.getenv('GET_SONG_LILBRO_TRANSPORT', '').strip().lower() == 'user'):
        files.append('requirements-lilbro.txt')
    for filename in files:
        for line in (root / filename).read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            req = Requirement(line)
            if req.marker and not req.marker.evaluate():
                continue
            try:
                installed = version(req.name)
            except metadata.PackageNotFoundError:
                errors.append('Missing dependency: ' + req.name)
                continue
            if not req.specifier.contains(installed, prereleases=False):
                errors.append('Incompatible dependency: ' + req.name)
    return errors


def smoke_imports(run=subprocess.run):
    # Capture all library diagnostics. Never echo exception messages or stderr.
    modules = ['aiogram', 'aiohttp', 'sqlalchemy', 'aiosqlite', 'dotenv',
               'shazamio', 'imageio_ffmpeg', 'mutagen.id3', 'mutagen.mp4', 'yt_dlp']
    if sys.version_info >= (3, 13):
        modules.append('audioop')
    if (os.getenv('GET_SONG_PROVIDER', '').strip().lower() == 'lilbro'
            and os.getenv('GET_SONG_LILBRO_TRANSPORT', '').strip().lower() == 'user'):
        modules.append('telethon')
    errors = []
    for module in modules:
        try:
            result = run([sys.executable, '-c', 'import ' + module],
                         capture_output=True, timeout=20)
            if result.returncode:
                errors.append('Import failed: ' + module)
        except (OSError, subprocess.TimeoutExpired):
            errors.append('Import check failed: ' + module)
    return errors


def configuration():
    from .config import load_config
    from .get_song import FetchSettings
    from .lyrics_search import LyricsSettings
    from .recognition import RecognitionSettings
    load_config()
    FetchSettings.environment()
    LyricsSettings.environment()
    RecognitionSettings.environment()
    provider = os.getenv('GET_SONG_PROVIDER', 'youtube').strip().lower()
    transport = os.getenv('GET_SONG_LILBRO_TRANSPORT', 'bot').strip().lower()
    if provider not in {'youtube', 'lilbro'} or transport not in {'bot', 'user'}:
        raise ValueError
    if provider == 'lilbro' and transport == 'user':
        from .lilbro_user import UserSessionConfig
        config = UserSessionConfig.environment()
        # Do not open a Telegram session or create a missing session.
        if not config.session.is_file() or not os.access(config.session, os.R_OK | os.W_OK):
            raise ValueError


def writable(directory):
    """Probe only a disposable file; never open an application data file."""
    try:
        with tempfile.TemporaryFile(dir=directory) as probe:
            probe.write(b'preflight')
            probe.flush()
        return True
    except OSError:
        return False


def main():
    errors = []
    if not (3, 12) <= sys.version_info[:2] <= (3, 13):
        errors.append('Supported Python versions: 3.12 and 3.13 (deployment target: 3.13).')
    # Configuration loads .env first, so optional transport dependencies use the
    # same effective settings as the application. Never construct that transport.
    try:
        configuration()
    except Exception:
        errors.append('Configuration invalid; check required variables and feature settings in deployment documentation.')
    try:
        dependency_errors = dependencies()
    except Exception:
        dependency_errors = ['Dependency check unavailable; install requirements.txt and requirements-audio.txt.']
    errors.extend(dependency_errors)
    if not dependency_errors:
        errors.extend(smoke_imports())
    try:
        if subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, timeout=30).returncode:
            errors.append('Dependency consistency failed; run pip check privately.')
    except (OSError, subprocess.TimeoutExpired):
        errors.append('Dependency consistency check unavailable.')
    try:
        if subprocess.run([sys.executable, '-m', 'yt_dlp', '--version'], capture_output=True, timeout=20).returncode:
            errors.append('yt-dlp module command is unavailable.')
    except (OSError, subprocess.TimeoutExpired):
        errors.append('yt-dlp command check failed.')
    for binary in ('ffmpeg', 'ffprobe'):
        path = shutil.which(binary)
        try:
            if not path or subprocess.run([path, '-version'], capture_output=True, timeout=10).returncode:
                errors.append('Missing or unusable executable: ' + binary)
        except (OSError, subprocess.TimeoutExpired):
            errors.append('Executable check failed: ' + binary)
    for label, directory in [('application data', ROOT / 'data'), ('temporary data', Path(tempfile.gettempdir()))]:
        if not writable(directory):
            errors.append('Directory missing or not writable: ' + label)
    # The SQLite file is never opened, but existing permissions must allow writes.
    db = ROOT / 'data' / 'music_bot.sqlite3'
    if db.exists() and not os.access(db, os.R_OK | os.W_OK):
        errors.append('Existing application database permissions are insufficient.')
    if not shutil.which('node'):
        print('WARN: Node.js unavailable; YouTube JavaScript challenges may fail. See deployment documentation.')
    for error in errors:
        print('FAIL: ' + error)
    if not errors:
        print('PASS: Offline preflight complete; network access and media delivery remain unverified.')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
