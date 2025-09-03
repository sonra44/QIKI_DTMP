
import time
import sys
import os
import yaml
import asyncio
from typing import Dict, Any

# Добавляем корневую директорию проекта в sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(ROOT_DIR)

from services.q_core_agent.core.agent_logger import setup_logging, logger
from services.q_sim_service.core.world_model import WorldModel
from generated.sensor_raw_in_pb2 import SensorReading
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import UUID
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.json_format import MessageToDict

class QSimService:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.world_model = WorldModel()
        queue_size = self.config.get("queue_maxsize", 64)
        self.sensor_data_queue = asyncio.Queue(maxsize=queue_size)
        self.actuator_command_queue = asyncio.Queue(maxsize=queue_size)
        logger.info("QSimService initialized.")

    def generate_sensor_data(self) -> SensorReading:
        # Generate sensor data based on world model state
        timestamp = Timestamp()
        timestamp.GetCurrentTime()
        world_state = self.world_model.get_state()
        return SensorReading(
            sensor_id=UUID(value="sim_lidar_front"),
            sensor_type=self.config.get("sim_sensor_type", 1), # LIDAR
            timestamp=timestamp,
            scalar_data=world_state["position"]["x"] # Example: return X position as scalar data
        )

    def receive_actuator_command(self, command: ActuatorCommand):
        try:
            self.actuator_command_queue.put_nowait(command)
        except asyncio.QueueFull:
            logger.warning("Actuator command queue full, dropping command")
        else:
            logger.info(f"QSim received actuator command: {MessageToDict(command)}")
            self.world_model.update(command)  # Update world model based on command

    def run(self):
        logger.info("QSimService started.")
        try:
            while True:
                self.step() # Call the new step method
                time.sleep(self.config.get("sim_tick_interval", 1))
        except KeyboardInterrupt:
            logger.info("QSimService stopped by user.")

    def step(self):
        """
        Performs one step of the simulation.
        """
        # Advance world model state
        delta_time = self.config.get("sim_tick_interval", 1)
        self.world_model.step(delta_time)

        # Generate sensor data
        sensor_data = self.generate_sensor_data()
        try:
            self.sensor_data_queue.put_nowait(sensor_data)
        except asyncio.QueueFull:
            logger.warning("Sensor data queue full, dropping data")
        else:
            logger.debug(f"Generated sensor data: {MessageToDict(sensor_data)}")

def load_config(path='config.yaml'):
    config_path = os.path.join(os.path.dirname(__file__), path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
            
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

if __name__ == "__main__":
    # Настройка логирования
    log_config_path = os.path.join(os.path.dirname(__file__), '..', 'q_core_agent', 'config', 'logging.yaml')
    setup_logging(default_path=log_config_path)

    config = load_config()
    sim_service = QSimService(config)
    sim_service.run()
