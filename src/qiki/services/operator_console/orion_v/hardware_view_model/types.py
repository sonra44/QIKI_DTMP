from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ViewStatus(StrEnum):
    OK = "НОРМА"
    WARN = "ПРЕДУПРЕЖДЕНИЕ"
    CRIT = "КРИТИЧНО"
    NO_DATA = "НЕТ_ДАННЫХ"


STATUS_ORDER: dict[ViewStatus, int] = {
    ViewStatus.NO_DATA: 0,
    ViewStatus.OK: 1,
    ViewStatus.WARN: 2,
    ViewStatus.CRIT: 3,
}


@dataclass(slots=True)
class TelemetryField:
    key: str
    label: str
    value: Any
    unit: str
    status: ViewStatus
    hint: str
    ts: float | None = None
    # Evidence metadata (ADR-0014 / IF-POWER-TELEM). Optional: subsystems that do
    # not yet populate these leave defaults, so existing fields are unaffected.
    freshness: str | None = None  # "fresh" | "stale" | "unknown"
    trust_status: str | None = None  # "trusted" | "degraded" | "missing"
    reason_codes: tuple[str, ...] = ()


@dataclass(slots=True)
class SubsystemView:
    id: str
    title: str
    status: ViewStatus
    fields: list[TelemetryField]
    summary: str


@dataclass(slots=True)
class HardwareViewModel:
    system_status: ViewStatus
    subsystems: dict[str, SubsystemView]
    generated_at: float
