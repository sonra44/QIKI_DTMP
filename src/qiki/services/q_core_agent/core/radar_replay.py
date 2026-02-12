"""Deterministic replay and timeline cursor for radar traces."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .radar_clock import ReplayClock


@dataclass(frozen=True)
class TimelineState:
    current_ts: float
    speed: float
    paused: bool
    cursor: int
    total_events: int


def load_trace(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            row = line.strip()
            if not row:
                continue
            parsed = json.loads(row)
            if isinstance(parsed, dict):
                rows.append(parsed)
    rows.sort(key=lambda item: float(item.get("ts", 0.0)))
    return rows


class RadarReplayEngine:
    def __init__(
        self,
        events: list[dict[str, Any]],
        *,
        speed: float = 1.0,
        step: bool = False,
        clock: ReplayClock | None = None,
    ) -> None:
        self._events = sorted(events, key=lambda item: float(item.get("ts", 0.0)))
        safe_speed = float(speed) if speed > 0 else 1.0
        initial_ts = float(self._events[0].get("ts", 0.0)) if self._events else 0.0
        self._clock = clock or ReplayClock(initial_ts)
        self._state = TimelineState(
            current_ts=initial_ts,
            speed=safe_speed,
            paused=False,
            cursor=0,
            total_events=len(self._events),
        )
        self._step_mode = bool(step)

    @property
    def clock(self) -> ReplayClock:
        return self._clock

    @property
    def timeline(self) -> TimelineState:
        return self._state

    @property
    def has_pending(self) -> bool:
        return self._state.cursor < self._state.total_events

    def peek_next(self) -> dict[str, Any] | None:
        if not self.has_pending:
            return None
        return self._events[self._state.cursor]

    def pause(self) -> None:
        self._state = TimelineState(
            current_ts=self._state.current_ts,
            speed=self._state.speed,
            paused=True,
            cursor=self._state.cursor,
            total_events=self._state.total_events,
        )

    def resume(self) -> None:
        self._state = TimelineState(
            current_ts=self._state.current_ts,
            speed=self._state.speed,
            paused=False,
            cursor=self._state.cursor,
            total_events=self._state.total_events,
        )

    def jump_to_ts(self, ts: float) -> None:
        target = float(ts)
        idx = 0
        for i, event in enumerate(self._events):
            if float(event.get("ts", 0.0)) >= target:
                idx = i
                break
        else:
            idx = len(self._events)
        self._state = TimelineState(
            current_ts=target,
            speed=self._state.speed,
            paused=self._state.paused,
            cursor=idx,
            total_events=self._state.total_events,
        )
        self._clock.set(target)

    def jump_to_event_type(self, event_type: str) -> bool:
        target = str(event_type).strip()
        if not target:
            return False
        for idx in range(self._state.cursor, len(self._events)):
            if str(self._events[idx].get("event_type", "")) == target:
                ts = float(self._events[idx].get("ts", self._state.current_ts))
                self._state = TimelineState(
                    current_ts=ts,
                    speed=self._state.speed,
                    paused=self._state.paused,
                    cursor=idx,
                    total_events=self._state.total_events,
                )
                self._clock.set(ts)
                return True
        return False

    def jump_to_situation_id(self, situation_id: str) -> bool:
        target = str(situation_id).strip()
        if not target:
            return False
        for idx in range(self._state.cursor, len(self._events)):
            payload = self._events[idx].get("payload", {})
            if not isinstance(payload, dict):
                continue
            if str(payload.get("situation_id", "")) == target:
                ts = float(self._events[idx].get("ts", self._state.current_ts))
                self._state = TimelineState(
                    current_ts=ts,
                    speed=self._state.speed,
                    paused=self._state.paused,
                    cursor=idx,
                    total_events=self._state.total_events,
                )
                self._clock.set(ts)
                return True
        return False

    def next_batch(self) -> list[dict[str, Any]]:
        if self._state.paused or not self.has_pending:
            return []
        cursor = self._state.cursor
        first = self._events[cursor]
        first_ts = float(first.get("ts", self._state.current_ts))
        batch: list[dict[str, Any]] = [first]
        cursor += 1
        if not self._step_mode:
            while cursor < len(self._events):
                event = self._events[cursor]
                if float(event.get("ts", first_ts)) != first_ts:
                    break
                batch.append(event)
                cursor += 1
        self._state = TimelineState(
            current_ts=first_ts,
            speed=self._state.speed,
            paused=self._state.paused,
            cursor=cursor,
            total_events=self._state.total_events,
        )
        self._clock.set(first_ts)
        return batch

    def replay_events(self, *, speed: float | None = None, step: bool | None = None) -> Iterator[dict[str, Any]]:
        if speed is not None and speed > 0:
            self._state = TimelineState(
                current_ts=self._state.current_ts,
                speed=float(speed),
                paused=self._state.paused,
                cursor=self._state.cursor,
                total_events=self._state.total_events,
            )
        if step is not None:
            self._step_mode = bool(step)

        prev_ts: float | None = None
        while self.has_pending:
            while self._state.paused:
                time.sleep(0.01)
            batch = self.next_batch()
            if not batch:
                break
            current_ts = float(batch[-1].get("ts", self._state.current_ts))
            if prev_ts is not None and not self._step_mode:
                delta = max(0.0, current_ts - prev_ts)
                delay = delta / max(0.001, self._state.speed)
                if delay > 0.0:
                    time.sleep(delay)
            prev_ts = current_ts
            for event in batch:
                yield event


def replay_events(events: list[dict[str, Any]], speed: float = 1.0, step: bool = False) -> Iterator[dict[str, Any]]:
    engine = RadarReplayEngine(events, speed=speed, step=step)
    yield from engine.replay_events()


def jump_to_ts(engine: RadarReplayEngine, ts: float) -> None:
    engine.jump_to_ts(ts)


def pause(engine: RadarReplayEngine) -> None:
    engine.pause()


def resume(engine: RadarReplayEngine) -> None:
    engine.resume()
