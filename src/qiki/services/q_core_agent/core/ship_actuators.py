"""
Ship Actuator Control System
Provides high-level interfaces for controlling ship systems.
Translates pilot commands into low-level actuator commands.
"""

import os
import sys

# NOTE: This module is part of the qiki package. Mutating sys.path at import-time is
# dangerous and can mask real import issues.
#
# Keep the legacy sys.path bootstrap only for direct execution
# (`python ship_actuators.py`), not for normal package imports.
if not __package__:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
    generated_path = os.path.join(project_root, "generated")
    if project_root not in sys.path:
        sys.path.append(project_root)
    if generated_path not in sys.path:
        sys.path.append(generated_path)

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

RCS_FORWARD_ID = "e6b718f2-769c-527c-a931-d2d7bb2cad82"
RCS_AFT_ID = "aad7ce7d-9ee6-5949-9c45-c3baf309ca44"
RCS_PORT_ID = "e03efa3e-5735-5a82-8f5c-9a9d9dfff351"
RCS_STARBOARD_ID = "3ceca74a-2a9e-5aec-a308-4c24c9102324"

try:
    from .ship_core import ShipCore
    from .agent_logger import logger
except ImportError:
    import ship_core
    import agent_logger

    ShipCore = ship_core.ShipCore
    logger = agent_logger.logger

try:
    from generated.actuator_raw_out_pb2 import ActuatorCommand
    from generated.common_types_pb2 import UUID, Vector3, Unit
    from google.protobuf.timestamp_pb2 import Timestamp
except ImportError:
    # Mock classes for development
    class MockActuatorCommand:
        def __init__(self, **kwargs):
            self.command_id = ""
            self.actuator_id = ""
            self.timestamp = None
            self.float_value = 0.0
            self.int_value = 0
            self.bool_value = False
            self.vector_value = None
            self.unit = 0
            self.command_type = 0
            self.confidence = 1.0
            self.timeout_ms = 0
            self.ack_required = False
            self.retry_count = 0
            for key, value in kwargs.items():
                setattr(self, key, value)

        class CommandType:
            SET_VELOCITY = 1
            ROTATE = 2
            ENABLE = 3
            DISABLE = 4
            SET_MODE = 5

    class MockUUID:
        def __init__(self, value=""):
            self.value = value

    class MockVector3:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x = x
            self.y = y
            self.z = z

    class MockUnit:
        PERCENT = 3
        METERS = 1
        DEGREES = 2
        WATTS = 6

    class MockTimestamp:
        def GetCurrentTime(self):
            pass

    ActuatorCommand = MockActuatorCommand
    UUID = MockUUID
    Vector3 = MockVector3
    Unit = MockUnit
    Timestamp = MockTimestamp


class ThrusterAxis(Enum):
    """Thruster axis directions for RCS control."""

    FORWARD = "forward"  # +X axis
    BACKWARD = "backward"  # -X axis
    PORT = "port"  # +Y axis (left)
    STARBOARD = "starboard"  # -Y axis (right)
    UP = "up"  # +Z axis
    DOWN = "down"  # -Z axis


class PropulsionMode(Enum):
    """Propulsion system modes."""

    IDLE = "idle"
    MANEUVERING = "maneuvering"  # RCS only
    CRUISE = "cruise"  # Main drive
    EMERGENCY = "emergency"  # All systems


@dataclass
class ThrustVector:
    """3D thrust vector in Newtons."""

    x: float = 0.0  # Forward/backward
    y: float = 0.0  # Port/starboard
    z: float = 0.0  # Up/down


@dataclass
class PowerAllocation:
    """Power allocation for ship systems."""

    life_support: float = 8.0  # MW
    propulsion: float = 15.0  # MW
    sensors: float = 5.0  # MW
    qiki_core: float = 3.0  # MW
    shields: float = 4.0  # MW


