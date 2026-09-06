"""Killable, output-bounded subprocesses; no shell or inherited credentials."""

import asyncio
import os

from .common import AudioError, Category


def worker_environment(directory):
    return {"PATH": os.defpath, "LANG": "C.UTF-8", "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "NUMBA_NUM_THREADS": "1",
            "NUMBA_CACHE_DIR": str(directory / "numba"), "TMPDIR": str(directory),
            "PYTHONDONTWRITEBYTECODE": "1"}


async def run_process(arguments, timeout, *, env=None, output_limit=16384):
    try:
        process = await asyncio.create_subprocess_exec(
            *arguments, stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env,
        )
    except FileNotFoundError:
        raise AudioError(Category.MISSING_FFMPEG) from None
    try:
        async with asyncio.timeout(timeout):
            output = bytearray()
            while chunk := await process.stdout.read(4096):
                output.extend(chunk)
                if len(output) > output_limit:
                    raise AudioError(Category.DECODE)
            await process.wait()
            if process.returncode:
                raise AudioError(Category.DECODE)
            return bytes(output)
    except TimeoutError:
        raise AudioError(Category.TIMEOUT) from None
    finally:
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            async def reap():
                # Drain/discard after termination so a full pipe cannot block exit.
                while await process.stdout.read(65536):
                    pass
                await process.wait()
            try:
                await asyncio.wait_for(reap(), 2)
            except TimeoutError:
                process.kill()
                await reap()
