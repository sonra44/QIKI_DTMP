from __future__ import annotations

import pytest

from qiki.services.operator_console.orion_v.body_physics_view_model import get_body_physics_console_view_model
from qiki.services.operator_console.orion_v.body_structure_view_model import get_body_structure_console_view_model
from qiki.services.operator_console.orion_v.cockpit_playable_view_model import (
    build_cockpit_event_history_item,
    build_cockpit_playable_loop_vm,
    build_cockpit_playable_state,
    cockpit_playable_effect_panel_id,
    build_cockpit_focus_vm,
    build_cockpit_hint_vms,
    build_cockpit_visible_panel_vms,
    format_cockpit_event_ticker_lines,
    format_cockpit_focus_hint_lines,
    format_cockpit_playable_loop_lines,
    format_cockpit_visible_acceptance_lines,
    next_cockpit_focus_panel_id,
    next_cockpit_playable_action_id,
)
from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    build_power_thermal_console_view_model_from_telemetry,
)


def test_cockpit_playable_view_model_exposes_complete_normal_cycle() -> None:
    body = get_body_structure_console_view_model()
    physics = get_body_physics_console_view_model(body)
    power = build_power_thermal_console_view_model_from_telemetry({})
    state = build_cockpit_playable_state(selected_action_id="power_refresh", phase="preview")

    vm = build_cockpit_playable_loop_vm(
        loop_state=state,
        body_vm=body,
        body_physics_vm=physics,
        power_vm=power,
        active_left_mfd_page="radar",
        active_right_mfd_page="systems",
        nats_connected=False,
        active_incidents=0,
    )
    lines = "\n".join(format_cockpit_playable_loop_lines(vm))

    assert vm.selected_action_id == "power_refresh"
    assert vm.phase == "preview"
    assert "F1 PLAYABLE LOOP" in lines
    assert "snapshot → display → preview → request → applied → event → evidence" in lines
    assert "runtime_claim_status: local_ui_loop_no_runtime_command" in lines
    # dedup contract: right MFD page "systems" already shows body/power state,
    # so the loop panel must NOT repeat those detail lines
    assert "POWER: SoC_bat=" not in lines
    assert "BODY: " not in lines
    assert "F1 PANELS | visible_acceptance=ready | panels=6/6" in lines
    assert "BODY=yes | POWER=yes | NAV=yes | SENSORS=yes | COMMAND=yes | EVENT=yes" in lines
    assert "EVENT: status=ready" in lines
    assert "F1 FOCUS | panel=POWER | action=POWER REFRESH" in lines
    assert "F1 HINT |" in lines
    assert "B body | R reset" in lines  # key map merged into the single HINT line
    assert "F1 HELP | POWER REFRESH" in lines
    assert "F1 PALETTE | Ctrl+P" in lines
    assert "F1 PREVIEW | target=POWER" in lines
    assert "runtime_command=no" in lines

    # ...and when the right MFD shows another page, the panel carries the state itself
    vm_other = build_cockpit_playable_loop_vm(
        loop_state=state,
        body_vm=body,
        body_physics_vm=physics,
        power_vm=power,
        active_left_mfd_page="radar",
        active_right_mfd_page="thermal",
        nats_connected=False,
        active_incidents=0,
    )
    other_lines = "\n".join(format_cockpit_playable_loop_lines(vm_other))
    assert "POWER: SoC_bat=" in other_lines
    assert "BODY: " in other_lines


def test_cockpit_visible_acceptance_panels_are_stable_and_complete() -> None:
    body = get_body_structure_console_view_model()
    physics = get_body_physics_console_view_model(body)
    power = build_power_thermal_console_view_model_from_telemetry({})
    state = build_cockpit_playable_state(
        selected_action_id="command_preview",
        phase="evidence_visible",
        last_event_id="f1-loop:test",
        last_event_summary="local event recorded",
    )

    vm = build_cockpit_playable_loop_vm(
        loop_state=state,
        body_vm=body,
        body_physics_vm=physics,
        power_vm=power,
        active_left_mfd_page="nav",
        active_right_mfd_page="sensors",
        nats_connected=False,
        active_incidents=0,
    )
    panels = build_cockpit_visible_panel_vms(vm)
    panel_ids = tuple(panel.panel_id for panel in panels)
    lines = "\n".join(format_cockpit_visible_acceptance_lines(vm))

    assert panel_ids == ("body", "power", "nav", "sensors", "command", "event")
    # panel completeness stays machine-checkable via the panel VMs; the per-panel
    # text rows were removed from the visible block as duplicates of the flags
    statuses = {panel.panel_id: panel.status for panel in panels}
    assert statuses["body"] == statuses["power"] == statuses["nav"] == "shown"
    assert statuses["sensors"] == statuses["command"] == "shown"
    assert statuses["event"] == "recorded"
    assert "F1 PANELS | visible_acceptance=ready | panels=6/6" in lines
    assert "BODY=yes | POWER=yes | NAV=yes | SENSORS=yes | COMMAND=yes | EVENT=yes" in lines
    assert "EVENT: status=recorded" in lines
    # the event id lives in the F1 RESULT line of the full panel (single owner)
    full = "\n".join(format_cockpit_playable_loop_lines(vm))
    assert "f1-loop:test" in full


