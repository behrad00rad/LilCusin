# Debian 13 deployment (Python 3.13)

This is the bot deployment procedure. Application feature settings are documented
in `.env.example`, [Get Song](GET_SONG.md) and [recognition](RECOGNITION.md).
The separate Mini App services have their own [operations record](MINIAPP_DEPLOYMENT.md).
The polling entry point is `python -m music_bot` (`music_bot/__main__.py`).
Python 3.12 remains supported; the intended Debian 13 runtime is Python 3.13.
Python 3.14 is not validated by this pass.

## Preserve production differences first

Do not overwrite a running checkout or run `git reset --hard`, `git clean`, or an
unreviewed `git pull`. Production may have uncommitted code, a different commit,
service overrides, and installed packages absent from Git. The reported local
12-second artwork timeout and warning are incorporated here, but other production
changes are unknown. This audit did not connect to the VPS.

Before applying an approved release, an operator should privately record the current
commit, `git status --short`, staged/unstaged code diffs, untracked code, installed
versions, and `systemctl cat lilcusin-music-bot`. Keep that record on the server;
do not publish it or include credentials/environment values in a report. Reconcile
code differences into a separate release directory and review them before switching.
Preserve the existing private configuration, service arguments, ownership, data path,
and optional transport/session files. Do not copy databases into a testing checkout.

The repository uses `<checkout>/data/music_bot.sqlite3` (no database environment
override). A new release directory must use the existing data directory, with correct
permissions, before starting the service. Never accidentally start with an empty
`data/`. Any Mini App API sharing that database must use the same persistent data
directory. Stop all database writers before an operator makes a consistent backup
using the established backup procedure. Startup runs additive migrations; rolling
code back does not undo those migrations.

## Clean installation

The commands below are operator instructions; they were not run on production.
Use a reviewed release directory, owned by the service user. Run virtualenv commands
as that user, not root. For the existing installation the recorded checkout is
`/home/baharnaj/lilcusin-music-bot`; verify it against the actual service first.

```sh
sudo apt-get update
sudo apt-get install python3.13 python3.13-venv ffmpeg
cd /path/to/reviewed/release
python3.13 -m venv .venv-next
.venv-next/bin/python -m pip install -r requirements.txt -r requirements-audio.txt
# Only for GET_SONG_PROVIDER=lilbro with GET_SONG_LILBRO_TRANSPORT=user:
# .venv-next/bin/python -m pip install -r requirements-lilbro.txt
.venv-next/bin/python -m pip check
.venv-next/bin/python -m unittest tests.test_audio_artwork tests.test_preflight tests.test_get_song -v
```

Install both requirements files for the full bot deployment: the base file includes
ShazamIO and Python 3.13's `audioop-lts`; the audio file includes Mutagen and yt-dlp.
Existing unrelated pins are preserved. Pydantic is constrained to `>=2.13.5,<2.14`,
within aiogram 3.31's declared range. The original failing production Pydantic
version is unknown; do not attribute a specific version defect without evidence.
Do not reuse an old environment or use `--no-deps` to work around resolver errors.

