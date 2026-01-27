"""Test for QSimService functionality."""

import pytest
from qiki.services.q_sim_service.service import QSimService
from qiki.services.q_sim_service.grpc_server import QSimAPIService
from qiki.shared.config_models import QSimServiceConfig
from qiki.shared.models.core import CommandMessage, MessageMetadata
from generated.q_sim_api_pb2 import HealthCheckRequest, HealthCheckResponse
from generated.sensor_raw_in_pb2 import SensorReading

RCS_PORT_ID = "e03efa3e-5735-5a82-8f5c-9a9d9dfff351"


class _DummyCtx:
    """Mock context for gRPC servicer."""

    def set_code(self, *args, **kwargs):  # pragma: no cover - noop
        pass

    def set_details(self, *args, **kwargs):  # pragma: no cover - noop
        pass


@pytest.mark.asyncio
async def test_servicer_health_check():
    """Test that HealthCheck endpoint returns correct status."""
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)
    servicer = QSimAPIService(qsim)

    response = await servicer.HealthCheck(HealthCheckRequest(), _DummyCtx())
    assert isinstance(response, HealthCheckResponse)
    assert response.status == "SERVING"


def test_qsim_service_initialization():
    """Test that QSimService initializes correctly."""
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    assert qsim.config == cfg
    assert qsim.sensor_data_queue == []
    assert qsim.actuator_command_queue == []
    assert qsim.world_model is not None


def test_qsim_service_step_generates_sensor_data():
    """Test that QSimService.step() generates sensor data."""
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    # Initially queue should be empty
    assert len(qsim.sensor_data_queue) == 0

    # Run one simulation step
    qsim.step()

    # Queue should now have one sensor reading
    assert len(qsim.sensor_data_queue) == 1
    sensor_data = qsim.sensor_data_queue[0]

    # Verify it's a valid SensorReading
    assert isinstance(sensor_data, SensorReading)
    assert sensor_data.sensor_id is not None
    assert sensor_data.is_valid is True


def test_actuator_command_queue_is_cleared_each_tick() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    from generated.actuator_raw_out_pb2 import ActuatorCommand
    from generated.common_types_pb2 import Unit

    cmd = ActuatorCommand()
    cmd.actuator_id.value = RCS_PORT_ID
    cmd.command_type = ActuatorCommand.CommandType.SET_VELOCITY
    cmd.float_value = 10.0
    cmd.unit = Unit.PERCENT
    cmd.timeout_ms = 1000

    qsim.receive_actuator_command(cmd)
    assert len(qsim.actuator_command_queue) == 1

    qsim.step()
    assert qsim.actuator_command_queue == []


def test_generate_sensor_data():
    """Test sensor data generation directly."""
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    # Generate sensor data
    sensor_data = qsim.generate_sensor_data()

    # Verify it's a valid SensorReading
    assert isinstance(sensor_data, SensorReading)
    assert sensor_data.sensor_id is not None
    assert sensor_data.sensor_type is not None
    assert sensor_data.is_valid is True


def test_telemetry_payload_includes_3d_position() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    assert isinstance(payload, dict)
    assert payload.get("schema_version") == 1
    assert isinstance(payload.get("ts_unix_ms"), int)

    position = payload.get("position")
    assert isinstance(position, dict)
    assert set(position.keys()) >= {"x", "y", "z"}
    assert isinstance(position["x"], float)
    assert isinstance(position["y"], float)
    assert isinstance(position["z"], float)

    cpu_usage = payload.get("cpu_usage")
    memory_usage = payload.get("memory_usage")
    assert isinstance(cpu_usage, float)
    assert isinstance(memory_usage, float)
    assert 0.0 <= cpu_usage <= 100.0
    assert 0.0 <= memory_usage <= 100.0


def test_sim_pause_start_stop_and_reset_control_commands() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    meta = MessageMetadata(message_type="control_command", source="test", destination="q_sim_service")

    pause = CommandMessage(command_name="sim.pause", parameters={}, metadata=meta)
    assert qsim.apply_control_command(pause) is True
    assert qsim.get_sim_state()["paused"] is True

    start = CommandMessage(command_name="sim.start", parameters={"speed": 2.0}, metadata=meta)
    assert qsim.apply_control_command(start) is True
    st = qsim.get_sim_state()
    assert st["running"] is True
    assert st["paused"] is False
    assert st["speed"] == 2.0

    qsim.world_model.position.x = 123.0
    reset = CommandMessage(command_name="sim.reset", parameters={}, metadata=meta)
    assert qsim.apply_control_command(reset) is True
    assert qsim.world_model.position.x == 0.0

    stop = CommandMessage(command_name="sim.stop", parameters={}, metadata=meta)
    assert qsim.apply_control_command(stop) is True
    st = qsim.get_sim_state()
    assert st["running"] is False