def test_cockpit_playable_action_cycle_is_stable() -> None:
    assert next_cockpit_playable_action_id("body_self_check", delta=1) == "power_refresh"
    assert next_cockpit_playable_action_id("power_refresh", delta=-1) == "body_self_check"
    assert next_cockpit_playable_action_id("missing", delta=1) == "power_refresh"


def test_cockpit_action_effect_is_routed_to_target_panel() -> None:
    body = get_body_structure_console_view_model()
    physics = get_body_physics_console_view_model(body)
    power = build_power_thermal_console_view_model_from_telemetry({})
    state = build_cockpit_playable_state(
        selected_action_id="power_refresh",
        phase="evidence_visible",
        last_event_id="f1-loop:power",
        last_event_summary="F1 PLAYABLE applied: POWER REFRESH",
        last_action_id="power_refresh",
        last_effect_panel_id="power",
        last_effect_summary="power/accumulator view-model refreshed from current snapshot",
    )

    vm = build_cockpit_playable_loop_vm(
        loop_state=state,
        body_vm=body,
        body_physics_vm=physics,
        power_vm=power,
        active_left_mfd_page="radar",
        active_right_mfd_page="systems",
        nats_connected=False,
        active_incidents=0,
    )
    # effect routing is owned by F1 RESULT (the "F1 ACTION EFFECT" row duplicated it)
    full = "\n".join(format_cockpit_playable_loop_lines(vm))
    assert "F1 RESULT | applied=POWER REFRESH | target=POWER" in full
    assert "event=f1-loop:power" in full

    panels = {panel.panel_id: panel for panel in build_cockpit_visible_panel_vms(vm)}
    assert panels["power"].status == "shown"
    assert panels["body"].status == "shown"
    assert "SoC_bat=" in panels["power"].summary
    assert "last_effect=power/accumulator view-model refreshed from current snapshot" in panels["power"].summary
    # the non-target panel must not claim the effect
    assert "last_effect=none" in panels["body"].summary


def test_cockpit_action_effect_target_map_is_visible_for_all_actions() -> None:
    body = get_body_structure_console_view_model()
    physics = get_body_physics_console_view_model(body)
    power = build_power_thermal_console_view_model_from_telemetry({})
    state = build_cockpit_playable_state(selected_action_id="body_self_check")

    vm = build_cockpit_playable_loop_vm(
        loop_state=state,
        body_vm=body,
        body_physics_vm=physics,
        power_vm=power,
        active_left_mfd_page="radar",
        active_right_mfd_page="systems",
        nats_connected=False,
        active_incidents=0,
    )
    # карта маршрутизации проверяется машинно (boilerplate-строка с экрана убрана)
    expected = {
        "body_self_check": "body",
        "power_refresh": "power",
        "nav_cycle": "nav",
        "sensor_focus": "sensors",
        "command_preview": "command",
    }
    for action_id, panel_id in expected.items():
        assert cockpit_playable_effect_panel_id(action_id) == panel_id


