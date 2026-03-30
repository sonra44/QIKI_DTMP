"""Clock abstractions for deterministic radar pipeline execution."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


class Clock(Protocol):
    def now(self) -> float:
        """Return current timestamp in seconds."""


@dataclass(frozen=True)
class SystemClock:
    """Production clock backed by wall time."""

    def now(self) -> float:
        return float(time.time())


@dataclass
class ReplayClock:
    """Mutable clock used by deterministic replay."""

    current_ts: float = 0.0

    def now(self) -> float:
        return float(self.current_ts)

    def set(self, ts: float) -> None:
        self.current_ts = float(ts)


@dataclass(frozen=True)
class CallableClock:
    """Compatibility wrapper for plain callables."""

    fn: Callable[[], float]

    def now(self) -> float:
        return float(self.fn())


def ensure_clock(clock: Clock | Callable[[], float] | None) -> Clock:
    if clock is None:
        return SystemClock()
    now_attr = getattr(clock, "now", None)
    if callable(now_attr):
        return clock  # type: ignore[return-value]
    return CallableClock(clock)
