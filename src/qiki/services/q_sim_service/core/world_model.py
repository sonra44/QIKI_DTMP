from typing import Any, Dict

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

    def __init__(self, *, bot_config: dict | None = None):
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
        # Power/EPS model (virtual hardware, simulation-truth).
        self.power_in_w = 30.0  # watts (e.g., solar)
        self.power_out_w = 60.0  # watts baseline load
        self.power_bus_v = 28.0  # volts (actual bus voltage after sag model)
        self.power_bus_a = self.power_out_w / self.power_bus_v

        # Power Supervisor / PDU state (no-mocks; derived from simulation).
        self.power_load_shedding = False
        self.power_shed_loads: list[str] = []
        self.power_shed_reasons: list[str] = []
        self.power_pdu_throttled = False
        self.power_throttled_loads: list[str] = []
        self.power_faults: list[str] = []

        self.radar_allowed = True
        self.transponder_allowed = True

        # Power Plane parameters (single source of truth: bot_config.json; defaults are safe).
        self._bus_v_nominal = 28.0
        self._bus_v_min = 22.0
        self._max_bus_a = 5.0
        self._eps_soc_shed_low_pct = 20.0
        self._eps_soc_shed_high_pct = 30.0
        self._soc_shed_state = False
        self._battery_capacity_wh = 200.0
        self._base_power_in_w = 30.0
        self._base_power_out_w = 60.0
        self._motion_power_w_per_mps = 40.0
        self._mcqpu_power_w_at_100pct = 35.0
        self._radar_power_w = 18.0
        self._transponder_power_w = 6.0

        # Supercaps (peak buffer) - virtual hardware.
        self._supercap_capacity_wh = 0.0
        self._supercap_energy_wh = 0.0
        self._supercap_max_charge_w = 0.0
        self._supercap_max_discharge_w = 0.0
        self.supercap_soc_pct = 0.0
        self.supercap_charge_w = 0.0
        self.supercap_discharge_w = 0.0

        # Apply runtime profile from bot_config (single SoT).
        self._apply_bot_config(bot_config)

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

    def _apply_bot_config(self, bot_config: dict | None) -> None:
        if not isinstance(bot_config, dict):
            return

        hw = bot_config.get("hardware_profile")
        if not isinstance(hw, dict):
            return

        if "power_capacity_wh" in hw:
            try:
                self._battery_capacity_wh = float(hw["power_capacity_wh"])
            except Exception:
                self.power_faults.append("BATTERY_CAPACITY_INVALID")
        else:
            self.power_faults.append("BATTERY_CAPACITY_MISSING")

        pp = hw.get("power_plane")
        if not isinstance(pp, dict):
            self.power_faults.append("POWER_PLANE_CONFIG_MISSING")
            return

        def f(key: str, default: float) -> float:
            try:
                return float(pp.get(key, default))
            except Exception:
                self.power_faults.append(f"POWER_PLANE_PARAM_INVALID:{key}")
                return default

        self._bus_v_nominal = f("bus_v_nominal", self._bus_v_nominal)
        self._bus_v_min = f("bus_v_min", self._bus_v_min)
        self._max_bus_a = f("max_bus_a", self._max_bus_a)

        self._base_power_in_w = f("base_power_in_w", self._base_power_in_w)
        self._base_power_out_w = f("base_power_out_w", self._base_power_out_w)
        self._motion_power_w_per_mps = f("motion_power_w_per_mps", self._motion_power_w_per_mps)
        self._mcqpu_power_w_at_100pct = f("mcqpu_power_w_at_100pct", self._mcqpu_power_w_at_100pct)
        self._radar_power_w = f("radar_power_w", self._radar_power_w)
        self._transponder_power_w = f("transponder_power_w", self._transponder_power_w)

        self._eps_soc_shed_low_pct = f("soc_shed_low_pct", self._eps_soc_shed_low_pct)
        self._eps_soc_shed_high_pct = f("soc_shed_high_pct", self._eps_soc_shed_high_pct)

        self._supercap_capacity_wh = f("supercap_capacity_wh", self._supercap_capacity_wh)
        self._supercap_max_charge_w = f("supercap_max_charge_w", self._supercap_max_charge_w)
        self._supercap_max_discharge_w = f("supercap_max_discharge_w", self._supercap_max_discharge_w)

        init_soc = f("supercap_soc_pct_init", 0.0)
        init_soc = max(0.0, min(100.0, init_soc))
        self._supercap_energy_wh = (init_soc / 100.0) * max(0.0, self._supercap_capacity_wh)
        self.supercap_soc_pct = init_soc

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

        # Power Plane (Supervisor + PDU + Supercaps) — deterministic, no-mocks.
        self.power_faults = [f for f in self.power_faults if f.endswith("_MISSING") or f.endswith("_INVALID") or f.startswith("POWER_PLANE_PARAM_INVALID")]
        self.power_shed_loads = []
        self.power_shed_reasons = []
        self.power_pdu_throttled = False
        self.power_throttled_loads = []
        self.supercap_charge_w = 0.0
        self.supercap_discharge_w = 0.0

        soc = max(0.0, min(100.0, float(self.battery_level)))
        if self._bus_v_nominal <= 0.0:
            self.power_faults.append("BUS_V_NOMINAL_INVALID")
        if self._bus_v_min < 0.0:
            self.power_faults.append("BUS_V_MIN_INVALID")
        bus_v_span = max(0.0, self._bus_v_nominal - self._bus_v_min)
        self.power_bus_v = max(0.0, self._bus_v_min + bus_v_span * (soc / 100.0))
        if self.power_bus_v <= 0.0:
            self.power_faults.append("BUS_V_ZERO")
        pdu_limit_w = max(0.0, self._max_bus_a) * max(0.0, self.power_bus_v)

        # SoC-based load shedding with hysteresis.
        if not self._soc_shed_state and soc <= self._eps_soc_shed_low_pct:
            self._soc_shed_state = True
        if self._soc_shed_state and soc >= self._eps_soc_shed_high_pct:
            self._soc_shed_state = False

        # Start with SoC-based allow flags.
        self.radar_allowed = not self._soc_shed_state
        self.transponder_allowed = not self._soc_shed_state
        if self._soc_shed_state:
            self.power_shed_loads.extend(["radar", "transponder"])
            self.power_shed_reasons.append("low_soc")

        # Motion + avionics loads (virtual hardware; driven by simulation inputs).
        motion_out = abs(self.speed) * self._motion_power_w_per_mps
        mcqpu_out = (float(self.cpu_usage) / 100.0) * self._mcqpu_power_w_at_100pct
        radar_out = self._radar_power_w if (self._radar_enabled and self.radar_allowed) else 0.0
        xpdr_out = (
            self._transponder_power_w
            if (self._transponder_active and self.transponder_allowed)
            else 0.0
        )

        power_out_wo_supercap = self._base_power_out_w + motion_out + mcqpu_out + radar_out + xpdr_out
        power_in = self._base_power_in_w

        # PDU: enforce max bus current by shedding non-critical loads, then throttling motion.
        if pdu_limit_w > 0.0 and power_out_wo_supercap > pdu_limit_w:
            if radar_out > 0.0:
                radar_out = 0.0
                self.radar_allowed = False
                self.power_shed_loads.append("radar")
                self.power_shed_reasons.append("pdu_overcurrent")
            if xpdr_out > 0.0:
                xpdr_out = 0.0
                self.transponder_allowed = False
                self.power_shed_loads.append("transponder")
                self.power_shed_reasons.append("pdu_overcurrent")

            power_out_wo_supercap = self._base_power_out_w + motion_out + mcqpu_out + radar_out + xpdr_out
            if power_out_wo_supercap > pdu_limit_w and motion_out > 0.0:
                excess = power_out_wo_supercap - pdu_limit_w
                reduced = min(excess, motion_out)
                motion_out -= reduced
                self.power_pdu_throttled = True
                self.power_throttled_loads.append("motion")
                power_out_wo_supercap = self._base_power_out_w + motion_out + mcqpu_out + radar_out + xpdr_out

            if power_out_wo_supercap > pdu_limit_w:
                self.power_faults.append("PDU_OVERCURRENT")

        # Supercaps: charge on surplus, discharge on deficit (peak buffer).
        self.power_in_w = max(0.0, float(power_in))
        self.power_out_w = max(0.0, float(power_out_wo_supercap))

        if self._supercap_capacity_wh > 0.0 and delta_time > 0.0:
            cap_left_wh = max(0.0, self._supercap_capacity_wh - self._supercap_energy_wh)
            max_charge_wh = (max(0.0, self._supercap_max_charge_w) * delta_time) / 3600.0
            max_discharge_wh = (max(0.0, self._supercap_max_discharge_w) * delta_time) / 3600.0

            net_w0 = self.power_in_w - self.power_out_w
            if net_w0 > 0.0 and cap_left_wh > 0.0 and max_charge_wh > 0.0:
                charge_wh = min(net_w0 * delta_time / 3600.0, cap_left_wh, max_charge_wh)
                charge_w = (charge_wh * 3600.0) / delta_time
                self._supercap_energy_wh += charge_wh
                self.supercap_charge_w = float(charge_w)
                self.power_out_w += float(charge_w)
            elif net_w0 < 0.0 and self._supercap_energy_wh > 0.0 and max_discharge_wh > 0.0:
                need_wh = (-net_w0 * delta_time) / 3600.0
                discharge_wh = min(need_wh, self._supercap_energy_wh, max_discharge_wh)
                discharge_w = (discharge_wh * 3600.0) / delta_time
                self._supercap_energy_wh -= discharge_wh
                self.supercap_discharge_w = float(discharge_w)
                self.power_in_w += float(discharge_w)

            self._supercap_energy_wh = max(0.0, min(self._supercap_capacity_wh, self._supercap_energy_wh))
            self.supercap_soc_pct = 0.0 if self._supercap_capacity_wh <= 0.0 else (self._supercap_energy_wh / self._supercap_capacity_wh) * 100.0
        else:
            self.supercap_soc_pct = 0.0

        # Finalize bus current and battery SoC update.
        self.power_bus_a = 0.0 if self.power_bus_v <= 0.0 else self.power_out_w / self.power_bus_v
        net_w = self.power_in_w - self.power_out_w
        if self._battery_capacity_wh > 0.0:
            delta_wh = net_w * delta_time / 3600.0
            delta_pct = (delta_wh / self._battery_capacity_wh) * 100.0
            self.battery_level = max(0.0, min(100.0, self.battery_level + delta_pct))
        else:
            self.battery_level = max(0.0, min(100.0, self.battery_level))
            self.power_faults.append("BATTERY_CAPACITY_ZERO")

        if self.battery_level <= 0.0 and net_w < 0.0:
            self.power_faults.append("BATTERY_EMPTY")

        # Dedup (stable order) before exposing to telemetry.
        self.power_shed_loads = list(dict.fromkeys(self.power_shed_loads))
        self.power_shed_reasons = list(dict.fromkeys(self.power_shed_reasons))
        self.power_throttled_loads = list(dict.fromkeys(self.power_throttled_loads))
        self.power_faults = list(dict.fromkeys(self.power_faults))

        self.power_load_shedding = bool(self.power_shed_loads)

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
                "load_shedding": bool(self.power_load_shedding),
                "shed_loads": list(self.power_shed_loads),
                "shed_reasons": list(self.power_shed_reasons),
                "pdu_limit_w": max(0.0, float(self._max_bus_a) * float(self.power_bus_v)),
                "pdu_throttled": bool(self.power_pdu_throttled),
                "throttled_loads": list(self.power_throttled_loads),
                "faults": list(self.power_faults),
                "supercap_soc_pct": float(self.supercap_soc_pct),
                "supercap_charge_w": float(self.supercap_charge_w),
                "supercap_discharge_w": float(self.supercap_discharge_w),
            },
        }
