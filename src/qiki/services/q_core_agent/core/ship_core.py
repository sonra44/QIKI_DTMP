import json
import os
import hashlib
from typing import Any, Callable, Dict, List, Optional, Sequence
from dataclasses import dataclass

# Import generated protobuf classes
import sys

# NOTE: This module is part of the qiki package. Mutating sys.path at import-time is
# dangerous and can mask real import issues.
#
# Keep the legacy sys.path bootstrap only for direct execution
# (`python ship_core.py`), not for normal package imports.
if not __package__:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
    generated_path = os.path.join(project_root, "generated")
    if project_root not in sys.path:
        sys.path.append(project_root)
    if generated_path not in sys.path:
        sys.path.append(generated_path)

from generated import sensor_raw_in_pb2
from generated import actuator_raw_out_pb2


@dataclass
class HullStatus:
    """Статус корпуса корабля"""

    integrity: float
    max_integrity: float
    mass_kg: float
    volume_m3: float
    compartments: Dict[str, Dict[str, float]]


@dataclass
class PowerSystemStatus:
    """Статус энергосистем"""

    reactor_output_mw: float
    reactor_max_output_mw: float
    reactor_fuel_hours: float
    reactor_temperature_k: float
    battery_charge_mwh: float
    battery_capacity_mwh: float
    power_distribution: Dict[str, Dict[str, float]]


@dataclass
class PropulsionStatus:
    """Статус двигательной установки"""

    main_drive_thrust_n: float
    main_drive_max_thrust_n: float
    main_drive_fuel_kg: float
    main_drive_status: str
    rcs_status: Dict[str, Dict[str, Any]]


@dataclass
class SensorStatus:
    """Статус сенсорных систем"""

    active_sensors: List[str]
    sensor_data: Dict[str, Dict[str, Any]]
    total_power_consumption_kw: float


@dataclass
class LifeSupportStatus:
    """Статус систем жизнеобеспечения"""

    atmosphere: Dict[str, float]
    water_recycling: Dict[str, Any]
    air_recycling: Dict[str, Any]


@dataclass
class ComputingStatus:
    """Статус вычислительных систем"""

    qiki_core_status: str
    qiki_temperature_k: float
    qiki_power_consumption_kw: float
    backup_systems: Dict[str, str]


