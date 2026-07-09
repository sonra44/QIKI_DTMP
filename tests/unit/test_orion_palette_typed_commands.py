"""Этап 8 (§F4-4): typed-команды в палитре Ctrl+P — single path через роутер.

Записи палитры НЕ публикуют команды напрямую: безаргументные зовут
`_route_typed_command(name)` (тот же путь со всеми гейтами, что и Input);
аргументные — префиллят поле ввода (`proc run `), оператор дописывает.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.command_registry import iter_palette_specs

# Textual SystemCommandsProvider опрашивает screen.query/focused/maximized
_FAKE_SCREEN = SimpleNamespace(
    query=lambda *a, **k: [],
    maximized=None,
    focused=None,
    action_minimize=lambda: None,
)


def _system_commands(app: OrionVApp):
    return list(app.get_system_commands(screen=_FAKE_SCREEN))


def test_palette_exposes_typed_commands() -> None:
    app = OrionVApp()
    titles = " | ".join(str(cmd.title) for cmd in _system_commands(app))
    assert "sim.start" in titles
    assert "sim.pause" in titles
    assert "sim.stop" in titles
    assert "подтвердить действие" in titles  # q confirm
    assert "Справка" in titles  # help


def test_palette_argless_entry_routes_through_router() -> None:
    app = OrionVApp()
    app._route_typed_command = Mock()  # type: ignore[method-assign]
    app._publish_sim_command_tracked = Mock()  # type: ignore[method-assign]

    target = next(
        cmd for cmd in _system_commands(app) if "sim.start" in str(cmd.title)
    )
    target.callback()

    app._route_typed_command.assert_called_once_with("sim.start")
    app._publish_sim_command_tracked.assert_not_called()  # не мимо роутера


def test_palette_entries_use_only_registry_names() -> None:
    """F5-защита: роутер на F5 трактует неизвестное как вопрос QIKI —
    палитра обязана слать только канонические имена реестра."""
    registry_names = {spec.name for spec in iter_palette_specs()}
    app = OrionVApp()
    app._route_typed_command = Mock()  # type: ignore[method-assign]
    for cmd in _system_commands(app):
        app._route_typed_command.reset_mock()
        # Аудит 0052 (E): проверка ВНУТРИ try — callback, вызвавший роутер и
        # затем бросивший, не должен проскочить мимо ассерта через continue
        try:
            cmd.callback()
        except Exception:
            pass  # системные записи Textual (скриншот и т.п.) — не наши
        if app._route_typed_command.called:
            (sent,), _ = app._route_typed_command.call_args
            assert sent in registry_names, f"палитра шлёт вне реестра: {sent!r}"
