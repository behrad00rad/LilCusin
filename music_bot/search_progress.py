"""Bounded, cancellable status updates while a source lookup is running."""
import asyncio


async def search_with_updates(operation, update, *, delays=(6, 10)):
    async def notify():
        for delay, key in zip(delays, ('searching_slow', 'searching_sources')):
            await asyncio.sleep(delay)
            try:
                await update(key)
            except Exception:
                pass  # Presentation must never fail a source lookup.

    notifier = asyncio.create_task(notify())
    try:
        return await operation()
    finally:
        notifier.cancel()
        await asyncio.gather(notifier, return_exceptions=True)
