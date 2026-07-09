"""Единый владелец порогов, статусов и таксономии систем тела QIKI.

Срез 0 плана SelfModel (2026-07-09). До этого пороги warn/crit жили только в
консоли (orion_v/hardware_view_model/thresholds.py) — любой второй потребитель
(самоперцепция мозга) родил бы «второй вывод правды» с расхождениями из-за
разной логики, а не из-за данных. Теперь:
- числовые пороги и compare-функции — ЗДЕСЬ (консольный thresholds.py — тонкая
  обёртка, конвертирующая нейтральный статус в ViewStatus);
- таксономия систем «Я» (14 узлов, канон 01_BODY_CANON «идентичность») — ЗДЕСЬ;
- per-domain словари состояний (стыковка/связь/сенсоры/FSM) — ЗДЕСЬ (их же
  использует валидация видения: инъекция через wire-строки не проходит).

Нейтральный словарь статусов: "ok" | "warn" | "crit" | "no_data".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ComparisonMode = Literal["min", "max", "range"]
NodeStatus = Literal["ok", "warn", "crit", "no_data"]

# Power/EPS defaults and thresholds (stage 8.3.2)
DEFAULT_BATTERY_CAPACITY_WH = 500.0
EPSILON_POWER_W = 1e-6

POWER_SOC_WARN_PCT = 20.0
POWER_SOC_CRIT_PCT = 15.0
POWER_BUS_WARN_V = 22.0
POWER_BUS_CRIT_V = 20.0
POWER_RUNTIME_WARN_MIN = 20.0
POWER_RUNTIME_CRIT_MIN = 10.0

# Propulsion defaults and thresholds (stage 8.3.3)
DEFAULT_FUEL_TOTAL_G = 10000.0
PROPULSION_FUEL_WARN_PCT = 20.0
PROPULSION_FUEL_CRIT_PCT = 10.0
PROPULSION_BURN_WARN_MIN = 20.0
PROPULSION_BURN_CRIT_MIN = 10.0
PROPULSION_MOTOR_TEMP_WARN_C = 80.0
PROPULSION_MOTOR_TEMP_CRIT_C = 95.0

# Navigation thresholds (stage 8.3.4)
NAV_CONFIDENCE_WARN = 0.8
NAV_CONFIDENCE_LOW = 0.5
NAV_CONFIDENCE_CRIT = 0.2

# Comms thresholds (stage 8.3.9)
COMMS_LAT_WARN_MS = 200.0
COMMS_LAT_CRIT_MS = 500.0
COMMS_LOSS_WARN_PCT = 2.0
COMMS_LOSS_CRIT_PCT = 5.0
COMMS_AGE_WARN_S = 10.0
COMMS_AGE_CRIT_S = 30.0

# Thermal thresholds (stage 8.3.10)
THERMAL_CORE_WARN_C = 80.0
THERMAL_CORE_CRIT_C = 95.0
THERMAL_DELTA_WARN_C = 10.0
THERMAL_DELTA_CRIT_C = 20.0
THERMAL_TREND_WARN_C = 2.0

# Compute thresholds (stage 8.3.11)
COMPUTE_HEARTBEAT_WARN_S = 15.0
COMPUTE_HEARTBEAT_CRIT_S = 30.0
COMPUTE_CPU_WARN_PCT = 80.0
COMPUTE_CPU_CRIT_PCT = 95.0
COMPUTE_RAM_WARN_PCT = 85.0
COMPUTE_RAM_CRIT_PCT = 95.0
COMPUTE_TEMP_WARN_C = 80.0
COMPUTE_TEMP_CRIT_C = 95.0

# Docking thresholds (stage 8.3.6)
DOCK_MAX_ALIGN_WARN_DEG = 5.0
DOCK_MAX_ALIGN_CRIT_DEG = 10.0
DOCK_MAX_SPEED_WARN_MPS = 0.20
DOCK_MAX_SPEED_CRIT_MPS = 0.40
DOCK_MIN_DISTANCE_CAPTURE_M = 0.5

# Hull + Shields thresholds (stage 8.3.7)
HULL_INTEGRITY_WARN_PCT = 70.0
HULL_INTEGRITY_CRIT_PCT = 40.0
HULL_SECTOR_DAMAGE_WARN_PCT = 60.0
HULL_SECTOR_DAMAGE_CRIT_PCT = 80.0
HULL_STRESS_WARN = 0.8
HULL_STRESS_CRIT = 1.2

SHIELDS_LEVEL_WARN_PCT = 30.0
SHIELDS_LEVEL_CRIT_PCT = 10.0


@dataclass(frozen=True, slots=True)
class ThresholdSpec:
    mode: ComparisonMode
    warn: float | tuple[float, float]
    crit: float | tuple[float, float]


def status_by_min(value: float | None, warn_min: float, crit_min: float) -> NodeStatus:
    if value is None:
        return "no_data"
    if value <= crit_min:
        return "crit"
    if value <= warn_min:
        return "warn"
    return "ok"


def status_by_max(value: float | None, warn_max: float, crit_max: float) -> NodeStatus:
    if value is None:
        return "no_data"
    if value >= crit_max:
        return "crit"
    if value >= warn_max:
        return "warn"
    return "ok"


def status_by_range(
    value: float | None,
    ok_min: float,
    ok_max: float,
    warn_band: float | tuple[float, float],
) -> NodeStatus:
    if value is None:
        return "no_data"
    lower_band, upper_band = (warn_band, warn_band) if isinstance(warn_band, (int, float)) else warn_band
    warn_min = ok_min - lower_band
    warn_max = ok_max + upper_band
    if ok_min <= value <= ok_max:
        return "ok"
    if warn_min <= value <= warn_max:
        return "warn"
    return "crit"


# ── Таксономия систем «Я» (канон 01_BODY_CANON: идентичность тела) ──────────
# 14 узлов SelfModel: 13 физических/логистических + SAFE/гейтинг («что мне
# сейчас можно» — канон считает частью тела). id стабильны — контракт.
SELF_SYSTEM_IDS: dict[str, str] = {
    "power": "Питание",
    "thermal": "Тепло",
    "propulsion": "Двигатели",
    "hull": "Корпус",
    "compute": "Вычислитель",
    "comms": "Связь",
    "docking": "Стыковка",
    "sensors": "Сенсоры",
    "radar": "Радар",
    "navigation": "Навигация",
    "environment": "Среда",
    "body_structure": "Структура тела",
    "cargo": "Грузовой отсек",
    "safe_gating": "SAFE/гейтинг",
}

# ── Per-domain словари состояний (валидация wire-значений: не в словаре →
#    "unknown"; инъекция через строки телеметрии не доходит ни до промпта,
#    ни до SelfModel) ─────────────────────────────────────────────────────────
FSM_STATES = frozenset({"RUNNING", "PAUSED", "STOPPED"})
DOCKING_STATES = frozenset({"docked", "undocked", "docking", "undocking", "disabled"})
LINK_STATES = frozenset({"online", "offline", "degraded", "down"})
SENSOR_STATUSES = frozenset({"ok", "warn", "degraded", "failed", "crit", "na", "off"})
ORBIT_STATES = frozenset({"off", "stable", "elliptical", "decaying", "unknown"})
