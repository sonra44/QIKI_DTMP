"""Тонкая обёртка над единым владельцем порогов (qiki.shared.body_status).

Срез 0 SelfModel (2026-07-09): числовые пороги и compare-логика переехали в
qiki/shared — иначе самоперцепция мозга стала бы «вторым выводом правды».
Здесь остаётся только конверсия нейтрального статуса в консольный ViewStatus;
все импорт-сайты консоли живут без изменений.
"""

from __future__ import annotations

# Константы и спецификация — реэкспорт единого владельца (не копия).
from qiki.shared.body_status import (  # noqa: F401
    COMMS_AGE_CRIT_S,
    COMMS_AGE_WARN_S,
    COMMS_LAT_CRIT_MS,
    COMMS_LAT_WARN_MS,
    COMMS_LOSS_CRIT_PCT,
    COMMS_LOSS_WARN_PCT,
    COMPUTE_CPU_CRIT_PCT,
    COMPUTE_CPU_WARN_PCT,
    COMPUTE_HEARTBEAT_CRIT_S,
    COMPUTE_HEARTBEAT_WARN_S,
    COMPUTE_RAM_CRIT_PCT,
    COMPUTE_RAM_WARN_PCT,
    COMPUTE_TEMP_CRIT_C,
    COMPUTE_TEMP_WARN_C,
    DEFAULT_BATTERY_CAPACITY_WH,
    DEFAULT_FUEL_TOTAL_G,
    DOCK_MAX_ALIGN_CRIT_DEG,
    DOCK_MAX_ALIGN_WARN_DEG,
    DOCK_MAX_SPEED_CRIT_MPS,
    DOCK_MAX_SPEED_WARN_MPS,
    DOCK_MIN_DISTANCE_CAPTURE_M,
    EPSILON_POWER_W,
    HULL_INTEGRITY_CRIT_PCT,
    HULL_INTEGRITY_WARN_PCT,
    HULL_SECTOR_DAMAGE_CRIT_PCT,
    HULL_SECTOR_DAMAGE_WARN_PCT,
    HULL_STRESS_CRIT,
    HULL_STRESS_WARN,
    NAV_CONFIDENCE_CRIT,
    NAV_CONFIDENCE_LOW,
    NAV_CONFIDENCE_WARN,
    POWER_BUS_CRIT_V,
    POWER_BUS_WARN_V,
    POWER_RUNTIME_CRIT_MIN,
    POWER_RUNTIME_WARN_MIN,
    POWER_SOC_CRIT_PCT,
    POWER_SOC_WARN_PCT,
    PROPULSION_BURN_CRIT_MIN,
    PROPULSION_BURN_WARN_MIN,
    PROPULSION_FUEL_CRIT_PCT,
    PROPULSION_FUEL_WARN_PCT,
    PROPULSION_MOTOR_TEMP_CRIT_C,
    PROPULSION_MOTOR_TEMP_WARN_C,
    SHIELDS_LEVEL_CRIT_PCT,
    SHIELDS_LEVEL_WARN_PCT,
    THERMAL_CORE_CRIT_C,
    THERMAL_CORE_WARN_C,
    THERMAL_DELTA_CRIT_C,
    THERMAL_DELTA_WARN_C,
    THERMAL_TREND_WARN_C,
    ComparisonMode,
    NodeStatus,
    ThresholdSpec,
)
from qiki.shared.body_status import (
    status_by_max as _shared_status_by_max,
    status_by_min as _shared_status_by_min,
    status_by_range as _shared_status_by_range,
)

from .types import ViewStatus

_STATUS_MAP: dict[str, ViewStatus] = {
    "ok": ViewStatus.OK,
    "warn": ViewStatus.WARN,
    "crit": ViewStatus.CRIT,
    "no_data": ViewStatus.NO_DATA,
}


def status_by_min(value: float | None, warn_min: float, crit_min: float) -> ViewStatus:
    return _STATUS_MAP[_shared_status_by_min(value, warn_min, crit_min)]


def status_by_max(value: float | None, warn_max: float, crit_max: float) -> ViewStatus:
    return _STATUS_MAP[_shared_status_by_max(value, warn_max, crit_max)]


def status_by_range(
    value: float | None,
    ok_min: float,
    ok_max: float,
    warn_band: float | tuple[float, float],
) -> ViewStatus:
    return _STATUS_MAP[_shared_status_by_range(value, ok_min, ok_max, warn_band)]
