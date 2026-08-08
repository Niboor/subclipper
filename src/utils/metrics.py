import time
import functools
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque
from prometheus_client import Histogram, Counter, Gauge

_LOCK = threading.Lock()
_MAX_SAMPLES = 200

@dataclass
class _OperationStats:
    samples: Deque[float] = field(default_factory=lambda: deque(maxlen=_MAX_SAMPLES))
    count: int = 0
    total: float = 0.0
    min: float = float("inf")
    max: float = 0.0

_stats: dict[str, _OperationStats] = {}

_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30)
_DURATION = Histogram(
    "subclipper_operation_duration_seconds",
    "Duration of instrumented Subclipper operations",
    labelnames=["component", "operation"],
    buckets=_BUCKETS,
)
_ERRORS = Counter(
    "subclipper_operation_errors_total",
    "Count of instrumented operations that raised an exception",
    labelnames=["component", "operation"],
)
_INFLIGHT = Gauge(
    "subclipper_operation_inflight",
    "Currently in-progress instrumented operations",
    labelnames=["component", "operation"],
)

def _split(operation: str) -> tuple[str, str]:
    if ":" in operation:
        component, _, name = operation.partition(":")
        return component, name
    return "app", operation

def record(operation: str, duration_s: float, error: bool = False):
    component, name = _split(operation)
    _DURATION.labels(component=component, operation=name).observe(duration_s)
    if error:
        _ERRORS.labels(component=component, operation=name).inc()

    with _LOCK:
        stat = _stats.setdefault(operation, _OperationStats())
        stat.samples.append(duration_s)
        stat.count += 1
        stat.total += duration_s
        stat.min = min(stat.min, duration_s)
        stat.max = max(stat.max, duration_s)

def timed(operation: str):
    component, name = _split(operation)
    def decorator(fn: Callable):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            _INFLIGHT.labels(component=component, operation=name).inc()
            start = time.perf_counter()
            errored = False
            try:
                return fn(*args, **kwargs)
            except Exception:
                errored = True
                raise
            finally:
                record(operation, time.perf_counter() - start, error=errored)
                _INFLIGHT.labels(component=component, operation=name).dec()
        return wrapper
    return decorator

def snapshot() -> dict:
    with _LOCK:
        result = {}
        for name, stat in sorted(_stats.items()):
            samples = sorted(stat.samples)
            p50 = samples[len(samples) // 2] if samples else 0
            p95 = samples[int(len(samples) * 0.95)] if samples else 0
            result[name] = {
                "count": stat.count,
                "avg_ms": (stat.total / stat.count * 1000) if stat.count else 0,
                "min_ms": stat.min * 1000 if stat.count else 0,
                "max_ms": stat.max * 1000,
                "p50_ms": p50 * 1000,
                "p95_ms": p95 * 1000,
            }
        return result

def reset():
    with _LOCK:
        _stats.clear()