class ShipCore:
    """
    Represents the fundamental definition of the ship entity within the Q-Core Agent.
    Manages ship identification, static configuration, and raw sensor/actuator interaction points.
    Replaces BotCore for space-based operations.
    """

    SHIP_ID_FILE = ".qiki_ship.id"
    CONFIG_FILE = "ship_config.json"

    def __init__(self, base_path: str):
        self.base_path = base_path
        self._ship_id: Optional[str] = None
        self._config: Dict[str, Any] = {}
        self._runtime_sensor_snapshot: Dict[str, sensor_raw_in_pb2.SensorReading] = {}
        self._last_actuator_commands: Dict[str, actuator_raw_out_pb2.ActuatorCommand] = {}
        self._sensor_callbacks: List[Callable[[sensor_raw_in_pb2.SensorReading], None]] = []

        self._load_config()
        self._initialize_ship_id()

    def _load_config(self):
        config_path = os.path.join(self.base_path, "config", self.CONFIG_FILE)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Ship configuration file not found: {config_path}")
        try:
            with open(config_path, "r") as f:
                self._config = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {config_path}: {e}")

        if self._config.get("mode") == "minimal":
            print("ShipCore running in minimal mode. Sensor/actuator methods will be non-operational.")

    def _initialize_ship_id(self):
        id_path = os.path.join(self.base_path, self.SHIP_ID_FILE)
        if os.path.exists(id_path):
            with open(id_path, "r") as f:
                self._ship_id = f.read().strip()
        else:
            self._ship_id = self._generate_ship_id()
            with open(id_path, "w") as f:
                f.write(self._ship_id)

    def _generate_ship_id(self) -> str:
        timestamp = os.getenv("QIKI_SHIP_INIT_TIMESTAMP", "")
        if not timestamp:
            import datetime

            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        unique_string = f"{timestamp}-{os.uname().nodename}-{os.urandom(8).hex()}"
        hash_val = hashlib.sha256(unique_string.encode()).hexdigest()[:8]
        return f"QIKI-SHIP-{timestamp[:8]}-{hash_val}"

    def get_id(self) -> str:
        """Returns the unique ship ID."""
        if not self._ship_id:
            raise RuntimeError("Ship ID not initialized.")
        return self._ship_id

    def get_ship_class(self) -> str:
        """Returns the ship class (e.g., 'light_explorer')."""
        return self._config.get("ship_class", "unknown")

    def get_property(self, property_name: str) -> Any:
        """Retrieves a static property from the loaded configuration."""
        return self._config.get(property_name)

    # === Ship System Status Methods ===

    def get_hull_status(self) -> HullStatus:
        """Returns current hull status."""
        hull_config = self._config.get("hull", {})
        return HullStatus(
            integrity=hull_config.get("integrity", 0.0),
            max_integrity=hull_config.get("max_integrity", 100.0),
            mass_kg=hull_config.get("mass_kg", 0.0),
            volume_m3=hull_config.get("volume_m3", 0.0),
            compartments=hull_config.get("compartments", {}),
        )

    def get_power_status(self) -> PowerSystemStatus:
        """Returns current power system status."""
        power_config = self._config.get("power_systems", {})
        reactor = power_config.get("reactor", {})
        batteries = power_config.get("batteries", [{}])
        battery = batteries[0] if batteries else {}

        return PowerSystemStatus(
            reactor_output_mw=reactor.get("current_output_mw", 0.0),
            reactor_max_output_mw=reactor.get("max_output_mw", 0.0),
            reactor_fuel_hours=reactor.get("fuel_remaining_hours", 0.0),
            reactor_temperature_k=reactor.get("temperature_k", 0.0),
            battery_charge_mwh=battery.get("current_charge_mwh", 0.0),
            battery_capacity_mwh=battery.get("capacity_mwh", 0.0),
            power_distribution=power_config.get("power_distribution", {}),
        )

    def get_propulsion_status(self) -> PropulsionStatus:
        """Returns current propulsion system status."""
        prop_config = self._config.get("propulsion", {})
        main_drive = prop_config.get("main_drive", {})
        rcs_thrusters = prop_config.get("maneuvering_thrusters", [])

        rcs_status = {}
        for thruster in rcs_thrusters:
            rcs_status[thruster.get("id", "unknown")] = {
                "thrust_n": thruster.get("max_thrust_n", 0),
                "fuel_kg": thruster.get("fuel_remaining_kg", 0),
                "status": thruster.get("status", "unknown"),
                "position": thruster.get("position", [0, 0, 0]),
            }

        return PropulsionStatus(
            main_drive_thrust_n=main_drive.get("current_thrust_n", 0.0),
            main_drive_max_thrust_n=main_drive.get("max_thrust_n", 0.0),
            main_drive_fuel_kg=main_drive.get("fuel_remaining_kg", 0.0),
            main_drive_status=main_drive.get("status", "unknown"),
            rcs_status=rcs_status,
        )

    def get_sensor_status(self) -> SensorStatus:
        """Returns current sensor system status."""
        sensors_config = self._config.get("sensors", [])
        active_sensors = []
        sensor_data = {}
        total_power = 0.0

        for sensor in sensors_config:
            sensor_id = sensor.get("id", "unknown")
            status = sensor.get("status", "offline")
            power = sensor.get("power_consumption_kw", 0.0)

            if status == "active":
                active_sensors.append(sensor_id)
                total_power += power

            sensor_data[sensor_id] = {
                "type": sensor.get("type", "unknown"),
                "status": status,
                "power_kw": power,
                "range_km": sensor.get("range_km", 0),
                "position": sensor.get("mount_position", [0, 0, 0]),
            }

        return SensorStatus(
            active_sensors=active_sensors,
            sensor_data=sensor_data,
            total_power_consumption_kw=total_power,
        )

    def get_life_support_status(self) -> LifeSupportStatus:
        """Returns current life support status."""
        ls_config = self._config.get("life_support", {})
        return LifeSupportStatus(
            atmosphere=ls_config.get("atmosphere", {}),
            water_recycling=ls_config.get("water_recycling", {}),
            air_recycling=ls_config.get("air_recycling", {}),
        )

    def get_computing_status(self) -> ComputingStatus:
        """Returns current computing system status."""
        comp_config = self._config.get("computing", {})
        qiki_core = comp_config.get("qiki_core", {})
        backup_systems = {}

        for backup in comp_config.get("backup_computers", []):
            backup_systems[backup.get("id", "unknown")] = backup.get("status", "unknown")

        return ComputingStatus(
            qiki_core_status=qiki_core.get("status", "unknown"),
            qiki_temperature_k=qiki_core.get("core_temperature_k", 0.0),
            qiki_power_consumption_kw=qiki_core.get("power_consumption_kw", 0.0),
            backup_systems=backup_systems,
        )

    # === Sensor/Actuator Interface ===

    def register_sensor_callback(self, callback: Callable[[sensor_raw_in_pb2.SensorReading], None]):
        """Registers a callback function for new sensor data."""
        self._sensor_callbacks.append(callback)

    def _process_incoming_sensor_data(self, sensor_data: sensor_raw_in_pb2.SensorReading):
        """Internal method to update runtime snapshot and trigger callbacks."""
        self._runtime_sensor_snapshot[sensor_data.sensor_id] = sensor_data
        for callback in self._sensor_callbacks:
            callback(sensor_data)

    def get_latest_sensor_value(self, sensor_id: str) -> Optional[sensor_raw_in_pb2.SensorReading]:
        """Retrieves the most recent value for a specific sensor."""
        if self._config.get("mode") == "minimal":
            return None
        return self._runtime_sensor_snapshot.get(sensor_id)

    def iter_latest_sensor_readings(self) -> Sequence[sensor_raw_in_pb2.SensorReading]:
        """Returns a snapshot of latest sensor readings (best-effort, minimal-mode safe)."""
        if self._config.get("mode") == "minimal":
            return ()
        return tuple(self._runtime_sensor_snapshot.values())

    def send_actuator_command(self, command: actuator_raw_out_pb2.ActuatorCommand):
        """Sends a raw command to a ship system (actuator)."""
        if self._config.get("mode") == "minimal":
            print(f"Minimal mode: Ship system command for {command.actuator_id} ignored.")
            return

        # Validate against ship systems (sensors, thrusters, etc.)
        all_systems = []

        # Add all sensor IDs
        for sensor in self._config.get("sensors", []):
            all_systems.append(sensor.get("id"))

        # Add thruster IDs
        propulsion = self._config.get("propulsion", {})
        if "main_drive" in propulsion:
            all_systems.append(propulsion["main_drive"].get("id"))

        for thruster in propulsion.get("maneuvering_thrusters", []):
            all_systems.append(thruster.get("id"))

        actuator_id_str = (
            command.actuator_id.value if hasattr(command.actuator_id, "value") else str(command.actuator_id)
        )
        if actuator_id_str not in all_systems:
            raise ValueError(f"Unknown ship system ID: {actuator_id_str}. Must be one of {all_systems}")

        self._last_actuator_commands[actuator_id_str] = command
        print(f"ShipCore: Command sent to {actuator_id_str}: {command.command_type}")

    @property
    def current_sensor_snapshot(self) -> Dict[str, sensor_raw_in_pb2.SensorReading]:
        """Returns a dictionary of the last known values for all sensors."""
        return self._runtime_sensor_snapshot

    @property
    def last_actuator_commands(self) -> Dict[str, actuator_raw_out_pb2.ActuatorCommand]:
        """Returns a dictionary of the last commands sent to all ship systems."""
        return self._last_actuator_commands

    def get_ship_summary(self) -> Dict[str, Any]:
        """Returns a comprehensive summary of ship status."""
        hull = self.get_hull_status()
        power = self.get_power_status()
        propulsion = self.get_propulsion_status()
        sensors = self.get_sensor_status()
        life_support = self.get_life_support_status()
        computing = self.get_computing_status()

        return {
            "ship_id": self.get_id(),
            "ship_class": self.get_ship_class(),
            "hull_integrity_percent": hull.integrity,
            "reactor_output_percent": (power.reactor_output_mw / power.reactor_max_output_mw) * 100
            if power.reactor_max_output_mw > 0
            else 0,
            "battery_charge_percent": (power.battery_charge_mwh / power.battery_capacity_mwh) * 100
            if power.battery_capacity_mwh > 0
            else 0,
            "main_drive_status": propulsion.main_drive_status,
            "active_sensors": len(sensors.active_sensors),
            "life_support_status": life_support.atmosphere.get("pressure_kpa", 0) > 50,  # Simplified check
            "qiki_core_status": computing.qiki_core_status,
            "total_mass_kg": hull.mass_kg,
        }


