from enum import StrEnum

ANALYZER_NAME = "librosa"
# Bump the pipeline version when extraction settings or dependencies change.
ANALYZER_VERSION = "0.11.0-pipeline1-numpy2.2.6"
SAMPLE_RATE = 22050
TOTAL_TIMEOUT = 180
CONVERSION_TIMEOUT = 30
WORKER_TIMEOUT = 120


class Category(StrEnum):
    METADATA = "invalid_metadata"
    SIZE = "file_too_large"
    DURATION = "duration_exceeded"
    TYPE = "unsupported_audio"
    DOWNLOAD = "download_failed"
    MISSING_FFMPEG = "ffmpeg_unavailable"
    DECODE = "invalid_audio"
    TIMEOUT = "timeout"
    FEATURES = "feature_extraction_failed"
    INTERRUPTED = "interrupted"
    INTERNAL = "analysis_failed"


class AudioError(Exception):
    def __init__(self, category: Category):
        self.category = category
        super().__init__(category.value)
