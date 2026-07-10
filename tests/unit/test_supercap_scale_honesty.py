"""Срез C5 «cap-унификация» (карта AUDIT_2026-07-10, хвост task-0051).

Один физический факт (SoC_cap) обязан давать ОДНУ шкалу готовности.
Владелец — qiki/shared/supercap_gate (T_boost=0.6 / T_hold=0.3, спека Z2):
чип PWR классифицирует boost/hold/stab по 60/30, а контур блокировок
команд `_peak_state` держал локальные 20/70 — при SoC_cap 61-69% чип
кричал «▸БУСТ» (готов к пику), а карточка F2 — «limited» (пик ограничен).

Соответствие шкал: boost→ready, hold→limited, stab→blocked, None→unknown.
"""

from __future__ import annotations

from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    build_power_thermal_console_view_model,
)
from qiki.shared.supercap_gate import (
    SUPERCAP_T_BOOST,
    SUPERCAP_T_HOLD,
    classify_cap_gate,
)

_BOOST_PCT = SUPERCAP_T_BOOST * 100.0
_HOLD_PCT = SUPERCAP_T_HOLD * 100.0


def test_boost_zone_is_ready_not_limited() -> None:
    """61%: чип PWR говорит boost — карточка не имеет права говорить limited."""
    assert classify_cap_gate(61.0) == "boost"
    vm = build_power_thermal_console_view_model(supercap_soc_pct=61)
    assert vm.peak_ready is True
    assert vm.peak_readiness == "ready", (
        "SoC_cap=61%: чип ▸БУСТ, а контур блокировок limited — две шкалы (C5)"
    )
    assert "PEAK_LIMITED" not in vm.reason_codes


def test_hold_zone_is_limited() -> None:
    """45% (hold): пик ограничен в обеих шкалах."""
    assert classify_cap_gate(45.0) == "hold"
    vm = build_power_thermal_console_view_model(supercap_soc_pct=45)
    assert vm.peak_ready is False
    assert vm.peak_readiness == "limited"
    assert "PEAK_LIMITED" in vm.reason_codes


def test_stab_zone_is_blocked() -> None:
    """25% (stab у владельца) — блок; локальная шкала считала это limited."""
    assert classify_cap_gate(25.0) == "stab"
    vm = build_power_thermal_console_view_model(supercap_soc_pct=25)
    assert vm.peak_ready is False
    assert vm.peak_readiness == "blocked", (
        "SoC_cap=25%: владелец говорит stab, а контур блокировок limited (C5)"
    )
    assert "CAP_LOW" in vm.reason_codes


def test_boundaries_match_owner_exactly() -> None:
    """Границы шкалы — ровно пороги владельца, без локальных копий."""
    at_boost = build_power_thermal_console_view_model(supercap_soc_pct=int(_BOOST_PCT))
    assert at_boost.peak_readiness == "ready"

    below_boost = build_power_thermal_console_view_model(
        supercap_soc_pct=int(_BOOST_PCT) - 1
    )
    assert below_boost.peak_readiness == "limited"

    at_hold = build_power_thermal_console_view_model(supercap_soc_pct=int(_HOLD_PCT))
    assert at_hold.peak_readiness == "limited"

    below_hold = build_power_thermal_console_view_model(
        supercap_soc_pct=int(_HOLD_PCT) - 1
    )
    assert below_hold.peak_readiness == "blocked"


def test_unknown_cap_stays_unknown() -> None:
    vm = build_power_thermal_console_view_model(supercap_soc_pct=None)
    assert vm.peak_ready is False
    assert vm.peak_readiness == "unknown"
    assert "POWER_TELEM_MISSING" in vm.reason_codes


def test_fractional_boundary_matches_chip_scale() -> None:
    """59.6% (float): чип классифицирует hold — карточка обязана limited.
    Усечение к int (59) даёт то же — но классификация идёт по сырому float."""
    assert classify_cap_gate(59.6) == "hold"
    vm = build_power_thermal_console_view_model(supercap_soc_pct=59.6)
    assert vm.peak_readiness == "limited"


def test_out_of_range_fractional_is_unknown_like_owner() -> None:
    """C5-аудит: 100.4 усекался в 100 → ready, а чип честно unknown;
    −0.5 усекался в 0 → blocked. Guard владельца обязан наследоваться."""
    for bogus in (100.4, 100.6, -0.5, -0.9, 150.0):
        assert classify_cap_gate(bogus) is None, bogus
        vm = build_power_thermal_console_view_model(supercap_soc_pct=bogus)
        assert vm.peak_readiness == "unknown", (
            f"SoC_cap={bogus}: карточка {vm.peak_readiness!r}, чип unknown (guard)"
        )


def test_non_finite_cap_does_not_crash_adapter() -> None:
    """inf в телеметрии: владелец возвращает None; адаптер не имеет права
    падать OverflowError на int(float('inf'))."""
    for bogus in (float("inf"), float("-inf"), float("nan")):
        vm = build_power_thermal_console_view_model(supercap_soc_pct=bogus)
        assert vm.peak_readiness == "unknown"
