"""RCS (Propulsion Plane) MVP tests — no-mocks, STEP-A."""

from __future__ import annotations

from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import Unit
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config.loaders import load_thrusters_config, thruster_allocation_rank
from qiki.shared.config_models import QSimServiceConfig


def test_thrusters_config_rank_is_6() -> None:
    thrusters = load_thrusters_config()
    assert len(thrusters) == 16
    assert thruster_allocation_rank(thrusters) == 6


def test_rcs_command_consumes_propellant_and_emits_telemetry() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    state0 = qsim.world_model.get_state()
    prop0 = (state0.get("propulsion") or {}).get("rcs") or {}
    assert prop0.get("enabled") is True
    propellant0 = float(prop0.get("propellant_kg", 0.0))
    assert propellant0 > 0.0

    cmd = ActuatorCommand()
    cmd.actuator_id.value = "rcs_port"
    cmd.command_type = ActuatorCommand.CommandType.SET_VELOCITY
    cmd.float_value = 60.0
    cmd.unit = Unit.PERCENT
    cmd.timeout_ms = 2000
    qsim.receive_actuator_command(cmd)

    qsim.step()

    state1 = qsim.world_model.get_state()
    prop1 = (state1.get("propulsion") or {}).get("rcs") or {}
    assert prop1.get("active") in (True, False)  # must exist
    propellant1 = float(prop1.get("propellant_kg", 0.0))
    assert propellant1 <= propellant0

    payload = qsim._build_telemetry_payload(state1)
    assert isinstance(payload, dict)
    assert "propulsion" in payload
    assert "rcs" in (payload.get("propulsion") or {})


def test_rcs_timeout_zero_stops_immediately() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    state0 = qsim.world_model.get_state()
    prop0 = (state0.get("propulsion") or {}).get("rcs") or {}
    propellant0 = float(prop0.get("propellant_kg", 0.0))

    cmd = ActuatorCommand()
    cmd.actuator_id.value = "rcs_port"
    cmd.command_type = ActuatorCommand.CommandType.SET_VELOCITY
    cmd.float_value = 60.0
    cmd.unit = Unit.PERCENT
    cmd.timeout_ms = 0
    qsim.receive_actuator_command(cmd)

    qsim.step()

    state1 = qsim.world_model.get_state()
    rcs = (state1.get("propulsion") or {}).get("rcs") or {}
    assert float(rcs.get("command_pct", 0.0)) == 0.0
    assert float(rcs.get("time_left_s", 0.0)) == 0.0
    propellant1 = float(rcs.get("propellant_kg", 0.0))
    assert propellant1 == propellant0
