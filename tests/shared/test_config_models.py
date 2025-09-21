import pytest
from pydantic import ValidationError

from qiki.shared.config_models import QSimServiceConfig, QCoreAgentConfig, load_config

# Создаем временную директорию для тестовых файлов
@pytest.fixture
def temp_config_dir(tmp_path):
    return tmp_path


class TestConfigModels:
    def test_qsim_service_config_valid(self):
        config_data = {
            "sim_tick_interval": 100,
            "sim_sensor_type": 1,
            "log_level": "INFO",
        }
        config = QSimServiceConfig(**config_data)
        assert config.sim_tick_interval == 100
        assert config.sim_sensor_type == 1
        assert config.log_level == "INFO"

    def test_qsim_service_config_invalid_type(self):
        with pytest.raises(ValidationError):
            QSimServiceConfig(
                sim_tick_interval="abc",
                sim_sensor_type=1,
                log_level="INFO",
            )

    def test_qsim_service_config_missing_field(self):
        with pytest.raises(ValidationError):
            QSimServiceConfig(sim_sensor_type=1, log_level="INFO")

    def test_qcore_agent_config_valid(self):
        config_data = {
            "tick_interval": 5,
            "log_level": "DEBUG",
            "recovery_delay": 30,
            "proposal_confidence_threshold": 0.75,
            "mock_neural_proposals_enabled": True,
            "grpc_server_address": "localhost:50051",
        }
        config = QCoreAgentConfig(**config_data)
        assert config.tick_interval == 5
        assert config.log_level == "DEBUG"
        assert config.recovery_delay == 30
        assert config.proposal_confidence_threshold == 0.75
        assert config.mock_neural_proposals_enabled is True
        assert config.grpc_server_address == "localhost:50051"

    def test_qcore_agent_config_invalid_type(self):
        with pytest.raises(ValidationError):
            QCoreAgentConfig(
                tick_interval="abc",
                log_level="INFO",
                recovery_delay=10,
                proposal_confidence_threshold=0.5,
                mock_neural_proposals_enabled=False,
                grpc_server_address="localhost:50051",
            )

    def test_qcore_agent_config_missing_field(self):
        with pytest.raises(ValidationError):
            QCoreAgentConfig(
                log_level="INFO",
                recovery_delay=10,
                proposal_confidence_threshold=0.5,
                mock_neural_proposals_enabled=False,
                grpc_server_address="localhost:50051",
            )


class TestLoadConfig:
    def test_load_config_yaml(self, temp_config_dir):
        config_path = temp_config_dir / "config.yaml"
        config_path.write_text(
            """
            sim_tick_interval: 10
            sim_sensor_type: 2
            log_level: WARNING
            """
        )
        config = load_config(config_path, QSimServiceConfig)
        assert isinstance(config, QSimServiceConfig)
        assert config.sim_tick_interval == 10
        assert config.sim_sensor_type == 2
        assert config.log_level == "WARNING"

    def test_load_config_json(self, temp_config_dir):
        config_path = temp_config_dir / "config.json"
        config_path.write_text(
            """
            {
                "tick_interval": 15,
                "log_level": "ERROR",
                "recovery_delay": 60,
                "proposal_confidence_threshold": 0.9,
                "mock_neural_proposals_enabled": false,
                "grpc_server_address": "remotehost:50052"
            }
            """
        )
        config = load_config(config_path, QCoreAgentConfig)
        assert isinstance(config, QCoreAgentConfig)
        assert config.tick_interval == 15
        assert config.log_level == "ERROR"
        assert config.recovery_delay == 60
        assert config.proposal_confidence_threshold == 0.9
        assert config.mock_neural_proposals_enabled is False
        assert config.grpc_server_address == "remotehost:50052"

    def test_load_config_invalid_data(self, temp_config_dir):
        config_path = temp_config_dir / "invalid.yaml"
        config_path.write_text(
            """
            sim_tick_interval: abc
            sim_sensor_type: 1
            log_level: INFO
            """
        )
        with pytest.raises(ValidationError):
            load_config(config_path, QSimServiceConfig)

    def test_load_config_file_not_found(self, temp_config_dir):
        config_path = temp_config_dir / "non_existent.yaml"
        with pytest.raises(FileNotFoundError):
            load_config(config_path, QSimServiceConfig)
