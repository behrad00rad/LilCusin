"""Internal, killable librosa worker. Receives only a converted local WAV path."""

import json
import resource
import sys

from .features import extract_features


def main():
    # Linux/Codespaces limits in addition to the parent's wall-clock deadline.
    resource.setrlimit(resource.RLIMIT_CPU, (120, 125))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 ** 3, 2 * 1024 ** 3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 ** 2, 64 * 1024 ** 2))
    try:
        result = extract_features(sys.argv[1])
        print(json.dumps({"features": result}, allow_nan=False))
    except Exception:
        print('{"error":"feature_extraction_failed"}')


if __name__ == "__main__":
    main()