class ShipActuatorController:
    """
    High-level interface for controlling ship systems.
    Translates pilot commands into actuator commands.
    """

    def __init__(self, ship_core: ShipCore):
        self.ship_core = ship_core
        self.current_mode = PropulsionMode.IDLE
        logger.info("ShipActuatorController initialized.")

    # === PROPULSION CONTROL ===

    def set_main_drive_thrust(self, thrust_percent: float, duration_sec: Optional[float] = None) -> bool:
        """
        Set main drive thrust as percentage of maximum.

        Args:
            thrust_percent: 0-100% of maximum thrust
            duration_sec: Optional duration limit

        Returns:
            bool: Success status
        """
        try:
            # Validate input
            thrust_percent = max(0.0, min(100.0, thrust_percent))

            # Create actuator command
            command = ActuatorCommand()
            command.actuator_id.value = "ion_drive_array"

            # Skip timestamp for now - not critical for testing
            # command.timestamp = timestamp

            command.command_type = ActuatorCommand.CommandType.SET_VELOCITY
            command.float_value = thrust_percent
            command.unit = Unit.PERCENT
            command.confidence = 1.0
            command.ack_required = True

            if duration_sec:
                command.timeout_ms = int(duration_sec * 1000)

            # Send command
            self.ship_core.send_actuator_command(command)

            if thrust_percent > 0:
                self.current_mode = PropulsionMode.CRUISE
            else:
                self.current_mode = PropulsionMode.IDLE

            logger.info(f"Main drive set to {thrust_percent:.1f}% thrust")
            return True

        except Exception as e:
            logger.error(f"Failed to set main drive thrust: {e}")
            return False

    def fire_rcs_thruster(
        self,
        thruster_axis: ThrusterAxis,
        thrust_percent: float,
        duration_sec: float = 1.0,
    ) -> bool:
        """
        Fire RCS thruster in specified direction.

        Args:
            thruster_axis: Direction to thrust
            thrust_percent: 0-100% of maximum thrust
            duration_sec: Duration of thrust

        Returns:
            bool: Success status
        """
        try:
            # Map axis to thruster ID
            thruster_map = {
                ThrusterAxis.FORWARD: RCS_FORWARD_ID,
                ThrusterAxis.BACKWARD: RCS_AFT_ID,
                ThrusterAxis.PORT: RCS_PORT_ID,
                ThrusterAxis.STARBOARD: RCS_STARBOARD_ID,
            }

            thruster_id = thruster_map.get(thruster_axis)
            if not thruster_id:
                logger.error(f"Unsupported thruster axis: {thruster_axis}")
                return False

            # Validate input
            thrust_percent = max(0.0, min(100.0, thrust_percent))

            # Create actuator command
            command = ActuatorCommand()
            command.actuator_id.value = thruster_id

            # Skip timestamp for now - not critical for testing
            # command.timestamp = timestamp

            command.command_type = ActuatorCommand.CommandType.SET_VELOCITY
            command.float_value = thrust_percent
            command.unit = Unit.PERCENT
            command.confidence = 1.0
            command.timeout_ms = int(duration_sec * 1000)
            command.ack_required = True

            # Send command
            self.ship_core.send_actuator_command(command)

            self.current_mode = PropulsionMode.MANEUVERING
            logger.info(f"RCS {thruster_axis.value} fired at {thrust_percent:.1f}% for {duration_sec:.1f}s")
            return True

        except Exception as e:
            logger.error(f"Failed to fire RCS thruster: {e}")
            return False

    def execute_maneuver(self, thrust_vector: ThrustVector, duration_sec: float = 2.0) -> bool:
        """
        Execute complex maneuver using multiple RCS thrusters.

        Args:
            thrust_vector: Desired thrust in 3D space
            duration_sec: Maneuver duration

        Returns:
            bool: Success status
        """
        try:
            success_count = 0
            total_commands = 0

            # X-axis (forward/backward)
            if abs(thrust_vector.x) > 0.1:
                total_commands += 1
                axis = ThrusterAxis.FORWARD if thrust_vector.x > 0 else ThrusterAxis.BACKWARD
                thrust_percent = min(100.0, abs(thrust_vector.x))
                if self.fire_rcs_thruster(axis, thrust_percent, duration_sec):
                    success_count += 1

            # Y-axis (port/starboard)
            if abs(thrust_vector.y) > 0.1:
                total_commands += 1
                axis = ThrusterAxis.PORT if thrust_vector.y > 0 else ThrusterAxis.STARBOARD
                thrust_percent = min(100.0, abs(thrust_vector.y))
                if self.fire_rcs_thruster(axis, thrust_percent, duration_sec):
                    success_count += 1

            # Z-axis not implemented yet (up/down thrusters)
            if abs(thrust_vector.z) > 0.1:
                logger.warning(f"Z-axis thrust not supported yet: {thrust_vector.z}")

            success = success_count == total_commands if total_commands > 0 else True
            logger.info(f"Maneuver executed: {success_count}/{total_commands} commands successful")
            return success

        except Exception as e:
            logger.error(f"Failed to execute maneuver: {e}")
            return False

    def emergency_stop(self) -> bool:
        """
        Emergency stop - shutdown all propulsion systems.

        Returns:
            bool: Success status
        """
        try:
            success_count = 0

            # Stop main drive
            if self.set_main_drive_thrust(0.0):
                success_count += 1

            # Stop all RCS thrusters
            for axis in [
                ThrusterAxis.FORWARD,
                ThrusterAxis.BACKWARD,
                ThrusterAxis.PORT,
                ThrusterAxis.STARBOARD,
            ]:
                if self.fire_rcs_thruster(axis, 0.0, 0.1):
                    success_count += 1

            self.current_mode = PropulsionMode.EMERGENCY
            logger.warning(f"EMERGENCY STOP executed: {success_count} systems stopped")
            return success_count > 0

        except Exception as e:
            logger.error(f"Failed emergency stop: {e}")
            return False

    # === POWER CONTROL ===

    def set_power_allocation(self, allocation: PowerAllocation) -> bool:
        """
        Set power allocation across ship systems.

        Args:
            allocation: Power allocation in MW for each system

        Returns:
            bool: Success status
        """
        try:
            power_status = self.ship_core.get_power_status()
            total_requested = (
                allocation.life_support
                + allocation.propulsion
                + allocation.sensors
                + allocation.qiki_core
                + allocation.shields
            )

            if total_requested > power_status.reactor_max_output_mw:
                logger.warning(
                    f"Power allocation exceeds reactor capacity: {total_requested:.1f}/{power_status.reactor_max_output_mw:.1f} MW"
                )
                return False

            # Create power allocation commands (simplified)
            systems = {
                "life_support": allocation.life_support,
                "propulsion": allocation.propulsion,
                "sensors": allocation.sensors,
                "qiki_core": allocation.qiki_core,
                "shields": allocation.shields,
            }

            for system_name, power_mw in systems.items():
                command = ActuatorCommand()
                command.actuator_id.value = f"power_distribution_{system_name}"

                # Skip timestamp for now - not critical for testing
                # command.timestamp = timestamp

                command.command_type = ActuatorCommand.CommandType.SET_MODE
                command.float_value = power_mw
                command.unit = Unit.WATTS
                command.confidence = 1.0

                # Note: In real implementation, would send to power management system
                logger.debug(f"Power allocation: {system_name} = {power_mw:.1f} MW")

            logger.info(f"Power allocation set: {total_requested:.1f} MW total")
            return True

        except Exception as e:
            logger.error(f"Failed to set power allocation: {e}")
            return False

    # === SENSOR CONTROL ===

    def activate_sensor(self, sensor_id: str) -> bool:
        """
        Activate a specific sensor.

        Args:
            sensor_id: ID of sensor to activate

        Returns:
            bool: Success status
        """
        try:
            command = ActuatorCommand()
            command.actuator_id.value = sensor_id

            # Skip timestamp for now - not critical for testing
            # command.timestamp = timestamp

            command.command_type = ActuatorCommand.CommandType.ENABLE
            command.bool_value = True
            command.confidence = 1.0
            command.ack_required = True

            self.ship_core.send_actuator_command(command)
            logger.info(f"Sensor activated: {sensor_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to activate sensor {sensor_id}: {e}")
            return False

    def deactivate_sensor(self, sensor_id: str) -> bool:
        """
        Deactivate a specific sensor.

        Args:
            sensor_id: ID of sensor to deactivate

        Returns:
            bool: Success status
        """
        try:
            command = ActuatorCommand()
            command.actuator_id.value = sensor_id

            # Skip timestamp for now - not critical for testing
            # command.timestamp = timestamp

            command.command_type = ActuatorCommand.CommandType.DISABLE
            command.bool_value = False
            command.confidence = 1.0
            command.ack_required = True

            self.ship_core.send_actuator_command(command)
            logger.info(f"Sensor deactivated: {sensor_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to deactivate sensor {sensor_id}: {e}")
            return False

    # === STATUS METHODS ===

    def get_propulsion_status(self) -> Dict[str, Any]:
        """Get current propulsion status summary."""
        propulsion = self.ship_core.get_propulsion_status()
        return {
            "mode": self.current_mode.value,
            "main_drive": propulsion.main_drive_status,
            "main_drive_fuel_kg": propulsion.main_drive_fuel_kg,
            "rcs_thrusters": len([t for t in propulsion.rcs_status.values() if t["status"] == "ready"]),
            "total_rcs_fuel_kg": sum(t["fuel_kg"] for t in propulsion.rcs_status.values()),
        }

    def get_control_summary(self) -> Dict[str, Any]:
        """Get summary of all controllable systems."""
        hull = self.ship_core.get_hull_status()
        power = self.ship_core.get_power_status()
        sensors = self.ship_core.get_sensor_status()
        propulsion_status = self.get_propulsion_status()

        return {
            "ship_id": self.ship_core.get_id(),
            "operational_status": "OPERATIONAL" if hull.integrity > 80 else "DEGRADED",
            "propulsion": propulsion_status,
            "power_available_mw": power.reactor_output_mw,
            "sensors_active": len(sensors.active_sensors),
            "systems_controllable": [
                "main_drive",
                "rcs_thrusters",
                "power_distribution",
                "sensor_array",
                "life_support",
            ],
        }


