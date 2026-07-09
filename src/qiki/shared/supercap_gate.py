"""Владелец порогов cap-гейта суперконденсатора (этап 8, Z2/G3).

Канон (BODY_CANON §13): SoC_cap = готовность к краткому пиковому действию;
«Пороговая логика: T_boost/T_hold» — элемент Power Plane (bot_gdd §Power).
Численные значения канон не задаёт — спека пакета Z2 фиксирует 0.6/0.3.
Анти-образец 0.17: локальные копии порогов запрещены — потребители (чип PWR
консоли) читают ТОЛЬКО отсюда.

Смежный владелец `power_thermal_view_model._peak_state` (20/70,
blocked/limited/ready) — ДРУГАЯ семантика (контур блокировок команд);
унификация — отдельный срез.
"""

from __future__ import annotations

import math

# Пороги в процентах SoC_cap (спека Z2: T_boost=0.6, T_hold=0.3 от полного).
SUPERCAP_T_BOOST = 0.6
SUPERCAP_T_HOLD = 0.3


def classify_cap_gate(supercap_soc_pct: float | None) -> str | None:
    """SoC_cap (0..100 %) → "boost" | "hold" | "stab" | None (нет данных).

    boost — готов к пиковому действию (≥60%); hold — держать заряд,
    пик ограничен (30–60%); stab — только стабилизация (<30%).
    Не-конечные значения — честное None, не выдуманный гейт.
    """
    if supercap_soc_pct is None:
        return None
    try:
        value = float(supercap_soc_pct)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    # Аудит 0052 (F3): физически невозможный SoC (вне 0..100) — не данные;
    # отрицательное значение клеймилось как «stab» вместо честного None.
    if not (0.0 <= value <= 100.0):
        return None
    if value >= SUPERCAP_T_BOOST * 100.0:
        return "boost"
    if value >= SUPERCAP_T_HOLD * 100.0:
        return "hold"
    return "stab"