# Example Usage (for testing purposes)
if __name__ == "__main__":
    # Allow direct execution while keeping normal package imports clean.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "..", ".."))
    src_root = os.path.join(repo_root, "src")
    for path in (src_root, repo_root):
        if path not in sys.path:
            sys.path.append(path)

    try:
        # Test with the q_core_agent directory as base_path
        q_core_agent_root = os.path.abspath(os.path.join(current_dir, ".."))
        ship = ShipCore(base_path=q_core_agent_root)

        print(f"Ship ID: {ship.get_id()}")
        print(f"Ship Class: {ship.get_ship_class()}")

        # Test system status methods
        hull_status = ship.get_hull_status()
        print(f"Hull Integrity: {hull_status.integrity}%")

        power_status = ship.get_power_status()
        print(f"Reactor Output: {power_status.reactor_output_mw} MW")

        propulsion_status = ship.get_propulsion_status()
        print(f"Main Drive: {propulsion_status.main_drive_status}")

        sensor_status = ship.get_sensor_status()
        print(f"Active Sensors: {sensor_status.active_sensors}")

        life_support_status = ship.get_life_support_status()
        print(f"Atmosphere Pressure: {life_support_status.atmosphere.get('pressure_kpa', 0)} kPa")

        computing_status = ship.get_computing_status()
        print(f"QIKI Core: {computing_status.qiki_core_status}")

        # Test summary
        summary = ship.get_ship_summary()
        print(f"Ship Summary: {summary}")

    except Exception as e:
        print(f"An error occurred: {e}")
