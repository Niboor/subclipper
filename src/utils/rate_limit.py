import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """A simple in-memory sliding-window rate limiter, keyed by an arbitrary string
    (e.g. client IP). Not shared across processes — fine for the single-worker
    deployment this app runs as (see gunicorn --workers 1 in the Dockerfile/Makefile).

    Periodically sweeps out keys with no hits left in the window, so long-running
    processes that see requests from many distinct one-off IPs (e.g. internet scanners)
    don't accumulate an ever-growing dict of empty entries.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            self._trim(hits, now)

            if len(hits) >= self.max_requests:
                return False

            hits.append(now)

            if now - self._last_sweep > self.window_seconds:
                self._sweep(now)

            return True

    def _trim(self, hits: "deque[float]", now: float) -> None:
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()

    def _sweep(self, now: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits]:
            del self._hits[key]
        self._last_sweep = now
