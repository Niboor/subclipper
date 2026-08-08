import os
import time
import threading
from contextlib import contextmanager

from . import metrics

_MAX_CONCURRENT_FFMPEG = int(os.getenv("MAX_CONCURRENT_FFMPEG", "4"))
_semaphore = threading.BoundedSemaphore(_MAX_CONCURRENT_FFMPEG)


@contextmanager
def limit_ffmpeg_concurrency():
    """Bound how many ffmpeg/ffprobe-invoking operations can run at once.

    Sized by MAX_CONCURRENT_FFMPEG since each ffmpeg process holds its own decode
    buffers and an unbounded burst can exceed a small container's memory limit.
    """
    start = time.perf_counter()
    with _semaphore:
        metrics.record("ffmpeg:queue_wait", time.perf_counter() - start)
        yield
