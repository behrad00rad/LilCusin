import json
import sys

from .common import AudioError, Category, WORKER_TIMEOUT
from .features import validate_features
from .process import run_process, worker_environment


async def analyse_audio(path):
    try:
        output = await run_process([sys.executable, "-m", "music_bot.audio.worker", str(path)],
                                   WORKER_TIMEOUT, env=worker_environment(path.parent))
        payload = json.loads(output)
        return validate_features(payload["features"])
    except AudioError as error:
        if error.category == Category.TIMEOUT:
            raise
        raise AudioError(Category.FEATURES) from None
    except (ValueError, KeyError, TypeError):
        raise AudioError(Category.FEATURES) from None
