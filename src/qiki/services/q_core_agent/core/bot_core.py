import json
import os
import hashlib
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID as PyUUID

# Import generated protobuf classes
from qiki.shared.models.core import SensorData, ActuatorCommand, SensorTypeEnum, CommandTypeEnum

MOTOR_LEFT_ID = "37dcb32c-ae13-5156-ae80-0f4c663824de"
MOTOR_RIGHT_ID = "2b2c711f-0e36-5e6b-85fc-d8737fd5e1da"
SYSTEM_CONTROLLER_ID = "c0648061-af84-5c8a-a383-71218ba92082"


class BotCore:
    """
    Represents the fundamental, low-level definition of the bot entity within the Q-Core Agent microservice.
    Manages bot identification, static configuration, and raw sensor/actuator interaction points.
    """

    BOT_ID_FILE = ".qiki_bot.id"
    CONFIG_FILE = "bot_config.json"

    def __init__(self, base_path: str):
        self.base_path = base_path
        self._bot_id: Optional[str] = None
        self._config: Dict[str, Any] = {}
        self._runtime_sensor_snapshot: Dict[str, SensorData] = {}
        self._last_actuator_commands: Dict[str, ActuatorCommand] = {}
        self._sensor_callbacks: List[Callable[[SensorData], None]] = []

        self._load_config()
        self._initialize_bot_id()

    def _load_config(self):
        config_path = os.path.join(self.base_path, "config", self.CONFIG_FILE)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Bot configuration file not found: {config_path}")
        try:
            with open(config_path, "r") as f:
                self._config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {config_path}: {e}")

        if self._config.get("mode") == "minimal":
            print("BotCore running in minimal mode. Sensor/actuator methods will be non-operational.")

    def _initialize_bot_id(self):
        id_path = os.path.join(self.base_path, self.BOT_ID_FILE)
        if os.path.exists(id_path):
            with open(id_path, "r") as f:
                self._bot_id = f.read().strip()
        else:
            self._bot_id = self._generate_bot_id()
            with open(id_path, "w") as f:
                f.write(self._bot_id)

    def _generate_bot_id(self) -> str:
        timestamp = os.getenv("QIKI_BOT_INIT_TIMESTAMP", "")  # For testing/reproducibility
        if not timestamp:
            import datetime

            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        # Use a combination of timestamp, hostname, and a random component for uniqueness
        unique_string = f"{timestamp}-{os.uname().nodename}-{os.urandom(8).hex()}"
        hash_val = hashlib.sha256(unique_string.encode()).hexdigest()[:8]
        return f"QIKI-{timestamp[:8]}-{hash_val}"

    def get_id(self) -> str:
        """Returns the unique bot ID."""
        if not self._bot_id:
            raise RuntimeError("Bot ID not initialized.")
        return self._bot_id

    def get_property(self, property_name: str) -> Any:
        """Retrieves a static property from the loaded configuration."""
        return self._config.get(property_name)

    def register_sensor_callback(self, callback: Callable[[SensorData], None]):
        """Registers a callback function that will be invoked with new sensor data as it arrives."""
        self._sensor_callbacks.append(callback)

    def _process_incoming_sensor_data(self, sensor_data: SensorData):
        """Internal method to update runtime snapshot and trigger callbacks."""
        self._runtime_sensor_snapshot[sensor_data.sensor_id] = sensor_data
        for callback in self._sensor_callbacks:
            callback(sensor_data)

    def ingest_sensor_data(self, sensor_data: SensorData) -> None:
        """Public hook for feeding sensor data into the bot core."""

        self._process_incoming_sensor_data(sensor_data)

    def get_latest_sensor_value(self, sensor_id: str) -> Optional[SensorData]:
        """Retrieves the most recent value for a specific sensor."""
        if self._config.get("mode") == "minimal":
            return None  # Non-operational in minimal mode
        return self._runtime_sensor_snapshot.get(sensor_id)

    def get_sensor_history(self, sensor_id: str, n: int = 10) -> List[SensorData]:
        """Retrieves the last `n` values for a specific sensor. (Placeholder - full history not implemented yet)"""
        if self._config.get("mode") == "minimal":
            return []  # Non-operational in minimal mode
        # In a real implementation, this would involve a history buffer or database
        latest = self._runtime_sensor_snapshot.get(sensor_id)
        return [latest] if latest else []

    def send_actuator_command(self, command: ActuatorCommand):
        """Sends a raw command to an actuator."""
        if self._config.get("mode") == "minimal":
            print(f"Minimal mode: Actuator command for {command.actuator_id} ignored.")
            return

        # Validate actuator_id against hardware_profile
        actuator_ids = [act["id"] for act in self._config.get("hardware_profile", {}).get("actuators", [])]
        if str(command.actuator_id) not in actuator_ids:
            raise ValueError(f"Unknown actuator ID: {command.actuator_id}. Must be one of {actuator_ids}")

        self._last_actuator_commands[str(command.actuator_id)] = command
        # In a real system, this would send the command to the Q-Sim Service or hardware

    @property
    def current_sensor_snapshot(self) -> Dict[str, SensorData]:
        """Returns a dictionary of the last known values for all sensors."""
        return self._runtime_sensor_snapshot

    @property
    def last_actuator_commands(self) -> Dict[str, ActuatorCommand]:
        """Returns a dictionary of the last commands sent to all actuators."""
        return self._last_actuator_commands


