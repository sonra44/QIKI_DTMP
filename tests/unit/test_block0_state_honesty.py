"""Блок 0, этап 3 «честность состояния»: FSM enum, актуатор, to_thread, fixture-поля.

По `02_BLOCK0_DEFECT_BASELINE.md` (0.6/0.7/0.8/0.11) и `08_VERIFICATION_PLAN.md`
(этап 3).
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import grpc
import pytest

from qiki.services.q_core_agent.core.fsm_handler import FSMHandler
from qiki.services.q_core_agent.core.grpc_data_provider import GrpcDataProvider
from qiki.services.q_core_agent.core.guard_table import GuardEvaluationResult
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import (
    ActuatorCommand,
    CommandTypeEnum,
    FsmStateEnum,
    FsmStateSnapshot,
)
from qiki.shared.models.radar import FriendFoeEnum, TransponderModeEnum


def _handler(*, bios_ok: bool = True, guards: list | None = None) -> FSMHandler:
    context = SimpleNamespace(
        guard_events=list(guards or []),
        is_bios_ok=lambda: bios_ok,
        has_valid_proposals=lambda: False,
    )
    return FSMHandler(context=context)


def _critical_guard() -> GuardEvaluationResult:
    return GuardEvaluationResult(
        rule_id="UNKNOWN_CLOSE",
        severity="critical",
        fsm_event="RADAR_ALERT_UNKNOWN_CLOSE",
        message="unknown contact close",
        track_id=str(uuid4()),
        range_m=42.0,
        quality=0.9,
        iff=FriendFoeEnum.UNKNOWN,
        transponder_on=False,
        transponder_mode=TransponderModeEnum.OFF,
    )


# ── 0.6: FSM enum-коллизия agent(4=ERROR_STATE) vs shared(4=PAUSED) ──────────

def test_paused_state_is_not_healed_as_error() -> None:
    """PAUSED(4) — операторская пауза; правило «ERROR_STATE + bios ok → IDLE»
    не имеет права её «вылечить» (коллизия значений 4)."""
    handler = _handler(bios_ok=True)
    snapshot = FsmStateSnapshot(
        current_state=FsmStateEnum.PAUSED,
        previous_state=FsmStateEnum.RUNNING,
    )
    result = handler.process_fsm_state(snapshot)
    assert result.current_state is FsmStateEnum.PAUSED


def test_critical_guard_lands_in_shared_error_not_paused() -> None:
    """critical guard → авария; в shared-снапшоте это ERROR(5), а не PAUSED(4)."""
    handler = _handler(guards=[_critical_guard()])
    snapshot = FsmStateSnapshot(
        current_state=FsmStateEnum.RUNNING,
        previous_state=FsmStateEnum.IDLE,
    )
    result = handler.process_fsm_state(snapshot)
    assert result.current_state is FsmStateEnum.ERROR


def test_error_state_recovers_to_idle_when_bios_ok() -> None:
    """Настоящая авария (shared ERROR=5) с чистым BIOS честно уходит в IDLE."""
    handler = _handler(bios_ok=True)
    snapshot = FsmStateSnapshot(
        current_state=FsmStateEnum.ERROR,
        previous_state=FsmStateEnum.RUNNING,
    )
    result = handler.process_fsm_state(snapshot)
    assert result.current_state is FsmStateEnum.IDLE


# ── 0.7: провал актуаторной команды не может выглядеть как «accepted» ────────

class _FakeRpcError(grpc.RpcError):
    def code(self) -> grpc.StatusCode:
        return grpc.StatusCode.UNAVAILABLE

    def details(self) -> str:
        return "sim unreachable"


def _actuator_command() -> ActuatorCommand:
    return ActuatorCommand(
        actuator_id=uuid4(),
        command_type=CommandTypeEnum.SET_VELOCITY,
        int_value=10,
    )


def test_actuator_rpc_error_raises_connection_error() -> None:
    provider = GrpcDataProvider.__new__(GrpcDataProvider)
    provider.channel = None  # __del__ не должен ругаться на тестовый объект
    provider.stub = Mock()
    provider.stub.SendActuatorCommand.side_effect = _FakeRpcError()
    with pytest.raises(ConnectionError):
        provider.send_actuator_command(_actuator_command())


def test_actuator_rejected_raises_value_error() -> None:
    provider = GrpcDataProvider.__new__(GrpcDataProvider)
    provider.channel = None  # __del__ не должен ругаться на тестовый объект
    provider.stub = Mock()
    provider.stub.SendActuatorCommand.return_value = SimpleNamespace(
        accepted=False, message="actuator refused"
    )
    with pytest.raises(ValueError):
        provider.send_actuator_command(_actuator_command())


def test_actuator_accepted_returns_true() -> None:
    provider = GrpcDataProvider.__new__(GrpcDataProvider)
    provider.channel = None  # __del__ не должен ругаться на тестовый объект
    provider.stub = Mock()
    provider.stub.SendActuatorCommand.return_value = SimpleNamespace(accepted=True, message="ok")
    assert provider.send_actuator_command(_actuator_command()) is True


# ── 0.8: refresh уходит в поток и не блокирует event loop ────────────────────

def test_refresh_async_does_not_block_event_loop() -> None:
    from qiki.services.q_core_agent.qiki_orion_intents_service import (
        _refresh_agent_snapshot_async,
    )

    agent = SimpleNamespace()
    blocking = SimpleNamespace()

    def _slow_refresh(*, agent, data_provider) -> None:  # noqa: ARG001
        time.sleep(0.4)  # блокирующий sync-вызов (gRPC timeout=10s в проде)

    async def _main() -> int:
        ticks = 0

        async def _ticker() -> None:
            nonlocal ticks
            while True:
                ticks += 1
                await asyncio.sleep(0.05)

        task = asyncio.get_running_loop().create_task(_ticker())
        import qiki.services.q_core_agent.qiki_orion_intents_service as svc

        original = svc._refresh_agent_snapshot
        svc._refresh_agent_snapshot = _slow_refresh
        try:
            await _refresh_agent_snapshot_async(agent=agent, data_provider=blocking)
        finally:
            svc._refresh_agent_snapshot = original
            task.cancel()
        return ticks

    ticks = asyncio.run(_main())
    # При блокировке loop тикер не натикал бы вовсе; в потоке — минимум ~5.
    assert ticks >= 3


# ── 0.11: fixture-константы неотличимы от измерений ──────────────────────────

def test_sim_truth_marks_fixture_fields(monkeypatch) -> None:
    monkeypatch.setenv("RADAR_ENABLED", "0")
    sim = QSimService(QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO"))
    state = sim.world_model.get_state()
    sources = state.get("field_sources")
    assert isinstance(sources, dict)
    assert sources.get("hull_integrity") == "fixture"
    assert sources.get("radiation_usvh") == "fixture"
    assert sources.get("temp_external_c") == "fixture"
