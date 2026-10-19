"""A local content identifier that also distinguishes uncommitted builds."""
import hashlib
from pathlib import Path


def build_id():
    digest = hashlib.sha256()
    root = Path(__file__).resolve().parent
    for path in sorted(root.rglob('*.py')):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return 'chat-' + digest.hexdigest()[:12]


BUILD_ID = build_id()
