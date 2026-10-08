# Security policy

## Reporting a vulnerability

Please do not publish credentials, private user data, or an exploitable security
issue in a public issue. Contact the maintainer privately through GitHub. Include
the affected area, impact, and steps to reproduce; do not include real user data
or working secrets.

## Protecting local data

- Keep `.env` and `data/music_bot.sqlite3` out of version control.
- Use a separate bot token for development where possible.
- Grant the bot only the Telegram permissions it needs.
- If a token or API key is committed or otherwise exposed, revoke/rotate it
  immediately. Removing it in a later commit does not remove it from history.
- Do not share database files: they can contain Telegram identifiers, submissions,
  ratings, and channel metadata.
