"""Срез «Быстрая честность» (карта AUDIT_2026-07-10, C2/C3/C4).

Один физический факт обязан давать ОДИН класс тревоги на всех панелях.
Канон сравнения — shared/body_status: status_by_min = «<=» (граница — худший
класс, консервативно), status_by_max = «>=».

C2: cockpit._thermal_block держал литералы 90/80 против канона
THERMAL_CORE_CRIT_C=95/WARN_C=80 — в полосе 90-94° F1 crit, F2 warn.
C3: cockpit._energy_block и modules/power сравнивали «<» против канонного
«<=» — ровно на пороге классы панелей расходились.
C4: staleness тепла — литерал 30.0 мимо владельца COMMS_AGE_CRIT_S.
"""

from __future__ import annotations

import pytest

from qiki.shared.body_status import (
    POWER_SOC_CRIT_PCT,
    POWER_SOC_WARN_PCT,
    THERMAL_CORE_CRIT_C,
    THERMAL_CORE_WARN_C,
    status_by_max,
    status_by_min,
)


def _cockpit():
    pytest.importorskip("textual")
    from tests.unit.test_orion_v_cockpit import _CaptureCockpit

    screen = _CaptureCockpit()
    screen.set_state(telemetry={}, nats_connected=True, active_incidents=0, incidents=[])
    return screen


# ── C2: температура ядра — класс совпадает с каноном на всей шкале ───────────

def _thermal_severity(screen, core_c: float) -> str:
    severity, lines = screen._thermal_block(
        {"thermal": {"core_c": core_c, "nodes": []}}
    )
    return severity


def test_core_between_90_and_95_is_warn_everywhere() -> None:
    """Полоса 90-94°: канон (crit=95) говорит warn — F1 не имеет права кричать crit."""
    screen = _cockpit()
    canon = status_by_max(92.0, THERMAL_CORE_WARN_C, THERMAL_CORE_CRIT_C)
    assert canon == "warn"
    assert _thermal_severity(screen, 92.0) == "warn", (
        "cockpit кричит crit при 92° — литерал 90 против канона 95 (C2)"
    )


def test_core_at_canon_crit_is_crit() -> None:
    screen = _cockpit()
    assert _thermal_severity(screen, THERMAL_CORE_CRIT_C) == "crit"
    assert _thermal_severity(screen, THERMAL_CORE_CRIT_C + 5.0) == "crit"


def test_core_at_canon_warn_boundary() -> None:
    screen = _cockpit()
    canon = status_by_max(THERMAL_CORE_WARN_C, THERMAL_CORE_WARN_C, THERMAL_CORE_CRIT_C)
    assert _thermal_severity(screen, THERMAL_CORE_WARN_C) == canon
    assert _thermal_severity(screen, THERMAL_CORE_WARN_C - 0.5) == "ok"


# ── C3: SoC — граничное значение даёт один класс на всех панелях ─────────────

def test_soc_boundary_class_consistent_across_panels() -> None:
    """SoC ровно на пороге: канон status_by_min = «<=» → худший класс.
    cockpit._energy_block и modules/power использовали «<» — расходились."""
    screen = _cockpit()

    canon_at_crit = status_by_min(POWER_SOC_CRIT_PCT, POWER_SOC_WARN_PCT, POWER_SOC_CRIT_PCT)
    assert canon_at_crit == "crit"

    severity, lines = screen._energy_block(
        {"power": {"soc_pct": POWER_SOC_CRIT_PCT}}
    )
    assert severity == "crit", (
        f"cockpit при SoC=={POWER_SOC_CRIT_PCT} даёт {severity!r}, канон — crit (C3)"
    )

    canon_at_warn = status_by_min(POWER_SOC_WARN_PCT, POWER_SOC_WARN_PCT, POWER_SOC_CRIT_PCT)
    assert canon_at_warn == "warn"
    severity, lines = screen._energy_block(
        {"power": {"soc_pct": POWER_SOC_WARN_PCT}}
    )
    assert severity == "warn", (
        f"cockpit при SoC=={POWER_SOC_WARN_PCT} даёт {severity!r}, канон — warn (C3)"
    )


def test_soc_boundary_module_power_matches_canon() -> None:
    from qiki.services.operator_console.orion_v.i18n_ru import tr
    from qiki.services.operator_console.orion_v.modules.power import PowerSubsystemModule

    summary = PowerSubsystemModule().render_summary(
        {"telemetry": {"power": {"soc_pct": POWER_SOC_CRIT_PCT, "bus_v": 28.0}}}
    )
    assert tr("crit") in summary, (
        f"modules/power при SoC=={POWER_SOC_CRIT_PCT} без {tr('crit')!r}: {summary[:120]} (C3)"
    )


# ── C4: staleness тепла — порог из владельца, не литерал ─────────────────────

def test_thermal_staleness_follows_shared_threshold(monkeypatch) -> None:
    """Связь с владельцем: подменяем константу — порог обязан сдвинуться.
    Литерал 30.0 эту связь рвал (C4)."""
    import qiki.services.operator_console.orion_v.screens.cockpit as cockpit_module

    screen = _cockpit()
    monkeypatch.setattr(cockpit_module, "COMMS_AGE_CRIT_S", 5.0, raising=False)
    line = screen._thermal_evidence_line(
        {"thermal": {"age_s": 10.0, "core_c": 25.0, "nodes": []}}
    )
    assert "degraded" in line or "УСТАРЕЛО" in line, (
        f"staleness не сдвинулась за константой (порог-литерал?): {line}"
    )
