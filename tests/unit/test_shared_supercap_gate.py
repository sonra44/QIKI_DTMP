"""Этап 8 (Z2/G3): shared-владелец порогов cap-гейта суперконденсатора.

Канон (BODY_CANON §13): SoC_cap = готовность к краткому пиковому действию;
«Пороговая логика: T_boost/T_hold» — элемент Power Plane (bot_gdd), численные
значения канон не задаёт — спека пакета Z2 фиксирует 0.6/0.3. Владелец —
ТОЛЬКО qiki/shared (анти-образец 0.17: локальные копии запрещены).
`_peak_state` (20/70, blocked/limited/ready) — ДРУГАЯ семантика (контур
блокировок), сознательно не трогается; унификация — отдельный срез.
"""

from __future__ import annotations

from qiki.shared.supercap_gate import (
    SUPERCAP_T_BOOST,
    SUPERCAP_T_HOLD,
    classify_cap_gate,
)


def test_thresholds_are_spec_values() -> None:
    assert SUPERCAP_T_BOOST == 0.6
    assert SUPERCAP_T_HOLD == 0.3


def test_gate_boundaries() -> None:
    assert classify_cap_gate(100.0) == "boost"
    assert classify_cap_gate(60.0) == "boost"  # ≥ T_boost включительно
    assert classify_cap_gate(59.9) == "hold"
    assert classify_cap_gate(30.0) == "hold"  # ≥ T_hold включительно
    assert classify_cap_gate(29.9) == "stab"
    assert classify_cap_gate(0.0) == "stab"


def test_gate_honest_none() -> None:
    assert classify_cap_gate(None) is None
    assert classify_cap_gate(float("nan")) is None


def _model(snapshot: dict[str, object]):
    from qiki.services.operator_console.orion_v.hardware_view_model import (
        HardwareCollector,
    )

    return HardwareCollector().update(snapshot)


def test_pwr_chip_carries_cap_gate() -> None:
    """Чип PWR несёт cap-сегмент: `… · cap 70% ▸БУСТ` (Z2)."""
    from qiki.services.operator_console.orion_v.operator_state import (
        build_operator_shell_state,
    )

    state = build_operator_shell_state(
        hardware_model=_model({"power.soc_pct": 93.0, "power.supercap_soc_pct": 70.0}),
        nats_state="connected",
    )
    pwr = next((chip for chip in state.chips if chip.label == "PWR"), None)
    assert pwr is not None, [chip.label for chip in state.chips]
    assert "cap 70%" in pwr.anchor_text, pwr.anchor_text
    assert "▸БУСТ" in pwr.anchor_text, pwr.anchor_text


def test_pwr_chip_cap_gate_hold_and_stab() -> None:
    from qiki.services.operator_console.orion_v.operator_state import (
        build_operator_shell_state,
    )

    for cap, code in ((45.0, "▸ДЕРЖ"), (10.0, "▸СТАБ")):
        state = build_operator_shell_state(
            hardware_model=_model({"power.soc_pct": 93.0, "power.supercap_soc_pct": cap}),
            nats_state="connected",
        )
        pwr = next(chip for chip in state.chips if chip.label == "PWR")
        assert code in pwr.anchor_text, (cap, pwr.anchor_text)


def test_pwr_chip_without_cap_data_has_no_segment() -> None:
    from qiki.services.operator_console.orion_v.operator_state import (
        build_operator_shell_state,
    )

    state = build_operator_shell_state(
        hardware_model=_model({"power.soc_pct": 93.0}),
        nats_state="connected",
    )
    pwr = next((chip for chip in state.chips if chip.label == "PWR"), None)
    if pwr is None:
        return  # без данных чип может отсутствовать целиком — тоже честно
    assert "cap" not in pwr.anchor_text, pwr.anchor_text
    assert "БУСТ" not in pwr.anchor_text and "ДЕРЖ" not in pwr.anchor_text
