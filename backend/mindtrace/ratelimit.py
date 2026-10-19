"""In-memory rate limiting for /api/analyze.

Per-client sliding windows (minute, hour) plus a global per-UTC-day cap. State lives in
the process, which suits a single-instance deployment such as Render's free tier; with
several instances each one enforces its own limits.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Callable

_SWEEP_EVERY = 500


class RateLimiter:
    def __init__(
        self,
        per_minute: int = 0,
        per_hour: int = 0,
        daily_cap: int = 0,
        clock: Callable[[], float] = time.time,
    ):
        self.per_minute = per_minute
        self.per_hour = per_hour
        self.daily_cap = daily_cap
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._day: int | None = None
        self._day_count = 0
        self._checks = 0

    @property
    def enabled(self) -> bool:
        return bool(self.per_minute or self.per_hour or self.daily_cap)

    def check(self, key: str) -> float | None:
        """Record a request from `key`. Returns None if allowed, otherwise the number of
        seconds the client should wait before retrying."""
        if not self.enabled:
            return None
        now = self._clock()
        self._checks += 1
        if self._checks % _SWEEP_EVERY == 0:
            self._sweep(now)

        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= 3600:
            hits.popleft()

        if self.per_minute:
            recent = [t for t in hits if now - t < 60]
            if len(recent) >= self.per_minute:
                return max(1.0, 60 - (now - recent[0]))
        if self.per_hour and len(hits) >= self.per_hour:
            return max(1.0, 3600 - (now - hits[0]))

        day = int(now // 86400)
        if day != self._day:
            self._day, self._day_count = day, 0
        if self.daily_cap and self._day_count >= self.daily_cap:
            return max(1.0, (day + 1) * 86400 - now)

        hits.append(now)
        self._day_count += 1
        return None

    def _sweep(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] >= 3600]:
            del self._hits[key]
