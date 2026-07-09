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
    # Аудит 0052 (F3): физически невозможный SoC — не данные, не «stab»
    assert classify_cap_gate(-5.0) is None
    assert classify_cap_gate(150.0) is None


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
    # Аудит 0052 (F2): компакт-формат «cap70%▸БУСТ» ПЕРЕД таймером — на узком
    # экране клипается хвост чипа, безопасность-гейт терять нельзя
    assert "cap70%▸БУСТ" in pwr.anchor_text, pwr.anchor_text


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
        # Аудит 0052 (F): процент отслеживает ФАКТ (мутация «hardcode 70%»
        # переживала тесты — carries совпадала с константой, тут код-only)
        assert f"cap{cap:.0f}%" in pwr.anchor_text, (cap, pwr.anchor_text)


def test_pwr_chip_cap_gate_precedes_runtime_timer() -> None:
    """Аудит 0052 (F2): cap-гейт идёт ПЕРЕД «~мин» — клип узкого экрана
    съедает таймер, а не безопасность-гейт."""
    from qiki.services.operator_console.orion_v.operator_state import (
        build_operator_shell_state,
    )

    state = build_operator_shell_state(
        hardware_model=_model(
            {
                "power.soc_pct": 93.0,
                "power.supercap_soc_pct": 70.0,
                # runtime_min выводится коллектором из draw/capacity
                "power.draw_w": 100.0,
                "power.battery_wh": 500.0,
            }
        ),
        nats_state="connected",
    )
    pwr = next(chip for chip in state.chips if chip.label == "PWR")
    anchor = pwr.anchor_text
    assert "cap70%" in anchor and "~" in anchor, anchor
    assert anchor.index("cap70%") < anchor.index("~"), anchor


def test_status_bar_rerenders_when_only_cap_changes() -> None:
    """Аудит 0052 (HIGH): кэш-ключ ре-рендера чипа не включал anchor_text —
    cap-гейт залипал на ▸БУСТ при просевшем суперкапе (battery SoC не
    менялся). Регресс: смена ТОЛЬКО supercap обновляет лейбл."""
    import asyncio

    import pytest as _pytest

    _pytest.importorskip("textual")
    from textual.app import App, ComposeResult
    from textual.widgets import Button

    from qiki.services.operator_console.orion_v.operator_state import (
        build_operator_shell_state,
    )
    from qiki.services.operator_console.orion_v.widgets.status_bars import (
        OrionVStatusBars,
    )

    class _BarsApp(App[None]):
        def compose(self) -> ComposeResult:
            yield OrionVStatusBars(id="orionv-bars")

    async def _run() -> tuple[str, str]:
        app = _BarsApp()
        async with app.run_test(size=(200, 30)) as pilot:
            await pilot.pause()
            bars = app.query_one("#orionv-bars", OrionVStatusBars)

            def _label() -> str:
                return str(app.query_one("#orionv-status-power-action", Button).label)

            bars.set_state(
                build_operator_shell_state(
                    hardware_model=_model({"power.soc_pct": 80.0, "power.supercap_soc_pct": 80.0}),
                    nats_state="connected",
                )
            )
            await pilot.pause()
            first = _label()
            bars.set_state(
                build_operator_shell_state(
                    hardware_model=_model({"power.soc_pct": 80.0, "power.supercap_soc_pct": 10.0}),
                    nats_state="connected",
                )
            )
            await pilot.pause()
            return first, _label()

    first, second = asyncio.run(_run())
    assert "▸БУСТ" in first, first
    assert "▸СТАБ" in second, f"чип залип: {second!r} (был {first!r})"


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
