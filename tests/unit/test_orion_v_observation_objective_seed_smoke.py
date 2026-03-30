from __future__ import annotations

import asyncio

import pytest

from tools import orion_v_qiki_observation_objective_seed_smoke as smoke


class _StubApp:
    def __init__(self, sim_state: dict[str, object]) -> None:
        self._telemetry = {"sim_state": sim_state}
        self.published: list[tuple[str, dict[str, object]]] = []
        self.waited_for_ack: list[tuple[str, float]] = []

    async def _publish_sim_command(self, command_name: str, parameters: dict[str, object] | None = None) -> None:
        self.published.append((command_name, dict(parameters or {})))
        self._telemetry["sim_state"] = {
            "fsm_state": "RUNNING",
            "paused": False,
            "speed": float((parameters or {}).get("speed") or 1.0),
        }

    async def _wait_for_ack(self, expected_ack: str, timeout_s: float) -> bool:
        self.waited_for_ack.append((expected_ack, timeout_s))
        return True


def test_ensure_sim_running_for_live_radar_is_noop_when_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _StubApp({"fsm_state": "RUNNING", "paused": False, "speed": 1.0})

    async def _unexpected_wait_until(**_: object) -> None:
        raise AssertionError("_wait_until must not run when sim is already RUNNING")

    monkeypatch.setattr(smoke, "_wait_until", _unexpected_wait_until)

    asyncio.run(smoke._ensure_sim_running_for_live_radar(app))

    assert app.published == []
    assert app.waited_for_ack == []


def test_ensure_sim_running_for_live_radar_bootstraps_from_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _StubApp({"fsm_state": "STOPPED", "paused": False, "speed": 1.0})
    wait_labels: list[str] = []

    async def _fake_wait_until(predicate, *, timeout_s: float, step_s: float, label: str) -> None:
        wait_labels.append(label)
        assert timeout_s == 6.0
        assert step_s == 0.1
        assert predicate() is True

    monkeypatch.setattr(smoke, "_wait_until", _fake_wait_until)

    asyncio.run(smoke._ensure_sim_running_for_live_radar(app))

    assert app.published == [("sim.start", {"speed": 1.0})]
    assert app.waited_for_ack == [("sim.start", 3.0)]
    assert wait_labels == ["sim_state running before live radar cache"]


def test_ensure_sim_running_for_live_radar_fails_without_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _StubApp({"fsm_state": "STOPPED", "paused": False, "speed": 1.0})

    async def _false_ack(expected_ack: str, timeout_s: float) -> bool:
        app.waited_for_ack.append((expected_ack, timeout_s))
        return False

    async def _unexpected_wait_until(**_: object) -> None:
        raise AssertionError("_wait_until must not run when sim.start ack is missing")

    monkeypatch.setattr(app, "_wait_for_ack", _false_ack)
    monkeypatch.setattr(smoke, "_wait_until", _unexpected_wait_until)

    with pytest.raises(AssertionError, match="sim.start did not receive ack"):
        asyncio.run(smoke._ensure_sim_running_for_live_radar(app))

    assert app.published == [("sim.start", {"speed": 1.0})]
    assert app.waited_for_ack == [("sim.start", 3.0)]
