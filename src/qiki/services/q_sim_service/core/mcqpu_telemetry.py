"""
MCQPU CPU/RAM Telemetry Logic (simulation-truth)
================================================
Virtual "hardware" utilization for the bot (not OS / VPS metrics).

Principles:
- Deterministic (no randomness)
- No-mocks UI: values must come from simulation truth
- Single source of truth: computed in WorldModel and exported via qiki.telemetry
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MCQPUTelemetryConfig:
    """
    Constants for MCQPU virtual hardware (MVP).

    Notes:
    - Capacity values are virtual "compute/memory units" used only for normalization.
    - With default capacities == 100, the demand formula effectively operates in percent units.
    """

    cpu_capacity_cu_per_sec: float = 100.0
    ram_capacity_mu: float = 100.0

    # Smoothing time constants (seconds)
    tau_cpu_sec: float = 2.0
    tau_ram_sec: float = 4.0

    # CPU demand coefficients (in virtual compute units)
    base_cpu_cu: float = 8.0
    motion_cpu_cu_per_unit_speed: float = 28.0
    motion_speed_max: float = 1.0
    radar_cpu_cu: float = 18.0
    queue_cpu_cu_max: float = 18.0
    sensor_queue_coeff: float = 0.9
    actuator_queue_coeff: float = 0.6
    transponder_cpu_cu: float = 3.0

    # RAM demand coefficients (in virtual memory units)
    base_ram_mu: float = 22.0
    sensor_buffer_mu_max: float = 35.0
    sensor_queue_coeff_ram: float = 1.2
    actuator_buffer_mu_max: float = 20.0
    actuator_queue_coeff_ram: float = 1.0
    radar_buffer_mu: float = 10.0


@dataclass
class MCQPUTelemetryState:
    cpu_usage_pct: float = 0.0  # [0..100]
    memory_usage_pct: float = 0.0  # [0..100]

    # Targets are kept for debugging/inspection (not exported by default).
    cpu_demand_target_pct: float = field(default=0.0, repr=False)
    mem_demand_target_pct: float = field(default=0.0, repr=False)


class MCQPUTelemetry:
    def __init__(self, config: MCQPUTelemetryConfig | None = None):
        self.config = config or MCQPUTelemetryConfig()
        self.state = MCQPUTelemetryState()

        # Initialize to the deterministic idle baseline (no UI "N/A" and no fake zeros).
        idle_cpu = self._compute_cpu_demand_pct(
            speed=0.0,
            radar_enabled=False,
            sensor_queue_depth=0,
            actuator_queue_depth=0,
            transponder_active=False,
        )
        idle_mem = self._compute_ram_demand_pct(
            radar_enabled=False,
            sensor_queue_depth=0,
            actuator_queue_depth=0,
        )
        self.state.cpu_demand_target_pct = idle_cpu
        self.state.mem_demand_target_pct = idle_mem
        self.state.cpu_usage_pct = idle_cpu
        self.state.memory_usage_pct = idle_mem

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    @staticmethod
    def _ema_alpha(dt: float, tau: float) -> float:
        """
        Exponential Moving Average (EMA) alpha coefficient.

        alpha = 1 - exp(-dt / tau)
        """
        if tau <= 0.0:
            return 1.0
        if dt <= 0.0:
            return 0.0
        return 1.0 - math.exp(-dt / tau)

    def _compute_cpu_demand_pct(
        self,
        *,
        speed: float,
        radar_enabled: bool,
        sensor_queue_depth: int,
        actuator_queue_depth: int,
        transponder_active: bool,
    ) -> float:
        base_cu = self.config.base_cpu_cu

        speed_norm = self._clamp(
            abs(float(speed)) / float(self.config.motion_speed_max),
            0.0,
            1.0,
        )
        motion_cu = self.config.motion_cpu_cu_per_unit_speed * speed_norm
        radar_cu = self.config.radar_cpu_cu if radar_enabled else 0.0

        queue_load = (
            self.config.sensor_queue_coeff * int(sensor_queue_depth)
            + self.config.actuator_queue_coeff * int(actuator_queue_depth)
        )
        queue_cu = min(self.config.queue_cpu_cu_max, queue_load)

        xpdr_cu = self.config.transponder_cpu_cu if transponder_active else 0.0

        demand_cu = base_cu + motion_cu + radar_cu + queue_cu + xpdr_cu
        demand_pct = (demand_cu / float(self.config.cpu_capacity_cu_per_sec)) * 100.0
        return self._clamp(demand_pct, 0.0, 100.0)

    def _compute_ram_demand_pct(
        self,
        *,
        radar_enabled: bool,
        sensor_queue_depth: int,
        actuator_queue_depth: int,
    ) -> float:
        base_mem = self.config.base_ram_mu
        sensor_buf = min(
            self.config.sensor_buffer_mu_max,
            self.config.sensor_queue_coeff_ram * int(sensor_queue_depth),
        )
        act_buf = min(
            self.config.actuator_buffer_mu_max,
            self.config.actuator_queue_coeff_ram * int(actuator_queue_depth),
        )
        radar_buf = self.config.radar_buffer_mu if radar_enabled else 0.0

        demand_mu = base_mem + sensor_buf + act_buf + radar_buf
        demand_pct = (demand_mu / float(self.config.ram_capacity_mu)) * 100.0
        return self._clamp(demand_pct, 0.0, 100.0)

    def update(
        self,
        *,
        dt: float,
        speed: float,
        radar_enabled: bool,
        sensor_queue_depth: int,
        actuator_queue_depth: int,
        transponder_active: bool,
    ) -> None:
        cpu_target = self._compute_cpu_demand_pct(
            speed=speed,
            radar_enabled=radar_enabled,
            sensor_queue_depth=sensor_queue_depth,
            actuator_queue_depth=actuator_queue_depth,
            transponder_active=transponder_active,
        )
        mem_target = self._compute_ram_demand_pct(
            radar_enabled=radar_enabled,
            sensor_queue_depth=sensor_queue_depth,
            actuator_queue_depth=actuator_queue_depth,
        )

        self.state.cpu_demand_target_pct = cpu_target
        self.state.mem_demand_target_pct = mem_target

        alpha_cpu = self._ema_alpha(float(dt), float(self.config.tau_cpu_sec))
        alpha_ram = self._ema_alpha(float(dt), float(self.config.tau_ram_sec))

        self.state.cpu_usage_pct = self._clamp(
            self.state.cpu_usage_pct + alpha_cpu * (cpu_target - self.state.cpu_usage_pct),
            0.0,
            100.0,
        )
        self.state.memory_usage_pct = self._clamp(
            self.state.memory_usage_pct
            + alpha_ram * (mem_target - self.state.memory_usage_pct),
            0.0,
            100.0,
        )

    def to_telemetry_dict(self) -> dict[str, float]:
        return {"cpu_usage": self.state.cpu_usage_pct, "memory_usage": self.state.memory_usage_pct}