FFmpeg **and ffprobe on PATH** are required for Get Song. The imageio-ffmpeg fallback
used for recognition does not replace ffprobe or Get Song's `ffmpeg` executable.
Install a supported Node.js runtime on the service PATH for full YouTube JavaScript
challenge support. The adapter explicitly enables Node when found; yt-dlp's default
extras supply EJS. Consult the current [upstream runtime requirements](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
before choosing a Node version. Node is optional for starting the bot, but its absence
can prevent YouTube retrieval. No cookies or challenge bypass are configured.

Dependency ranges allow maintenance fixes, rather than freezing the VPS environment.
After a successful clean install, save the resolved versions privately as a release
receipt and retain the old environment for rollback. Re-run these checks after any
yt-dlp update; extractor compatibility and provider access can change independently
of this repository. A Debian/Python 3.13 clean install remains a release gate if it
has not been verified in the target staging environment.

## Application configuration and offline preflight

For a fresh installation only, copy `.env.example` to `.env`, restrict it to the
service user (`chmod 600 .env`), and edit it privately. For an existing deployment,
preserve `.env`; do not replace it with the example. Required values are
`TELEGRAM_BOT_TOKEN` and `LASTFM_API_KEY`. Preserve any Telegram API relay origin.
Get Song defaults off; activation, quotas and transport selection are application
configuration in GET_SONG.md. Musixmatch needs its API key only when selected;
the optional user transport needs Telegram API credentials and its existing session.

Create the data directory as the service user on a fresh installation. Use the existing
persistent directory for an upgrade. Give the user a private writable temporary
directory with sufficient free disk/quota; set `TMPDIR` in the service environment.
Do not point TMPDIR at application data, backups or session storage.

```sh
# Run from the reviewed release as the actual service user, with the service's
# environment and PATH (including its TMPDIR), without starting polling:
.venv-next/bin/python -m music_bot.preflight
```

Preflight checks declared versions, imports (including ShazamIO/Mutagen/yt-dlp),
installed dependency consistency, configuration, FFmpeg/ffprobe, data-file permissions,
and data/temp directory writes using only disposable probe files. It reads private
configuration locally but prints no values, paths, library stderr or exceptions.
It never opens SQLite, instantiates a Telegram client, starts polling, downloads media,
or checks network availability. A pass does not prove Telegram/YouTube reachability,
provider rights, session authorization, service sandbox permissions, or sufficient disk.

## Safe systemd switch/restart (after release approval)

No tracked systemd unit or deployment script was present during this audit. Preserve
the installed unit and its overrides; verify its User, WorkingDirectory, ExecStart,
EnvironmentFile, TMPDIR/PATH and database path privately. Do not replace the separate
Mini App/connector services with a second polling process. For a fresh bot unit,
use `Type=simple`, the service user, the checkout WorkingDirectory, an absolute
`ExecStart=/path/to/release/.venv-next/bin/python -m music_bot`, `Restart=on-failure`,
`KillMode=control-group`, and enough `TimeoutStopSec` for graceful shutdown.

1. Finish code reconciliation, clean installation, mocked tests and preflight in the
   reviewed release. Keep the previous code/environment and reviewed unit available.
2. Stop the installed polling service. Confirm it is inactive and all its children
   have exited. Do not run `python -m music_bot` manually alongside it.
3. If making a database backup, stop other database writers too; have the operator
   use the established consistent backup procedure. Preserve data/config/session paths.
4. Point the unit's WorkingDirectory and ExecStart at the reviewed code/environment
   (or apply the reviewed files to the stopped existing checkout). Preserve its other
   settings. Run preflight as the service user in that final location/environment.
5. Reload systemd only if the unit/override changed, then start exactly one service:

```sh
sudo systemctl stop lilcusin-music-bot
sudo systemctl is-active lilcusin-music-bot  # expected: inactive; exit status 3
# Perform the reviewed switch and final preflight while stopped.
sudo systemctl daemon-reload  # only if unit/override changed
sudo systemctl start lilcusin-music-bot
sudo systemctl is-active lilcusin-music-bot  # expected: active
sudo journalctl -u lilcusin-music-bot -n 50 --no-pager
```

Inspect logs privately. Verify one polling process and no Telegram conflict errors.
An operator should test an authorized song and check playback, cover and cached resend;
offline tests cannot prove these. Restore previously stopped API writers deliberately.
If startup fails, stop the new service, restore the previous code/environment/unit,
reload if needed, and start once. Do not restore a database blindly or run old and
new bot processes simultaneously. Verify migration compatibility before rollback.

## Troubleshooting

- **Missing dependency/import:** install both requirement files into the exact Python
  used by ExecStart; run `pip check` and preflight again. A successful installation
  in another interpreter does not fix the service.
- **Pydantic/aiogram:** use a clean environment and the declared Pydantic range.
  Do not upgrade aiogram or unrelated packages to mask an inconsistent environment.
- **ShazamIO on Python 3.13:** check `audioop-lts` and the ShazamIO import. `audioop`
  was removed from the standard library; its compatibility distribution is conditional.
- **No artwork:** `Artwork embedding unavailable` identifies missing Mutagen.
  `Artwork retrieval failed`, `Artwork conversion failed`, and `Artwork embedding failed`
  identify separate stages without revealing source URLs or exception text. The outer
  preparation budget is 12 seconds, allowing the bounded eight-second image request
  plus conversion/tagging; enrichment/recognition can still exhaust it. The budget is
  best-effort: cancellation waits for an already-started atomic tagging thread before
  cleanup. Audio delivery continues without a thumbnail if presentation fails.
- **YouTube retrieval:** verify yt-dlp in the service environment, FFmpeg/ffprobe and
  a supported Node on its PATH. Network restrictions and extractor drift are separate
  risks; preflight deliberately makes no media or provider requests.
