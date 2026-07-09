"""Этап 8 (§F4): реестр команд — единый владелец help/палитры + пин полноты.

Двунаправленная сверка:
- реестр→роутер (поведенчески): каждая команда реестра, поданная в
  `_route_typed_command`, НЕ уходит в ветку «Неизвестная команда»;
- роутер→реестр (AST): каждый строковый литерал команд из if-цепочки
  роутера обязан присутствовать в реестре — новая команда без записи в
  реестре невидима для оператора (нарушение критерия §F4).

Замечание хрупкости: AST-скан привязан к текущей форме роутера
(литералы в `in {...}` / `== "…"` / `startswith("…")`); при переводе
роутера на данные реестра пин упростится до тождества.
"""

from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.command_registry import (
    COMMAND_REGISTRY,
    HELP_GROUPS_ORDER,
    iter_help_lines,
    iter_palette_specs,
)

_MOCKED_SINKS = (
    "action_show_level",
    "action_incident_next",
    "action_incident_prev",
    "action_events_page_next",
    "action_events_page_prev",
    "action_ack_selected_incident",
    "action_clear_acknowledged_incidents",
    "action_ack_observation_review",
    "action_select_observation_recheck_hold",
    "action_resume_observation_follow_up",
    "action_close_command_mode",
    "_confirm_qiki_pending_action",
    "_cancel_qiki_pending_action",
    "_abort_attach_procedure",
    "_hold_attach_procedure",
    "_resume_attach_procedure",
    "_world_pause_command",
    "_publish_qiki_intent",
    "_publish_sim_command_tracked",
    "_publish_audit_event",
    "_start_procedure",
    "_start_replay",
    "_set_severity_filter",
    "_set_subsystem_filter",
    "_set_time_filter",
    "_set_audit_filter",
    "_request_quit_confirm",
    "_request_refresh_ui",
    "_spawn_task",
)


def _probe_app() -> tuple[OrionVApp, list[str]]:
    app = OrionVApp()
    helps: list[str] = []
    app._set_help_text = lambda text: helps.append(str(text))  # type: ignore[method-assign]
    for name in _MOCKED_SINKS:
        setattr(app, name, Mock())
    return app, helps


def _submit(app: OrionVApp, text: str) -> None:
    app.on_input_submitted(SimpleNamespace(value=text, input=SimpleNamespace(value="")))


def test_every_registry_command_is_known_to_router() -> None:
    for spec in COMMAND_REGISTRY:
        if not spec.probe:
            continue
        for form in (spec.name, *spec.aliases):
            app, helps = _probe_app()
            _submit(app, form + spec.extra_probe_args)
            unknown = [line for line in helps if line.startswith("Неизвестная команда")]
            assert not unknown, f"реестр знает «{form}», роутер — нет: {unknown}"


def test_every_router_command_is_in_registry() -> None:
    literals: set[str] = set()
    for func in (
        OrionVApp._route_typed_command,
        OrionVApp._try_sim_world_command,
    ):
        tree = ast.parse(inspect.getsource(func).lstrip())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.add(node.value)

    known: set[str] = set()
    for spec in COMMAND_REGISTRY:
        for form in (spec.name, *spec.aliases):
            known.add(form)
            known.add(form + " ")  # startswith-литералы вида "select "

    command_like = {
        lit
        for lit in literals
        # интересуют только literals-команды: нижний регистр, латиница/
        # кириллица + точки/дефисы/пробелы; фразы подсказок отсеиваются
        if lit
        and len(lit) <= 24
        and lit == lit.lower()  # команды роутера — нижний регистр
        and not lit.startswith((" ", ".", "«"))
        and " — " not in lit
        and ":" not in lit.strip(":")
        and lit.replace(".", "").replace("-", "").replace("_", "").replace(" ", "").isalnum()
        and any(ch.isalpha() for ch in lit)
    }
    # служебные литералы роутера, не являющиеся командами
    command_like -= {
        "f5",  # уровень (есть в реестре) — оставлен для ясности набора ниже
        "speed",
        "orion_v",
        "replay",
        "replay_mode",
        "kind",
        "action_type",
        "enabled",
        "operator",
        "none",
        "900",
    }
    missing = {
        lit
        for lit in command_like
        if lit not in known and not any(lit.startswith(k) or k.startswith(lit) for k in known)
    }
    assert not missing, f"команды роутера отсутствуют в реестре: {sorted(missing)}"


def test_help_prints_all_groups_to_console_history() -> None:
    app, helps = _probe_app()
    app._console_history.clear()
    _submit(app, "help")
    history_text = "\n".join(str(line) for line in app._console_history)
    for group in HELP_GROUPS_ORDER:
        assert f"{group}:" in history_text, f"группа {group} не выведена в консоль F4"
    # сводка в help-строке говорит, куда смотреть
    assert helps and "F4" in helps[-1]


def test_help_lines_fit_console_width() -> None:
    for line in iter_help_lines():
        assert len(line) <= 160, f"строка help длиннее 160: {line[:80]}…"


def test_palette_specs_cover_world_and_qiki() -> None:
    names = {spec.name for spec in iter_palette_specs()}
    assert {"sim.start", "sim.pause", "sim.stop", "q confirm", "help", "f1"} <= names
