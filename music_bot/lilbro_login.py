"""Interactive local sign-in only. Never called by polling, handlers or fetching jobs."""
import argparse
import asyncio
import getpass
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from .lilbro_user import UserSessionConfig


async def login():
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
    config = UserSessionConfig.environment()
    config.session.parent.mkdir(parents=True, exist_ok=True)
    lock = Path(str(config.session) + '.setup.lock')
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    client = TelegramClient(str(config.session), config.api_id, config.api_hash,
                            connection_retries=1, request_retries=0, timeout=10)
    try:
        os.chmod(config.session, 0o600)
        if os.name == 'nt':
            # Restrict the session to this Windows identity before any account sign-in.
            import subprocess
            sid = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'], capture_output=True,
                                 text=True, check=True).stdout.strip().split(',')[-1].strip('"')
            subprocess.run(['icacls', str(config.session), '/inheritance:r', '/grant:r', '*' + sid + ':(F)'],
                           capture_output=True, check=True)
        await client.connect()
        if not await client.is_user_authorized():
            phone = input('Telegram phone number (sent only to Telegram): ').strip()
            sent = await client.send_code_request(phone)
            try:
                await client.sign_in(phone=phone, code=getpass.getpass('Telegram login code (hidden): '),
                                     phone_code_hash=sent.phone_code_hash)
            except SessionPasswordNeededError:
                await client.sign_in(password=getpass.getpass('Telegram two-step password (hidden): '))
        me = await client.get_me()
        if me.bot:
            raise RuntimeError('A user account is required.')
        print('User session ready. Keep the session file private and use a dedicated account where possible.')
    finally:
        await client.disconnect()
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description='Authorize a local Telegram user session for Lil Bro.')
    parser.add_argument('--env-file', type=Path, default=Path('.env'))
    args = parser.parse_args()
    load_dotenv(args.env_file, override=True)
    logging.disable(logging.CRITICAL)
    try:
        asyncio.run(login())
        return 0
    except KeyboardInterrupt:
        print('Sign-in cancelled.')
    except Exception as error:
        print('Sign-in incomplete (' + type(error).__name__ + '); private details omitted.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
