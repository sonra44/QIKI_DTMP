from __future__ import annotations

import math
from typing import Any

from qiki.services.operator_console.orion_v.i18n_ru import tr


def telemetry_from_state(state: dict[str, Any]) -> dict[str, Any]:
    telemetry = state.get("telemetry")
    if isinstance(telemetry, dict):
        return telemetry
    return {}


def pick_num(payload: dict[str, Any], path: list[str]) -> float | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        num = float(value)
        if math.isfinite(num):
            return num
    return None


def pick_text(payload: dict[str, Any], path: list[str]) -> str:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return ""
        value = value[key]
    if value is None:
        return ""
    return str(value).strip()


def status_tag(ok: bool, warn: bool, crit: bool) -> str:
    if crit:
        return tr("crit")
    if warn:
        return tr("warn")
    if ok:
        return tr("ok")
    return tr("warn")
