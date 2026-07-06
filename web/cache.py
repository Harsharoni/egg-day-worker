import threading
import time
from typing import Callable, TypeVar

from config import SITE_CACHE_TTL_SECONDS

T = TypeVar("T")


class TTLCache:
    """Thread-safe TTL cache. Compute runs under the lock (single-flight):
    concurrent misses for the same key produce one DB hit, the rest wait.
    Values are pandas-heavy but small; serializing computes is fine at this
    traffic level. RLock, not Lock: computes may nest (a series compute
    reads the cached history through the same cache)."""

    def __init__(self, ttl_seconds: float = SITE_CACHE_TTL_SECONDS):
        self.ttl = ttl_seconds
        self._lock = threading.RLock()
        self._store: dict[str, tuple[float, object]] = {}

    def get_or_compute(self, key: str, fn: Callable[[], T]) -> T:
        with self._lock:
            hit = self._store.get(key)
            if hit is not None and time.monotonic() - hit[0] < self.ttl:
                return hit[1]
            value = fn()
            self._store[key] = (time.monotonic(), value)
            return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


cache = TTLCache()
