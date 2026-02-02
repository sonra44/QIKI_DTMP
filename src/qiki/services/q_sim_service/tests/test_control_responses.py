from __future__ import annotations

from uuid import UUID

from qiki.services.q_sim_service.grpc_server import (
    _build_control_response_payload,
    _describe_control_command_result,
)
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata


def test_control_response_payload_uses_correlation_id() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    req_id = UUID("00000000-0000-0000-0000-000000000001")
    meta = MessageMetadata(
        message_type="control_command",
        source="test",
        destination="q_sim_service",
        correlation_id=req_id,
    )
    cmd = CommandMessage(command_name="sim.start", parameters={}, metadata=meta)

    status, error = _describe_control_command_result(cmd, success=True, sim_service=qsim)
    assert (status, error) == ("applied", None)

    resp = _build_control_response_payload(cmd, success=True, status=status, error=error)
    assert resp["success"] is True
    assert resp["requestId"] == str(req_id)
    assert resp["payload"]["command_name"] == "sim.start"
    assert resp["payload"]["status"] == "applied"
    assert "error" not in resp


def test_control_response_describes_xpdr_rejection_when_comms_disabled() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)
    qsim._comms_enabled = False  # test-only: simulate hardware profile gating

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")
    cmd = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "ON"}, metadata=meta)

    status, error = _describe_control_command_result(cmd, success=False, sim_service=qsim)
    assert error == "comms_disabled"
    assert "связь" in status.lower()


def test_control_response_describes_xpdr_invalid_mode() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")
    cmd = CommandMessage(command_name="sim.xpdr.mode", parameters={"mode": "MAYBE"}, metadata=meta)

    status, error = _describe_control_command_result(cmd, success=False, sim_service=qsim)
    assert error == "invalid_mode"
    assert status.startswith("invalid mode:")