def test_cockpit_event_ticker_records_repeated_apply_cycles() -> None:
    body = get_body_structure_console_view_model()
    physics = get_body_physics_console_view_model(body)
    power = build_power_thermal_console_view_model_from_telemetry({})
    history = [
        build_cockpit_event_history_item(
            event_id="f1-loop:first",
            action_label="BODY SELF-CHECK",
            target_panel_id="body",
            effect_summary="body self-check registered",
        ),
        build_cockpit_event_history_item(
            event_id="f1-loop:second",
            action_label="POWER REFRESH",
            target_panel_id="power",
            effect_summary="power refreshed",
        ),
    ]
    state = build_cockpit_playable_state(
        selected_action_id="power_refresh",
        phase="evidence_visible",
        last_event_id="f1-loop:second",
        last_event_summary="F1 PLAYABLE applied: POWER REFRESH",
        last_action_id="power_refresh",
        last_effect_panel_id="power",
        last_effect_summary="power refreshed",
        action_history=history,
    )

    vm = build_cockpit_playable_loop_vm(
        loop_state=state,
        body_vm=body,
        body_physics_vm=physics,
        power_vm=power,
        active_left_mfd_page="radar",
        active_right_mfd_page="systems",
        nats_connected=False,
        active_incidents=0,
    )
    ticker = "\n".join(format_cockpit_event_ticker_lines(vm))
    lines = "\n".join(format_cockpit_playable_loop_lines(vm))

    assert "F1 EVENT TICKER | entries=2" in ticker  # заголовок только счётчик; latest = первая строка event[1]
    assert "event[1]: f1-loop:second | POWER REFRESH -> POWER | power refreshed" in ticker
    assert "event[2]: f1-loop:first | BODY SELF-CHECK -> BODY | body self-check registered" in ticker
    assert "F1 EVENT TICKER | entries=2" in lines
    assert "EVENT: status=recorded" in lines
    assert "history=2" in lines


def test_cockpit_focus_hint_view_model_exposes_operator_affordances() -> None:
    body = get_body_structure_console_view_model()
    physics = get_body_physics_console_view_model(body)
    power = build_power_thermal_console_view_model_from_telemetry({})
    state = build_cockpit_playable_state(
        selected_action_id="sensor_focus",
        phase="preview",
        focused_panel_id="sensors",
        focus_reason="panel_key",
    )

    vm = build_cockpit_playable_loop_vm(
        loop_state=state,
        body_vm=body,
        body_physics_vm=physics,
        power_vm=power,
        active_left_mfd_page="radar",
        active_right_mfd_page="systems",
        nats_connected=False,
        active_incidents=0,
    )
    focus = build_cockpit_focus_vm(vm)
    hints = build_cockpit_hint_vms(vm)
    lines = "\n".join(format_cockpit_focus_hint_lines(vm))

    assert focus.focused_panel_id == "sensors"
    assert focus.focused_panel_title == "SENSORS"
    assert focus.focused_action_label == "SENSOR FOCUS"
    assert focus.can_preview is True
    assert focus.can_apply is True
    assert focus.can_open_evidence is False
    assert "Ctrl+P command palette enabled" in focus.palette_hint
    # f1_keys hint removed: the key map is already the always-visible "F1 HINT |" line
    assert {hint.hint_id for hint in hints} >= {"f1_panel", "f1_evidence_pending"}
    assert "f1_keys" not in {hint.hint_id for hint in hints}
    assert "F1 FOCUS | panel=SENSORS | action=SENSOR FOCUS" in lines
    assert "F1 HINT | ←/→ action | ↑/↓ panel" in lines
    assert "F1 PALETTE | Ctrl+P" in lines
    assert "F1 CONTEXT | SENSORS" in lines
    assert "no runtime command published" in lines


def test_cockpit_focus_panel_cycle_is_stable_and_help_can_hide_context() -> None:
    assert next_cockpit_focus_panel_id("body", delta=1) == "power"
    assert next_cockpit_focus_panel_id("body", delta=-1) == "event"

    body = get_body_structure_console_view_model()
    physics = get_body_physics_console_view_model(body)
    power = build_power_thermal_console_view_model_from_telemetry({})
    state = build_cockpit_playable_state(
        selected_action_id="command_preview",
        focused_panel_id="event",
        help_visible=False,
    )
    vm = build_cockpit_playable_loop_vm(
        loop_state=state,
        body_vm=body,
        body_physics_vm=physics,
        power_vm=power,
        active_left_mfd_page="radar",
        active_right_mfd_page="systems",
        nats_connected=False,
        active_incidents=0,
    )
    lines = "\n".join(format_cockpit_focus_hint_lines(vm))

    assert "F1 FOCUS | panel=EVENT" in lines
    assert "F1 CONTEXT | hidden | press H to show help" in lines
    assert "F1 PALETTE | Ctrl+P" in lines


