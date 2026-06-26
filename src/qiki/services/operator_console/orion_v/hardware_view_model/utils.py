from __future__ import annotations

import math
from typing import Any

from qiki.services.operator_console.orion_v.i18n_ru import tr

from .types import STATUS_ORDER, TelemetryField, ViewStatus


def fmt_missing() -> str:
    return "Нет данных"


def safe_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def safe_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def trend(values: list[float]) -> str:
    if len(values) < 2:
        return "нет данных"
    first, last = safe_float(values[0]), safe_float(values[-1])
    if first is None or last is None:
        return "нет данных"
    delta = last - first
    if abs(delta) < 0.1:
        return "стабильно"
    if delta > 0:
        return "растет"
    return "падает"


def mk_field(
    key: str,
    label: str,
    value: Any,
    unit: str = "",
    status: ViewStatus = ViewStatus.NO_DATA,
    hint: str = "",
    ts: float | None = None,
    *,
    i18n_key: str | None = None,
    freshness: str | None = None,
    trust_status: str | None = None,
    reason_codes: tuple[str, ...] = (),
) -> TelemetryField:
    rendered_value = fmt_missing() if value is None else value
    rendered_label = tr(i18n_key) if i18n_key else label
    return TelemetryField(
        key=key,
        label=rendered_label,
        value=rendered_value,
        unit=unit,
        status=status,
        hint=hint,
        ts=ts,
        freshness=freshness,
        trust_status=trust_status,
        reason_codes=reason_codes,
    )


def presence_evidence(
    value: Any,
    age_s: float | None = None,
    stale_after_s: float | None = None,
) -> dict[str, Any]:
    """Console-side evidence (ADR-0014 / IF-POWER-TELEM) for a telemetry field.

    - Missing field -> source missing (POWER_TELEM_MISSING).
    - Present but telemetry older than stale_after_s -> degraded (POWER_TELEM_STALE).
    - Present and fresh -> trusted.

    stale_after_s is a console-side staleness threshold (no power-specific canon SLA);
    the caller passes COMMS_AGE_CRIT_S to stay consistent with _data_freshness_state.
    """
    if value is None:
        return {"freshness": "unknown", "trust_status": "missing", "reason_codes": ("POWER_TELEM_MISSING",)}
    if age_s is not None and stale_after_s is not None and age_s > stale_after_s:
        return {"freshness": "stale", "trust_status": "degraded", "reason_codes": ("POWER_TELEM_STALE",)}
    return {"freshness": "fresh", "trust_status": "trusted", "reason_codes": ()}


def merge_status(a: ViewStatus, b: ViewStatus) -> ViewStatus:
    return a if STATUS_ORDER[a] >= STATUS_ORDER[b] else b


def normalize_sensor_status(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, bool):
        return "ONLINE" if value else "OFFLINE"
    if isinstance(value, (int, float)):
        return "ONLINE" if value != 0 else "OFFLINE"
    normalized = str(value).strip().lower()
    if normalized in {"", "none", "unknown", "n/a"}:
        return "UNKNOWN"
    if normalized in {"true", "1", "online", "up", "ok", "active", "enabled", "locked"}:
        return "ONLINE"
    if normalized in {"degraded", "warn", "warning", "crit", "critical"}:
        # IF-SENSOR runtime maps both warn and crit to SENSOR_DEGRADED; a "crit" status must
        # surface as a concern (DEGRADED -> WARN), never silently UNKNOWN/NO_DATA — nor, once an
        # enabled sensor falls through to .enabled, a misleading OK.
        return "DEGRADED"
    if normalized in {"false", "0", "offline", "down", "lost", "disabled", "disconnected"}:
        return "OFFLINE"
    return "UNKNOWN"


def fmt_duration_seconds(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return fmt_missing()
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"
