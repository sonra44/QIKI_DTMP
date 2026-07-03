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
    assert "Ф1 ЖИВОЙ ЦИКЛ" in lines
    assert "снимок → экран → предпросмотр → запрос → применение → событие → улика" in lines
    assert "команды кораблю НЕ отправляются" in lines
    # dedup contract: right MFD page "systems" already shows body/power state,
    # so the loop panel must NOT repeat those detail lines
    assert "ПИТАНИЕ: SoC_bat=" not in lines
    assert "КОРПУС: " not in lines
    assert "ПАНЕЛИ | готово 6/6" in lines
    assert "КОРПУС ✓ | ПИТАНИЕ ✓ | НАВ ✓ | СЕНСОРЫ ✓ | КОМАНДА ✓ | СОБЫТИЯ ✓" in lines
    assert "СОБЫТИЯ: готово" in lines
    assert "ФОКУС | панель: ПИТАНИЕ | действие: ОБНОВИТЬ ПИТАНИЕ" in lines
    assert "КЛАВИШИ |" in lines
    assert "B корпус | R сброс" in lines  # key map merged into the single HINT line
    assert "СПРАВКА | ОБНОВИТЬ ПИТАНИЕ" in lines
    assert "ПАЛИТРА | Ctrl+P" in lines
    assert "ПРЕДПРОСМОТР | цель: ПИТАНИЕ" in lines
    assert "команда кораблю: НЕТ" in lines

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
    assert "ПИТАНИЕ: SoC_bat=" in other_lines
    assert "КОРПУС: " in other_lines


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
    assert "ПАНЕЛИ | готово 6/6" in lines
    assert "КОРПУС ✓ | ПИТАНИЕ ✓ | НАВ ✓ | СЕНСОРЫ ✓ | КОМАНДА ✓ | СОБЫТИЯ ✓" in lines
    assert "СОБЫТИЯ: записано" in lines
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
        last_event_summary="Ф1 применено: ОБНОВИТЬ ПИТАНИЕ",
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
    assert "РЕЗУЛЬТАТ | применено: ОБНОВИТЬ ПИТАНИЕ | цель: ПИТАНИЕ" in full
    assert "событие: f1-loop:power" in full

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
            action_label="ПРОВЕРКА КОРПУСА",
            target_panel_id="body",
            effect_summary="body self-check registered",
        ),
        build_cockpit_event_history_item(
            event_id="f1-loop:second",
            action_label="ОБНОВИТЬ ПИТАНИЕ",
            target_panel_id="power",
            effect_summary="power refreshed",
        ),
    ]
    state = build_cockpit_playable_state(
        selected_action_id="power_refresh",
        phase="evidence_visible",
        last_event_id="f1-loop:second",
        last_event_summary="Ф1 применено: ОБНОВИТЬ ПИТАНИЕ",
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

    assert "ЛЕНТА СОБЫТИЙ | записей: 2" in ticker  # заголовок только счётчик; latest = первая строка event[1]
    assert "событие[1]: f1-loop:second | ОБНОВИТЬ ПИТАНИЕ → ПИТАНИЕ | power refreshed" in ticker
    assert "событие[2]: f1-loop:first | ПРОВЕРКА КОРПУСА → КОРПУС | body self-check registered" in ticker
    assert "ЛЕНТА СОБЫТИЙ | записей: 2" in lines
    assert "СОБЫТИЯ: записано" in lines
    assert "история: 2" in lines


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
    assert focus.focused_panel_title == "СЕНСОРЫ"
    assert focus.focused_action_label == "ФОКУС СЕНСОРОВ"
    assert focus.can_preview is True
    assert focus.can_apply is True
    assert focus.can_open_evidence is False
    assert "Ctrl+P — палитра команд" in focus.palette_hint
    # f1_keys hint removed: the key map is already the always-visible "КЛАВИШИ |" line
    assert {hint.hint_id for hint in hints} >= {"f1_panel", "f1_evidence_pending"}
    assert "f1_keys" not in {hint.hint_id for hint in hints}
    assert "ФОКУС | панель: СЕНСОРЫ | действие: ФОКУС СЕНСОРОВ" in lines
    assert "КЛАВИШИ | ←/→ действие | ↑/↓ панель" in lines
    assert "ПАЛИТРА | Ctrl+P" in lines
    assert "ПОДСКАЗКА [СЕНСОРЫ]" in lines
    assert "команда кораблю не отправляется" in lines


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

    assert "ФОКУС | панель: СОБЫТИЯ" in lines
    assert "ПОДСКАЗКИ СКРЫТЫ | H — показать справку" in lines
    assert "ПАЛИТРА | Ctrl+P" in lines


def test_f1_command_palette_is_enabled_and_exposes_discoverable_actions() -> None:
    from pathlib import Path

    app_source = Path("src/qiki/services/operator_console/orion_v/app.py").read_text()

    assert "ENABLE_COMMAND_PALETTE = True" in app_source
    assert "def get_system_commands" in app_source
    assert "Ф1 Проверка корпуса" in app_source
    assert "Ф1 Обновить питание" in app_source
    assert "Ф1 Смена страницы НАВ" in app_source
    assert "Ф1 Фокус сенсоров" in app_source
    assert "Ф1 Репетиция команды" in app_source
    assert "команда кораблю не отправляется" in app_source


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
        assert "Ф1 ЖИВОЙ ЦИКЛ" in text
        assert "фаза: выбор" in text
        assert "ПРОВЕРКА КОРПУСА" in text
        assert "снимок → экран → предпросмотр → запрос → применение → событие → улика" in text
        assert "ПАНЕЛИ | готово 6/6" in text
        assert "КОРПУС ✓ | ПИТАНИЕ ✓ | НАВ ✓ | СЕНСОРЫ ✓ | КОМАНДА ✓ | СОБЫТИЯ ✓" in text


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
        assert "Ф1 ЖИВОЙ ЦИКЛ" in before
        assert "фаза: выбор" in before
        assert "ФОКУС |" in before
        assert "КЛАВИШИ |" in before
        assert "ПАЛИТРА | Ctrl+P" in before

        await pilot.click("#orionv-cockpit-focus-next")
        await pilot.pause()
        focused = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "ФОКУС | панель: ПИТАНИЕ" in focused

        await pilot.click("#orionv-cockpit-help-toggle")
        await pilot.pause()
        hidden_help = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "ПОДСКАЗКИ СКРЫТЫ | H — показать справку" in hidden_help

        await pilot.click("#orionv-cockpit-help-toggle")
        await pilot.pause()

        await pilot.click("#orionv-cockpit-loop-next")
        await pilot.pause()
        selected = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "ОБНОВИТЬ ПИТАНИЕ" in selected

        await pilot.click("#orionv-cockpit-loop-preview")
        await pilot.pause()
        preview = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "фаза: предпросмотр" in preview
        assert "ПРЕДПРОСМОТР | цель: ПИТАНИЕ" in preview  # last_event-строка убрана; PREVIEW видна с фазы preview

        await pilot.click("#orionv-cockpit-loop-apply")
        await pilot.pause()
        applied = app.query_one("#orionv-mfd-qiki", Static).render().plain
        assert "фаза: улика на экране" in applied
        assert "f1-loop:" in applied
        assert "СОБЫТИЯ: записано" in applied
        assert "ЛЕНТА СОБЫТИЙ | записей: 1" in applied
        assert "событие[1]:" in applied
        assert "ОБНОВИТЬ ПИТАНИЕ → ПИТАНИЕ" in applied
        assert "история: 1" in applied
        assert "команды кораблю НЕ отправляются" in applied

        history = "\n".join(app._console_history)  # noqa: SLF001 - UI regression test
        assert "Ф1 применено: ОБНОВИТЬ ПИТАНИЕ" in history