# Example Usage (for testing purposes)
if __name__ == "__main__":
    # Create dummy config and id files for testing
    test_base_path = os.path.dirname(os.path.abspath(__file__))

    dummy_config_content = {
        "schema_version": "1.0",
        "bot_id": "QIKI-TEST-001",
        "bot_type": "test_bot",
        "mode": "full",
        "hardware_profile": {
            "max_speed_mps": 1.0,
            "power_capacity_wh": 500,
            "actuators": [
                {"id": MOTOR_LEFT_ID, "role": "motor_left", "type": "wheel_motor"},
                {"id": MOTOR_RIGHT_ID, "role": "motor_right", "type": "wheel_motor"},
                {"id": SYSTEM_CONTROLLER_ID, "role": "system_controller", "type": "main_controller"},
            ],
            "sensors": [
                {"id": "lidar_front", "type": "lidar"},
                {"id": "imu_main", "type": "imu"},
            ],
        },
    }

    # Adjust path for config file to be in the 'config' subdirectory
    config_dir = os.path.join(test_base_path, "..", "config")  # Go up one level to q_core_agent, then into config
    os.makedirs(config_dir, exist_ok=True)
    with open(os.path.join(config_dir, "bot_config.json"), "w") as f:
        json.dump(dummy_config_content, f, indent=2)

    # Ensure .qiki_bot.id is clean for testing new ID generation
    # .qiki_bot.id should be in the q_core_agent root, not core
    q_core_agent_root = os.path.abspath(os.path.join(test_base_path, ".."))
    if os.path.exists(os.path.join(q_core_agent_root, ".qiki_bot.id")):
        os.remove(os.path.join(q_core_agent_root, ".qiki_bot.id"))

    try:
        # Pass the q_core_agent root as base_path
        bot = BotCore(base_path=q_core_agent_root)
        print(f"Bot ID: {bot.get_id()}")
        print(f"Bot Type: {bot.get_property('bot_type')}")

        # Simulate incoming sensor data
        # Create a Pydantic SensorData instance
        sensor_data_pydantic = SensorData(
            sensor_id=PyUUID("lidar_front"),
            sensor_type=SensorTypeEnum.LIDAR,
            scalar_data=15.3,
            string_data="meters",
        )
        bot._process_incoming_sensor_data(sensor_data_pydantic)  # Simulate internal data reception

        print(f"Latest lidar value: {bot.current_sensor_snapshot.get('lidar_front').scalar_data}")

        # Simulate sending actuator command
        # Create a Pydantic ActuatorCommand instance
        actuator_command_pydantic = ActuatorCommand(
            actuator_id=PyUUID(MOTOR_LEFT_ID),
            command_type=CommandTypeEnum.SET_VELOCITY,
            int_value=75,
        )
        bot.send_actuator_command(actuator_command_pydantic)
        print(f"Last motor_left command value: {bot.last_actuator_commands.get(MOTOR_LEFT_ID).int_value}")

        # Test minimal mode
        dummy_config_content["mode"] = "minimal"
        with open(os.path.join(config_dir, "bot_config.json"), "w") as f:
            json.dump(dummy_config_content, f, indent=2)

        bot_minimal = BotCore(base_path=q_core_agent_root)
        print(f"Bot ID in minimal mode: {bot_minimal.get_id()}")
        print(f"Latest lidar value in minimal mode: {bot_minimal.get_latest_sensor_value('lidar_front')}")
        bot_minimal.send_actuator_command(actuator_command_pydantic)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Clean up dummy files
        os.remove(os.path.join(config_dir, "bot_config.json"))
        if os.path.exists(os.path.join(q_core_agent_root, ".qiki_bot.id")):
            os.remove(os.path.join(q_core_agent_root, ".qiki_bot.id"))
