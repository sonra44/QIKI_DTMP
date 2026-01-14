from typing import Dict, Any
import math

from qiki.services.q_sim_service.logger import logger
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import Vector3

from qiki.services.q_sim_service.core.mcqpu_telemetry import MCQPUTelemetry


class WorldModel:
    """
    Represents the simulated state of the bot and its immediate environment.
    This is the single source of truth for the simulation.
    """

    def __init__(self):
        self.position = Vector3(x=0.0, y=0.0, z=0.0)  # meters
        self.heading = 0.0  # degrees, 0 is +Y, 90 is +X
        self.roll_rad = 0.0
        self.pitch_rad = 0.0
        self.yaw_rad = math.radians(self.heading)
        self.battery_level = 100.0  # percent
        self.speed = 0.0  # meters/second
        # Additional avionics-friendly fields (simulation truth, not UI mocks).
        self.hull_integrity = 100.0  # percent
        self.radiation_usvh = 0.0  # microSievert per hour
        self.temp_external_c = -60.0  # deg C
        self.temp_core_c = 25.0  # deg C
        # Power/EPS model (simple, deterministic).
        self.power_bus_v = 28.0  # volts
        self.power_in_w = 30.0  # watts (e.g., solar)
        self.power_out_w = 60.0  # watts baseline load
        self.power_bus_a = self.power_out_w / self.power_bus_v
        self._battery_capacity_wh = 200.0
        self._base_power_in_w = 30.0
        self._base_power_out_w = 60.0
        self._motion_power_w_per_mps = 40.0
        self._mcqpu_power_w_at_100pct = 35.0
        self._radar_power_w = 18.0
        self._transponder_power_w = 6.0
        self._sim_time_s = 0.0

        # Virtual MCQPU utilization (simulation-truth).
        self._mcqpu = MCQPUTelemetry()
        self.cpu_usage = float(self._mcqpu.state.cpu_usage_pct)
        self.memory_usage = float(self._mcqpu.state.memory_usage_pct)
        self._radar_enabled = False
        self._sensor_queue_depth = 0
        self._actuator_queue_depth = 0
        self._transponder_active = False
        logger.info("WorldModel initialized.")

    def set_runtime_load_inputs(
        self,
        *,
        radar_enabled: bool,
        sensor_queue_depth: int,
        actuator_queue_depth: int,
        transponder_active: bool,
    ) -> None:
        self._radar_enabled = bool(radar_enabled)
        self._sensor_queue_depth = max(0, int(sensor_queue_depth))
        self._actuator_queue_depth = max(0, int(actuator_queue_depth))
        self._transponder_active = bool(transponder_active)

    def update(self, command: ActuatorCommand):
        """
        Applies an actuator command to the world model, changing its state.
        """
        logger.debug(
            f"Applying command to WorldModel: {command.command_type} for {command.actuator_id.value}"
        )

        if (
            command.actuator_id.value == "motor_left"
            or command.actuator_id.value == "motor_right"
        ):
            if command.command_type == "set_velocity_percent":
                # Simple model: average speed of motors
                # In a real model, this would involve differential drive kinematics
                self.speed = (command.int_value / 100.0) * 1.0  # Max speed 1.0 m/s
                logger.debug(f"WorldModel speed set to {self.speed} m/s")
            elif command.command_type == "rotate_degrees_per_sec":
                # Simple rotation
                self.heading = (self.heading + command.int_value) % 360
                logger.debug(f"WorldModel heading set to {self.heading} degrees")
        # Add more command types and their effects on the world model

    def step(self, delta_time: float):
        """
        Advances the simulation by a given delta_time.
        """
        self._sim_time_s += delta_time
        # Update position based on current speed and heading
        if self.speed > 0:
            # Convert heading to radians for trigonometric functions
            heading_rad = math.radians(self.heading)

            # Assuming 0 degrees is +Y (North), 90 degrees is +X (East)
            # dx = speed * sin(heading_rad) * delta_time
            # dy = speed * cos(heading_rad) * delta_time

            # Adjusting for typical Cartesian (0 deg is +X, 90 deg is +Y)
            # If 0 degrees is +Y (North), then 90 degrees is +X (East)
            # So, x-component is sin(angle), y-component is cos(angle)
            dx = self.speed * math.sin(heading_rad) * delta_time
            dy = self.speed * math.cos(heading_rad) * delta_time

            self.position.x += dx
            self.position.y += dy
            logger.debug(
                f"WorldModel moved to ({self.position.x:.2f}, {self.position.y:.2f})"
            )

        # Simple attitude model (6DOF): small oscillations + yaw follows heading.
        roll_amp = math.radians(2.0)
        pitch_amp = math.radians(1.5)
        self.roll_rad = roll_amp * math.sin(self._sim_time_s * 0.6)
        self.pitch_rad = pitch_amp * math.cos(self._sim_time_s * 0.4)
        self.yaw_rad = math.radians(self.heading)

        # MCQPU utilization (virtual hardware, simulation-truth; not OS metrics).
        self._mcqpu.update(
            dt=delta_time,
            speed=float(self.speed),
            radar_enabled=self._radar_enabled,
            sensor_queue_depth=self._sensor_queue_depth,
            actuator_queue_depth=self._actuator_queue_depth,
            transponder_active=self._transponder_active,
        )
        self.cpu_usage = float(self._mcqpu.state.cpu_usage_pct)
        self.memory_usage = float(self._mcqpu.state.memory_usage_pct)

        # Power/EPS: derive loads and update SoC from net power.
        self.power_in_w = self._base_power_in_w

        # Motion + avionics loads (still MVP, but deterministic and driven by simulation inputs).
        motion_out = abs(self.speed) * self._motion_power_w_per_mps
        mcqpu_out = (float(self.cpu_usage) / 100.0) * self._mcqpu_power_w_at_100pct
        radar_out = self._radar_power_w if self._radar_enabled else 0.0
        xpdr_out = self._transponder_power_w if self._transponder_active else 0.0
        self.power_out_w = self._base_power_out_w + motion_out + mcqpu_out + radar_out + xpdr_out
        self.power_bus_a = 0.0 if self.power_bus_v <= 0 else self.power_out_w / self.power_bus_v
        net_w = self.power_in_w - self.power_out_w
        delta_wh = net_w * delta_time / 3600.0
        delta_pct = (delta_wh / self._battery_capacity_wh) * 100.0
        self.battery_level = max(0.0, min(100.0, self.battery_level + delta_pct))

        # Simple thermal model: core warms up with movement and relaxes to external temperature.
        # Keep bounded to reasonable values for display.
        heat_in = abs(self.speed) * 0.8  # arbitrary units
        self.temp_core_c += (0.15 * heat_in - 0.02 * (self.temp_core_c - self.temp_external_c)) * delta_time
        self.temp_core_c = max(-120.0, min(160.0, self.temp_core_c))

    def get_state(self) -> Dict[str, Any]:
        """
        Returns the current state of the world model.
        """
        thermal_nodes = [
            {"id": "core", "temp_c": self.temp_core_c},
            {"id": "bus", "temp_c": self.temp_core_c - 5.0},
            {"id": "battery", "temp_c": self.temp_core_c - 10.0},
            {"id": "radiator", "temp_c": self.temp_external_c + (self.temp_core_c - self.temp_external_c) * 0.2},
        ]
        return {
            "position": {
                "x": self.position.x,
                "y": self.position.y,
                "z": self.position.z,
            },
            "heading": self.heading,
            "attitude": {
                "roll_rad": self.roll_rad,
                "pitch_rad": self.pitch_rad,
                "yaw_rad": self.yaw_rad,
            },
            "battery_level": self.battery_level,
            "speed": self.speed,
            "hull_integrity": self.hull_integrity,
            "radiation_usvh": self.radiation_usvh,
            "temp_external_c": self.temp_external_c,
            "temp_core_c": self.temp_core_c,
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "thermal": {
                "nodes": thermal_nodes,
            },
            "power": {
                "soc_pct": self.battery_level,
                "power_in_w": self.power_in_w,
                "power_out_w": self.power_out_w,
                "bus_v": self.power_bus_v,
                "bus_a": self.power_bus_a,
            },
        }