# Example usage and testing
if __name__ == "__main__":
    try:
        # Test ship actuator control
        q_core_agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ship = ShipCore(base_path=q_core_agent_root)
        controller = ShipActuatorController(ship)

        print("=== SHIP ACTUATOR CONTROL TEST ===")
        print(f"Ship: {ship.get_id()}")
        print()

        # Test propulsion control
        print("1. PROPULSION TESTS:")
        print("   Setting main drive to 25% thrust...")
        success = controller.set_main_drive_thrust(25.0)
        print(f"   Result: {'SUCCESS' if success else 'FAILED'}")

        print("   Firing port RCS thruster...")
        success = controller.fire_rcs_thruster(ThrusterAxis.PORT, 50.0, 2.0)
        print(f"   Result: {'SUCCESS' if success else 'FAILED'}")

        print("   Executing complex maneuver...")
        thrust_vector = ThrustVector(x=30.0, y=-20.0, z=0.0)
        success = controller.execute_maneuver(thrust_vector, 3.0)
        print(f"   Result: {'SUCCESS' if success else 'FAILED'}")
        print()

        # Test power control
        print("2. POWER TESTS:")
        print("   Setting power allocation...")
        allocation = PowerAllocation(life_support=10.0, propulsion=20.0, sensors=8.0, qiki_core=4.0, shields=6.0)
        success = controller.set_power_allocation(allocation)
        print(f"   Result: {'SUCCESS' if success else 'FAILED'}")
        print()

        # Test sensor control
        print("3. SENSOR TESTS:")
        print("   Activating thermal scanner...")
        success = controller.activate_sensor("thermal_scanner")
        print(f"   Result: {'SUCCESS' if success else 'FAILED'}")

        print("   Deactivating quantum scanner...")
        success = controller.deactivate_sensor("quantum_scanner")
        print(f"   Result: {'SUCCESS' if success else 'FAILED'}")
        print()

        # Status reports
        print("4. STATUS REPORTS:")
        prop_status = controller.get_propulsion_status()
        print(f"   Propulsion: {prop_status}")

        control_summary = controller.get_control_summary()
        print(f"   Control Summary: {control_summary}")
        print()

        # Emergency stop test
        print("5. EMERGENCY PROCEDURES:")
        print("   Executing emergency stop...")
        success = controller.emergency_stop()
        print(f"   Result: {'SUCCESS' if success else 'FAILED'}")

        final_status = controller.get_propulsion_status()
        print(f"   Final propulsion mode: {final_status['mode']}")

    except Exception as e:
        print(f"Test failed: {e}")
        import traceback

        traceback.print_exc()
