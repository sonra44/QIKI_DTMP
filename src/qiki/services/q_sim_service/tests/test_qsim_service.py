"""Test for QSimService functionality."""

import pytest
from qiki.services.q_sim_service.main import QSimService
from qiki.services.q_sim_service.grpc_server import QSimAPIService
from qiki.shared.config_models import QSimServiceConfig
from generated.q_sim_api_pb2 import HealthCheckRequest, HealthCheckResponse
from generated.sensor_raw_in_pb2 import SensorReading


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