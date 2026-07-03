from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector
from qiki.services.operator_console.orion_v.operator_state import build_operator_shell_state
from qiki.services.operator_console.orion_v.widgets.status_bars import OrionVStatusBars


class _StatusBarsApp(App[None]):
    def compose(self) -> ComposeResult:
        yield OrionVStatusBars(id="orionv-bars")


def _model(snapshot: dict[str, object]):
    return HardwareCollector().update(snapshot)


@pytest.mark.asyncio
async def test_status_bars_render_compact_chips_from_hardware_model() -> None:
    pytest.importorskip("textual")

    app = _StatusBarsApp()
    async with app.run_test(size=(160, 30)) as pilot:
        await pilot.pause()

        bars = app.query_one("#orionv-bars", OrionVStatusBars)
        bars.set_state(
            build_operator_shell_state(
                hardware_model=_model(
                    {
                        "power.soc_pct": 48.0,
                        "thermal.core_c": 81.0,
                        "propulsion.fuel_pct": 55.0,
                        "hull.integrity": 92.0,
                        "compute.cpu_pct": 87.0,
                    }
                ),
                current_level="f2",
            )
        )
        await pilot.pause()

        title = app.query_one("#orionv-status-title", Static).render().plain
        power_chip = app.query_one("#orionv-status-power-action", Button).label.plain
        compute_chip = app.query_one("#orionv-status-compute-action", Button).label.plain

        assert "ALRT C0 W0 A0" in title
        assert "SAFE OK" in title
        assert "риск" not in title  # ADR-0016: риск cut from primary row to tooltip
        assert "PWR | OK" in power_chip
        assert "CPU | WARN" in compute_chip
        assert "Уровень заряда" not in power_chip

        # Affordance: chips read as actionable controls (leading marker + hover tooltip).
        power_button = app.query_one("#orionv-status-power-action", Button)
        assert power_button.label.plain.startswith("▸")
        assert power_button.tooltip


@pytest.mark.asyncio
async def test_status_bars_qiki_chip_reflects_pending_action() -> None:
    pytest.importorskip("textual")

    app = _StatusBarsApp()
    async with app.run_test(size=(160, 30)) as pilot:
        await pilot.pause()

        bars = app.query_one("#orionv-bars", OrionVStatusBars)
        bars.set_state(
            build_operator_shell_state(
                hardware_model=_model({}),
                safe_mode={"active": True},
                qiki_pending_action_title="Confirm release dock",
                qiki_pending_action={"title_ru": "Confirm release dock"},
            )
        )
        await pilot.pause()

        title = app.query_one("#orionv-status-title", Static).render().plain
        qiki_chip = app.query_one("#orionv-status-qiki-action", Button)

        assert "SAFE SMODE" in title
        assert "pending confirm" in qiki_chip.label.plain
        assert qiki_chip.variant == "warning"


@pytest.mark.asyncio
async def test_status_bars_skip_redundant_refresh_for_identical_state(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")

    app = _StatusBarsApp()
    async with app.run_test(size=(160, 30)) as pilot:
        await pilot.pause()
        bars = app.query_one("#orionv-bars", OrionVStatusBars)

        state = build_operator_shell_state(
            hardware_model=_model(
                {
                    "power.soc_pct": 48.0,
                    "thermal.core_c": 81.0,
                    "propulsion.fuel_pct": 55.0,
                    "hull.integrity": 92.0,
                    "compute.cpu_pct": 87.0,
                }
            )
        )
        bars.set_state(state)
        await pilot.pause()

        assert bars._last_rendered_states is not None

        def fail_query_one(*args: object, **kwargs: object) -> None:
            raise AssertionError("identical status-bar state should not touch child widgets again")

        monkeypatch.setattr(bars, "query_one", fail_query_one)
        bars.set_state(state)
