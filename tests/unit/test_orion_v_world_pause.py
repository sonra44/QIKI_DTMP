"""Игровая (активная) пауза: кнопка ⏸/▶ Мир + команды «пауза»/«старт».

Активная пауза: мир (реплика) стоит, консоль живёт. Кнопка — постоянный
операторский орган (видна всегда); label от живого состояния мира; ACK ≠ effect
(ADR-0015): эффект подтверждает чип РЕПЛИКА по телеметрии, консоль не заявляет.
"""

from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp
from qiki.services.operator_console.orion_v.operator_state import build_operator_shell_state


def _app() -> tuple[OrionVApp, dict]:
    calls = {"published": [], "help": []}
    app = OrionVApp()
    app._snapshot = {"sim_state": {"paused": False, "fsm_state": "RUNNING"}}
    app._set_help_text = lambda text="", *a, **k: calls["help"].append(str(text))  # type: ignore
    app._set_last_command_loop_state = lambda *a, **k: None  # type: ignore
    app._request_refresh_ui = lambda: None  # type: ignore

    async def _publish(command: str, parameters: dict | None = None) -> None:
        calls["published"].append(command)

    async def _ack(command: str, timeout: float, command_id=None) -> bool:
        return True

    app._publish_sim_command = _publish  # type: ignore
    app._wait_for_ack = _ack  # type: ignore
    return app, calls


def test_red_world_paused_state_plumbed_to_rail() -> None:
    state = build_operator_shell_state(hardware_model=None, world_paused=True)
    assert state.operator_loop.world_paused is True
    assert build_operator_shell_state(hardware_model=None).operator_loop.world_paused is False


def test_red_toggle_publishes_pause_when_running() -> None:
    app, calls = _app()
    asyncio.run(app._toggle_world_pause())
    assert calls["published"] == ["sim.pause"]
    # ACK ≠ effect: консоль не заявляет «мир стоит», только «жду телеметрию»
    assert any("РЕПЛИКА" in h for h in calls["help"])


def test_red_toggle_publishes_start_when_paused() -> None:
    app, calls = _app()
    app._snapshot["sim_state"] = {"paused": True, "fsm_state": "PAUSED"}
    asyncio.run(app._toggle_world_pause())
    assert calls["published"] == ["sim.start"]


def test_red_ack_timeout_is_not_silent() -> None:
    app, calls = _app()

    async def _no_ack(command: str, timeout: float, command_id=None) -> bool:
        return False

    app._wait_for_ack = _no_ack  # type: ignore
    asyncio.run(app._toggle_world_pause())
    assert any("нет ack" in h or "ACK" in h for h in calls["help"])


def test_red_replay_mode_blocks_world_toggle() -> None:
    app, calls = _app()
    app._replay_mode = True
    asyncio.run(app._toggle_world_pause())
    assert calls["published"] == []
    assert any("АНАЛИЗ" in h or "ОТКЛЮЧЕНО" in h for h in calls["help"])


def test_red_pause_and_start_commands_routed() -> None:
    """Команды «пауза»/«старт» из командного режима — явные, не toggle."""
    app, calls = _app()
    asyncio.run(app._world_pause_command("пауза"))
    app._snapshot["sim_state"] = {"paused": True, "fsm_state": "PAUSED"}
    asyncio.run(app._world_pause_command("старт"))
    assert calls["published"] == ["sim.pause", "sim.start"]
