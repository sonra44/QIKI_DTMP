import time
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(ROOT_DIR)

from services.q_sim_service.logger import setup_logging, logger
from services.q_sim_service.core.world_model import WorldModel
from generated.sensor_raw_in_pb2 import SensorReading
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import UUID
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.json_format import MessageToDict
from UP.config_models import QSimServiceConfig, load_config


class QSimService:
    def __init__(self, config: QSimServiceConfig):
        self.config = config
        self.world_model = WorldModel()
        self.sensor_data_queue = []  # Simulate incoming sensor data
        self.actuator_command_queue = []  # Simulate outgoing actuator commands
        logger.info("QSimService initialized.")

    def generate_sensor_data(self) -> SensorReading:
        # Generate sensor data based on world model state
        timestamp = Timestamp()
        timestamp.GetCurrentTime()
        world_state = self.world_model.get_state()
        return SensorReading(
            sensor_id=UUID(value="sim_lidar_front"),
            sensor_type=self.config.sim_sensor_type,  # LIDAR
            timestamp=timestamp,
            scalar_data=world_state["position"][
                "x"
            ],  # Example: return X position as scalar data
        )

    def receive_actuator_command(self, command: ActuatorCommand):
        self.actuator_command_queue.append(command)
        logger.info(f"QSim received actuator command: {MessageToDict(command)}")
        self.world_model.update(command)  # Update world model based on command

    def run(self):
        logger.info("QSimService started.")
        try:
            while True:
                self.step()  # Call the new step method
                time.sleep(self.config.sim_tick_interval)
        except KeyboardInterrupt:
            logger.info("QSimService stopped by user.")

    def step(self):
        """
        Performs one step of the simulation.
        """
        # Advance world model state
        delta_time = self.config.sim_tick_interval
        self.world_model.step(delta_time)

        # Generate sensor data
        sensor_data = self.generate_sensor_data()
        self.sensor_data_queue.append(sensor_data)
        logger.debug(f"Generated sensor data: {MessageToDict(sensor_data)}")


if __name__ == "__main__":
    # Настройка логирования - используем собственный config
    setup_logging(default_path="config.yaml")

    # Загрузка конфигурации через Pydantic
    config_path = Path(__file__).parent / "config.yaml"
    config = load_config(config_path, QSimServiceConfig)

    sim_service = QSimService(config)
    sim_service.run()
