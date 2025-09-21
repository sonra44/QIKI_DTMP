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
from generated.common_types_pb2 import UUID, Vector3 as ProtoVector3, SensorType as ProtoSensorType, Unit as ProtoUnit
from uuid import uuid4
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.json_format import MessageToDict
from shared.config_models import QSimServiceConfig, load_config


class QSimService:
    def __init__(self, config: QSimServiceConfig):
        self.config = config
        self.world_model = WorldModel()
        self.sensor_data_queue = []  # Simulate incoming sensor data
        self.actuator_command_queue = []  # Simulate outgoing actuator commands
        logger.info("QSimService initialized.")
        # Cycle between primary sim sensor and IMU to provide minimal multi-sensor stream
        primary = int(self.config.sim_sensor_type)
        imu = int(ProtoSensorType.IMU)
        self._sensor_cycle = [primary, imu if primary != imu else int(ProtoSensorType.LIDAR)]
        self._sensor_index = 0

    def generate_sensor_data(self) -> SensorReading:
        # Generate sensor data based on world model state
        timestamp = Timestamp()
        timestamp.GetCurrentTime()
        world_state = self.world_model.get_state()
        # Choose sensor type from cycle (LIDAR <-> IMU)
        sensor_type = self._sensor_cycle[self._sensor_index]
        self._sensor_index = (self._sensor_index + 1) % len(self._sensor_cycle)

        if sensor_type == int(ProtoSensorType.LIDAR):
            # Simple range-like scalar: use X position as placeholder
            return SensorReading(
                sensor_id=UUID(value=str(uuid4())),
                sensor_type=sensor_type,
                timestamp=timestamp,
                scalar_data=world_state["position"]["x"],
                unit=ProtoUnit.METERS,
                is_valid=True,
            )
        elif sensor_type == int(ProtoSensorType.IMU):
            # IMU orientation as Euler (roll, pitch, yaw) in degrees using heading from world model
            roll = 0.0
            pitch = 0.0
            yaw = float(world_state["heading"])  # degrees
            return SensorReading(
                sensor_id=UUID(value=str(uuid4())),
                sensor_type=sensor_type,
                timestamp=timestamp,
                vector_data=ProtoVector3(x=roll, y=pitch, z=yaw),
                unit=ProtoUnit.DEGREES,
                is_valid=True,
            )
        else:
            # Fallback to LIDAR-like scalar if unknown type
            return SensorReading(
                sensor_id=UUID(value=str(uuid4())),
                sensor_type=int(ProtoSensorType.LIDAR),
                timestamp=timestamp,
                scalar_data=world_state["position"]["x"],
                unit=ProtoUnit.METERS,
                is_valid=True,
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
