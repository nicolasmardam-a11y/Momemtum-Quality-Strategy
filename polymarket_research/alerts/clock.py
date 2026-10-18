"""Wall clock corrected to the Data API's clock.

Every time decision that is compared with block timestamps (the ``end`` of the poll
window, "too old to alert", detection lag, in-play) must use the server's notion of
"now". A machine without a battery-backed clock (a Raspberry Pi) can boot hours or
days off until NTP syncs, and a local clock behind by more than a day made ``end``
(now + 1 day) fall before the newest rows, which were then never requested while the
watermark (taken from the HTTP ``Date`` header) moved past them.

``ServerClock`` is a drop-in ``Callable[[], float]``: local time plus the offset last
observed from a fresh response's ``Date`` (+ ``Age`` when served from a cache). The
``Date`` header has one-second resolution, so offsets below ``min_correction_s`` are
ignored and a perfectly synced machine keeps using its own clock unchanged.
"""
from __future__ import annotations

import time
from typing import Callable


class ServerClock:
    def __init__(self, local: Callable[[], float] = time.time, *, min_correction_s: float = 2.0) -> None:
        self.local = local
        self.min_correction_s = min_correction_s
        self.offset = 0.0           # server minus local, seconds
        self.observed_at: float | None = None

    def __call__(self) -> float:
        return self.local() + self.offset

    def observe(self, server_now: float | None) -> None:
        """Update the offset from one response (``server_now`` = Date + Age, epoch seconds)."""
        if server_now is None:
            return
        local = self.local()
        est = server_now + 0.5 - local          # Date is floored to the second
        if abs(est) < self.min_correction_s:
            est = 0.0
        if abs(est - self.offset) >= self.min_correction_s or (est == 0.0 and self.offset != 0.0):
            self.offset = est
        self.observed_at = local


def as_server_clock(clock: Callable[[], float]) -> ServerClock:
    return clock if isinstance(clock, ServerClock) else ServerClock(clock)
