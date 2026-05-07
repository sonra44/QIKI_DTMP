from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class OperatorActionHistoryEntry:
    action_key: str
    label: str
    state: str
    message: str
    started_at: str
    finished_at: str | None = None

    @property
    def timestamp(self) -> str:
        return self.finished_at or self.started_at


@dataclass(slots=True)
class OperatorActionHistory:
    max_entries: int = 50
    entries: list[OperatorActionHistoryEntry] = field(default_factory=list)

    def start(self, action_key: str, label: str, *, message: str = "running", timestamp: str | None = None) -> None:
        self.record(
            action_key,
            label,
            "running",
            message,
            started_at=timestamp,
            finished_at=None,
        )

    def finish(
        self,
        action_key: str,
        *,
        state: str,
        message: str,
        timestamp: str | None = None,
    ) -> None:
        finished_at = timestamp or utc_now_iso()
        for index in range(len(self.entries) - 1, -1, -1):
            entry = self.entries[index]
            if entry.action_key == action_key and entry.state == "running" and entry.finished_at is None:
                self.entries[index] = OperatorActionHistoryEntry(
                    action_key=entry.action_key,
                    label=entry.label,
                    state=state,
                    message=message,
                    started_at=entry.started_at,
                    finished_at=finished_at,
                )
                return
        self.record(action_key, action_key, state, message, started_at=finished_at, finished_at=finished_at)

    def record(
        self,
        action_key: str,
        label: str,
        state: str,
        message: str,
        *,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        timestamp = started_at or utc_now_iso()
        self.entries.append(
            OperatorActionHistoryEntry(
                action_key=action_key,
                label=label,
                state=state,
                message=message,
                started_at=timestamp,
                finished_at=finished_at,
            )
        )
        self._trim()

    def latest(self, *, limit: int = 8) -> list[OperatorActionHistoryEntry]:
        if limit <= 0:
            return []
        return list(reversed(self.entries[-limit:]))

    def extend(self, entries: Iterable[OperatorActionHistoryEntry]) -> None:
        self.entries.extend(entries)
        self._trim()

    def _trim(self) -> None:
        if self.max_entries <= 0:
            self.entries.clear()
            return
        overflow = len(self.entries) - self.max_entries
        if overflow > 0:
            del self.entries[:overflow]
