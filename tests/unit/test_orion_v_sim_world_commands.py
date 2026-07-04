"""Operator world-control commands in the ORION V command mode.

sim.start [speed] / sim.pause / sim.stop (+ legacy aliases simulation.* and
симуляция.*) must publish through _publish_sim_command — the same ACK-awaited
CommandMessage path procedures use. ACK != effect confirmation.
"""

from __future__ import annotations

import asyncio

from qiki.services.operator_console.orion_v.app import OrionVApp


def _harness(monkeypatch=None):
    app = OrionVApp()
    published: list[tuple[str, dict]] = []
    messages: list[str] = []

    async def _record(command_name: str, parameters: dict | None = None) -> None:
        published.append((command_name, dict(parameters or {})))

    app._publish_sim_command = _record  # type: ignore[method-assign]
    app._set_help_text = lambda text: messages.append(text)  # type: ignore[method-assign]
    return app, published, messages


def _run(app: OrionVApp, command: str) -> bool:
    async def _inner() -> bool:
        consumed = app._try_sim_world_command(command)
        await asyncio.sleep(0)  # let the created task run
        return consumed

    return asyncio.run(_inner())


def test_sim_start_with_speed_publishes_command() -> None:
    app, published, messages = _harness()
    assert _run(app, "sim.start 2.0") is True
    assert published == [("sim.start", {"speed": 2.0})]
    assert "ждём ACK" in messages[-1]  # honesty: ACK != effect


def test_sim_start_without_speed_publishes_empty_parameters() -> None:
    app, published, _ = _harness()
    assert _run(app, "sim.start") is True
    assert published == [("sim.start", {})]


def test_sim_pause_and_stop_publish() -> None:
    app, published, _ = _harness()
    assert _run(app, "sim.pause") is True
    assert _run(app, "sim.stop") is True
    assert published == [("sim.pause", {}), ("sim.stop", {})]


def test_russian_alias_maps_to_canonical_name() -> None:
    app, published, _ = _harness()
    assert _run(app, "симуляция.старт 0.5") is True
    assert published == [("sim.start", {"speed": 0.5})]


def test_bad_speed_is_rejected_without_publish() -> None:
    app, published, messages = _harness()
    assert _run(app, "sim.start fast") is True  # consumed, but not published
    assert _run(app, "sim.start 0") is True
    assert published == []
    assert any("числом" in m for m in messages)
    assert any("больше нуля" in m for m in messages)


def test_unknown_sim_command_is_not_consumed() -> None:
    app, published, _ = _harness()
    assert _run(app, "sim.warp") is False
    assert published == []
