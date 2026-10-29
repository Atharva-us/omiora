"""In-process sliding-window limiter for sign-in attempts.

Limitation: state is per process. With several API processes the effective limit is multiplied by
the process count; a shared store (Redis or a table) is required before horizontal scaling. Run
creation, the expensive operation, is limited from the database instead (see services/runs.py).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float, clock=time.monotonic) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> float | None:
        """Records an attempt. Returns seconds to wait if the limit is exceeded, else None."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return self._window - (now - hits[0])
            hits.append(now)
            return None

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
