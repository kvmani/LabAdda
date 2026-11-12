"""A 60-second in-process cache of analytics results (AD-05), bounded in size.

Results hold no per-viewer data (authorization is checked on every request before and after
reading), so one cached copy serves every permitted console reader.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Hashable

TTL_SECONDS = 60.0
MAX_ENTRIES = 32


class ResultCache:
    def __init__(self, ttl: float = TTL_SECONDS, size: int = MAX_ENTRIES) -> None:
        self._ttl = ttl
        self._size = size
        self._lock = threading.Lock()
        self._entries: dict[Hashable, tuple[float, dict]] = {}

    def get(
        self, key: Hashable, build: Callable[[], dict], *, clock: Callable[[], float] = time.monotonic
    ) -> dict:
        """Return a fresh cached result or build, store and return a new one."""
        moment = clock()
        with self._lock:
            found = self._entries.get(key)
            if found and moment - found[0] < self._ttl:
                return found[1]
        result = build()
        with self._lock:
            if len(self._entries) >= self._size:
                self._entries.pop(min(self._entries, key=lambda name: self._entries[name][0]))
            self._entries[key] = (moment, result)
        return result

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


CACHE = ResultCache()