def test_f1_command_palette_is_enabled_and_exposes_discoverable_actions() -> None:
    from pathlib import Path

    app_source = Path("src/qiki/services/operator_console/orion_v/app.py").read_text()

    assert "ENABLE_COMMAND_PALETTE = True" in app_source
    assert "def get_system_commands" in app_source
    assert "F1 Body self-check" in app_source
    assert "F1 Power refresh" in app_source
    assert "F1 Navigation page cycle" in app_source
    assert "F1 Sensor focus" in app_source
    assert "F1 Command preview" in app_source
    assert "no runtime command is published" in app_source


@pytest.mark.asyncio
async def test_f1_cockpit_renders_first_playable_loop_panel() -> None:
    pytest.importorskip("textual")
    from textual.app import App, ComposeResult
    from textual.widgets import Static
    from qiki.services.operator_console.orion_v.screens.cockpit import OrionVCockpitScreen

    class _CockpitApp(App[None]):
        def compose(self) -> ComposeResult:
            yield OrionVCockpitScreen(id="cockpit")

    app = _CockpitApp()
    async with app.run_test(size=(180, 50)) as pilot:
        await pilot.pause()
        cockpit = app.query_one("#cockpit", OrionVCockpitScreen)
        cockpit.set_state(
            telemetry={},
            nats_connected=True,
            active_incidents=0,
            incidents=[],
            playable_loop_state=build_cockpit_playable_state(),
        )
        await pilot.pause()

        text = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "F1 PLAYABLE LOOP" in text
        assert "phase=selected" in text
        assert "BODY SELF-CHECK" in text
        assert "snapshot → display → preview → request → applied → event → evidence" in text
        assert "F1 PANELS | visible_acceptance=ready | panels=6/6" in text
        assert "BODY=yes | POWER=yes | NAV=yes | SENSORS=yes | COMMAND=yes | EVENT=yes" in text


@pytest.mark.asyncio
async def test_f1_playable_loop_buttons_preview_and_apply_visible_state(monkeypatch) -> None:
    pytest.importorskip("textual")
    from textual.widgets import Static
    from qiki.services.operator_console.orion_v.app import OrionVApp

    async def _no_nats(self) -> None:  # unit env has no NATS broker; neutralize mount-time connect/hydrate
        return None

    monkeypatch.setattr(OrionVApp, "_connect_and_subscribe", _no_nats)
    monkeypatch.setattr(OrionVApp, "_hydrate_last_observation_objective_from_jetstream", _no_nats)

    app = OrionVApp()
    async with app.run_test(size=(190, 60)) as pilot:
        await pilot.pause()
        app.action_show_level("f1")
        await pilot.pause()

        before = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "F1 PLAYABLE LOOP" in before
        assert "phase=selected" in before
        assert "F1 FOCUS |" in before
        assert "F1 HINT |" in before
        assert "F1 PALETTE | Ctrl+P" in before

        await pilot.click("#orionv-cockpit-focus-next")
        await pilot.pause()
        focused = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "F1 FOCUS | panel=POWER" in focused

        await pilot.click("#orionv-cockpit-help-toggle")
        await pilot.pause()
        hidden_help = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "F1 CONTEXT | hidden | press H to show help" in hidden_help

        await pilot.click("#orionv-cockpit-help-toggle")
        await pilot.pause()

        await pilot.click("#orionv-cockpit-loop-next")
        await pilot.pause()
        selected = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "POWER REFRESH" in selected

        await pilot.click("#orionv-cockpit-loop-preview")
        await pilot.pause()
        preview = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "phase=preview" in preview
        assert "F1 PREVIEW | target=POWER" in preview  # last_event-строка убрана; PREVIEW видна с фазы preview

        await pilot.click("#orionv-cockpit-loop-apply")
        await pilot.pause()
        applied = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "phase=evidence_visible" in applied
        assert "f1-loop:" in applied
        assert "EVENT: status=recorded" in applied
        assert "F1 EVENT TICKER | entries=1" in applied
        assert "event[1]:" in applied
        assert "POWER REFRESH -> POWER" in applied
        assert "history=1" in applied
        assert "local_ui_loop_no_runtime_command" in applied

        history = "\n".join(app._console_history)  # noqa: SLF001 - UI regression test
        assert "F1 PLAYABLE applied: POWER REFRESH" in history
