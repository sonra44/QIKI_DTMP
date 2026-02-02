"""RCS (Propulsion Plane) MVP tests — no-mocks, STEP-A."""

from __future__ import annotations

from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import Unit
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config.loaders import load_thrusters_config, thruster_allocation_rank
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata


RCS_PORT_ID = "e03efa3e-5735-5a82-8f5c-9a9d9dfff351"


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
    cmd.actuator_id.value = RCS_PORT_ID
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
    cmd.actuator_id.value = RCS_PORT_ID
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


def test_sim_rcs_fire_control_command_emits_thrusters_block() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")
    fire = CommandMessage(
        command_name="sim.rcs.fire",
        parameters={"axis": "forward", "pct": 60.0, "duration_s": 2.0},
        metadata=meta,
    )
    assert qsim.apply_control_command(fire) is True

    qsim.step(delta_time=1.0)

    state = qsim.world_model.get_state()
    rcs = ((state.get("propulsion") or {}).get("rcs") or {})
    assert rcs.get("enabled") is True
    assert rcs.get("active") is True
    assert rcs.get("axis") == "forward"

    thrusters = rcs.get("thrusters")
    assert isinstance(thrusters, list) and thrusters
    t0 = thrusters[0]
    assert isinstance(t0, dict)
    assert isinstance(t0.get("index"), int)
    assert isinstance(t0.get("cluster_id"), str)
    assert isinstance(t0.get("duty_pct"), (int, float))
    assert isinstance(t0.get("valve_open"), bool)

    stop = CommandMessage(command_name="sim.rcs.stop", parameters={}, metadata=meta)
    assert qsim.apply_control_command(stop) is True
