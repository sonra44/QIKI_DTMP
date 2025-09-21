from typing import Dict, Any
import math

from qiki.services.q_sim_service.logger import logger
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import Vector3


class WorldModel:
    """
    Represents the simulated state of the bot and its immediate environment.
    This is the single source of truth for the simulation.
    """

    def __init__(self):
        self.position = Vector3(x=0.0, y=0.0, z=0.0)  # meters
        self.heading = 0.0  # degrees, 0 is +Y, 90 is +X
        self.battery_level = 100.0  # percent
        self.speed = 0.0  # meters/second
        logger.info("WorldModel initialized.")

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

        # Simple battery drain
        self.battery_level = max(0.0, self.battery_level - (0.1 * delta_time))

    def get_state(self) -> Dict[str, Any]:
        """
        Returns the current state of the world model.
        """
        return {
            "position": {
                "x": self.position.x,
                "y": self.position.y,
                "z": self.position.z,
            },
            "heading": self.heading,
            "battery_level": self.battery_level,
            "speed": self.speed,
        }
