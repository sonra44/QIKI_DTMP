"""Единый владелец порогов и формулы риска сближения (гэп G5, этап 6).

Зеркало формулы `q_core_agent/core/radar_situation_engine.py` (:118-120,
:292-315): closing = max(0, −vr_mps); t_cpa = range / closing. Значения
констант = env-дефолты движка (RADAR_CPA_WARN_T и т.д.) — движок агента пока
читает env с теми же дефолтами; унификация его конфигурации на этот модуль —
отдельный этап (Non-goal здесь). Урок аудита 0.17: новые локальные копии
порогов запрещены — потребители импортируют отсюда.

Stateless-упрощение: правило CLOSING_FAST движка дополнительно требует
подтверждённого тренда «дистанция падает» (трейл кадров); здесь классификация
по одному замеру — высокая скорость сближения даёт warn без трейла.
"""

from __future__ import annotations

import math
from typing import Literal

RADAR_CPA_WARN_T_S = 20.0
RADAR_CPA_CRIT_T_S = 8.0
RADAR_CPA_CRIT_DIST_M = 150.0
RADAR_CLOSING_SPEED_WARN_MPS = 5.0

_EPS_CLOSING_MPS = 1e-9

RiskLevel = Literal["ok", "warn", "crit"]


def classify_approach_risk(range_m: float, vr_mps: float) -> tuple[RiskLevel, float | None]:
    """→ (уровень риска, время до сближения в секундах | None).

    Знаковая конвенция vr_mps — как у RadarTrackModel: отрицательное значение
    = сближение. Уровень derived из одного замера (см. docstring модуля).
    """
    range_f = float(range_m)
    vr_f = float(vr_mps)
    if not (math.isfinite(range_f) and math.isfinite(vr_f)) or range_f < 0.0:
        return ("ok", None)  # мусорный вход не классифицируем и не пугаем
    closing = max(0.0, -vr_f)
    if closing <= _EPS_CLOSING_MPS:
        return ("ok", None)
    t_cpa = range_f / closing
    if t_cpa < RADAR_CPA_CRIT_T_S and range_f < RADAR_CPA_CRIT_DIST_M:
        return ("crit", t_cpa)
    if t_cpa < RADAR_CPA_WARN_T_S or closing > RADAR_CLOSING_SPEED_WARN_MPS:
        return ("warn", t_cpa)
    return ("ok", t_cpa)
