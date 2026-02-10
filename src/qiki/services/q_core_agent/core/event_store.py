"""In-memory event store for truthful system fact journaling."""

from __future__ import annotations

import json
import os
import time
from collections import deque
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Optional
from uuid import uuid4


class TruthState(str, Enum):
    OK = "OK"
    NO_DATA = "NO_DATA"
    FALLBACK = "FALLBACK"
    INVALID = "INVALID"


@dataclass(frozen=True)
class SystemEvent:
    event_id: str
    ts: float
    subsystem: str
    event_type: str
    payload: dict[str, Any]
    tick_id: Optional[str]
    truth_state: TruthState
    reason: str

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["truth_state"] = self.truth_state.value
        return data


def _truth_state_from_any(value: TruthState | str) -> TruthState:
    if isinstance(value, TruthState):
        return value
    normalized = str(value or "").strip().upper()
    for state in TruthState:
        if state.value == normalized:
            return state
    return TruthState.INVALID


def _is_enabled(raw: str) -> bool:
    return raw.strip().lower() not in {"0", "false", "no", "off"}


class EventStore:
    def __init__(self, maxlen: int = 1000, enabled: bool = True):
        self.maxlen = max(1, int(maxlen))
        self.enabled = bool(enabled)
        self._events: Deque[SystemEvent] = deque(maxlen=self.maxlen)

    @classmethod
    def from_env(cls) -> "EventStore":
        maxlen_raw = os.getenv("QIKI_EVENT_STORE_MAXLEN", "1000")
        enable_raw = os.getenv("QIKI_EVENT_STORE_ENABLE", "true")
        try:
            maxlen = int(maxlen_raw)
        except Exception:
            maxlen = 1000
        return cls(maxlen=maxlen, enabled=_is_enabled(enable_raw))

    def append(self, event: SystemEvent) -> Optional[SystemEvent]:
        if not self.enabled:
            return None
        self._events.append(event)
        return event

    def append_new(
        self,
        *,
        subsystem: str,
        event_type: str,
        payload: dict[str, Any],
        truth_state: TruthState | str = TruthState.OK,
        reason: str = "",
        tick_id: Optional[str] = None,
    ) -> Optional[SystemEvent]:
        event = SystemEvent(
            event_id=str(uuid4()),
            ts=time.time(),
            subsystem=str(subsystem),
            event_type=str(event_type),
            payload=dict(payload),
            tick_id=tick_id,
            truth_state=_truth_state_from_any(truth_state),
            reason=str(reason or ""),
        )
        return self.append(event)

    def recent(self, n: int = 20) -> list[SystemEvent]:
        limit = max(0, int(n))
        if limit == 0:
            return []
        return list(self._events)[-limit:]

    def filter(
        self,
        *,
        subsystem: Optional[str] = None,
        event_type: Optional[str] = None,
        truth_state: Optional[TruthState | str] = None,
    ) -> list[SystemEvent]:
        expected_truth: Optional[TruthState] = None
        if truth_state is not None:
            expected_truth = _truth_state_from_any(truth_state)
        result: list[SystemEvent] = []
        for event in self._events:
            if subsystem is not None and event.subsystem != subsystem:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            if expected_truth is not None and event.truth_state != expected_truth:
                continue
            result.append(event)
        return result

    def export_jsonl(self, path: str) -> int:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with out_path.open("w", encoding="utf-8") as handle:
            for event in self._events:
                handle.write(json.dumps(event.to_json_dict(), ensure_ascii=True))
                handle.write("\n")
                count += 1
        return count

