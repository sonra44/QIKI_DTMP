from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence

import math

from qiki.services.q_sim_service.logger import logger
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import Vector3

from qiki.services.q_sim_service.core.mcqpu_telemetry import MCQPUTelemetry
from qiki.shared.config.loaders import ThrusterConfig, load_thrusters_config


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
        # Thermal Plane (virtual hardware, no-mocks).
        self._thermal_enabled = False
        self._thermal_ambient_exchange_w_per_c = 0.0
        self._thermal_nodes_order: list[str] = []
        self._thermal_nodes: dict[str, dict[str, float]] = {}
        self._thermal_couplings: dict[str, list[tuple[str, float]]] = {}
        self._thermal_trip_state: dict[str, bool] = {}
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

        # Dock Power Bridge (virtual hardware).
        self.dock_connected = False
        self._dock_station_bus_v = 28.0
        self._dock_station_max_power_w = 0.0
        self._dock_current_limit_a = 0.0
        self._dock_soft_start_s = 0.0
        self._dock_since_s = 0.0
        self.dock_soft_start_pct = 0.0
        self.dock_power_w = 0.0
        self.dock_v = 0.0
        self.dock_a = 0.0
        self.dock_temp_c = self.temp_external_c

        # Docking Plane (mechanical) — minimal MVP (no-mocks).
        # Note: power bridge is still modeled under power.*; docking.* only reflects docking state/selection.
        self._docking_enabled = False
        self._docking_ports: list[str] = ["A", "B"]
        self._docking_default_port: str = "A"
        self.docking_port: str | None = None
        self.docking_state: str = "undocked"

        # Sensor Plane (internal telemetry sensors) — virtual hardware (no-mocks).
        # NOTE: do not duplicate values already canonical under power/thermal/docking; here we expose only sensor-layer
        # status and additional measurements when available.
        self._sensor_plane_enabled = False
        self._imu_enabled = False
        self._imu_ok: bool | None = None
        self._imu_roll_rate_rps: float | None = None
        self._imu_pitch_rate_rps: float | None = None
        self._imu_yaw_rate_rps: float | None = None

        self._radiation_enabled = False
        self._radiation_dose_total_usv: float | None = None

        self._proximity_enabled = False
        self._proximity_min_range_m: float | None = None
        self._proximity_contacts: int | None = None

        self._solar_enabled = False
        self._solar_illumination_pct: float | None = None

        self._star_tracker_enabled = False
        self._star_tracker_locked: bool | None = None
        self._star_tracker_attitude_err_deg: float | None = None

        self._magnetometer_enabled = False
        self._mag_field_ut: dict[str, float] | None = None

        # NBL Power Budgeter (virtual hardware).
        self.nbl_active = False
        self.nbl_allowed = False
        self.nbl_power_w = 0.0
        self.nbl_budget_w = 0.0
        self._nbl_max_power_w = 0.0
        self._nbl_soc_min_pct = 0.0
        self._nbl_core_temp_max_c = 0.0

        # Propulsion Plane (RCS) — virtual thrusters, no-mocks.
        self._rcs_enabled = False
        self._rcs_thrusters_path = "config/propulsion/thrusters.json"
        self._rcs_thrusters: list[ThrusterConfig] = []
        self._rcs_axis_groups: dict[str, list[int]] = {}
        self._rcs_axis_group_max_proj_n: dict[str, float] = {}

        self._rcs_propellant_kg = 0.0
        self._rcs_isp_s = 0.0
        self._rcs_power_w_at_100pct = 0.0
        self._rcs_heat_fraction_to_hull = 0.0
        self._rcs_pulse_window_s = 0.0
        self._rcs_ztt_torque_tol_nm = 0.0

        self._rcs_cmd_axis: str | None = None
        self._rcs_cmd_pct: float = 0.0
        self._rcs_cmd_time_left_s: float = 0.0

        self.rcs_active = False
        self.rcs_power_w = 0.0
        self.rcs_propellant_kg = 0.0
        self.rcs_throttled = False
        self._rcs_thruster_state: dict[int, dict[str, float | bool | str]] = {}
        self._rcs_net_force_n: list[float] = [0.0, 0.0, 0.0]
        self._rcs_net_torque_nm: list[float] = [0.0, 0.0, 0.0]
        self._rcs_last_axis: str | None = None

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
            pp = {}

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

        # Dock Power Bridge defaults / scenario.
        self.dock_connected = bool(pp.get("dock_connected_init", False))
        self._dock_station_bus_v = f("dock_station_bus_v", self._dock_station_bus_v)
        self._dock_station_max_power_w = f("dock_station_max_power_w", self._dock_station_max_power_w)
        self._dock_current_limit_a = f("dock_current_limit_a", self._dock_current_limit_a)
        self._dock_soft_start_s = f("dock_soft_start_s", self._dock_soft_start_s)
        self.dock_temp_c = f("dock_temp_c_init", float(self.temp_external_c))
        self._dock_since_s = 0.0
        self.dock_soft_start_pct = 0.0

        # Docking Plane params (single source of truth: bot_config.json).
        dp = hw.get("docking_plane")
        if not isinstance(dp, dict):
            dp = {}
        self._docking_enabled = bool(dp.get("enabled", False))
        ports = dp.get("ports")
        if isinstance(ports, list):
            cleaned: list[str] = []
            for raw in ports:
                token = str(raw or "").strip()
                if token:
                    cleaned.append(token)
            if cleaned:
                self._docking_ports = cleaned
        default_port = str(dp.get("default_port") or "").strip()
        if default_port and default_port in self._docking_ports:
            self._docking_default_port = default_port
        else:
            self._docking_default_port = self._docking_ports[0] if self._docking_ports else "A"

        if not self._docking_enabled:
            self.docking_port = None
            self.docking_state = "disabled"
        else:
            self.docking_port = self._docking_default_port
            self.docking_state = "docked" if bool(self.dock_connected) else "undocked"

        # Sensor Plane params (single source of truth: bot_config.json).
        sp = hw.get("sensor_plane")
        if not isinstance(sp, dict):
            sp = {}
        self._sensor_plane_enabled = bool(sp.get("enabled", False))

        def _sub_enabled(key: str) -> bool:
            if not self._sensor_plane_enabled:
                return False
            sub = sp.get(key)
            if isinstance(sub, dict):
                return bool(sub.get("enabled", False))
            return False

        self._imu_enabled = _sub_enabled("imu")
        self._radiation_enabled = _sub_enabled("radiation")
        self._proximity_enabled = _sub_enabled("proximity")
        self._solar_enabled = _sub_enabled("solar")
        self._star_tracker_enabled = _sub_enabled("star_tracker")
        self._magnetometer_enabled = _sub_enabled("magnetometer")

        # Radiation dose integrator starts at 0 when enabled.
        self._radiation_dose_total_usv = 0.0 if self._radiation_enabled else None
        # Sensor Plane limits/status config (single source of truth: bot_config.json).
        # No-mocks: if limits are not configured, we mark status as NA (not evaluated).
        self._radiation_warn_usvh = None
        self._radiation_crit_usvh = None
        try:
            rad_cfg = sp.get("radiation") if isinstance(sp.get("radiation"), dict) else {}
            limits = rad_cfg.get("limits") if isinstance(rad_cfg.get("limits"), dict) else {}
            warn = limits.get("warn_usvh")
            crit = limits.get("crit_usvh")
            self._radiation_warn_usvh = float(warn) if warn is not None else None
            self._radiation_crit_usvh = float(crit) if crit is not None else None
        except Exception:
            self._radiation_warn_usvh = None
            self._radiation_crit_usvh = None

        # Optional scenario-provided initial values (still simulation-truth, not OS metrics).
        prox = sp.get("proximity") if isinstance(sp.get("proximity"), dict) else {}
        try:
            self._proximity_min_range_m = (
                float(prox.get("min_range_m_init")) if self._proximity_enabled and prox.get("min_range_m_init") is not None else None
            )
        except Exception:
            self._proximity_min_range_m = None
        try:
            self._proximity_contacts = (
                int(prox.get("contacts_init")) if self._proximity_enabled and prox.get("contacts_init") is not None else None
            )
        except Exception:
            self._proximity_contacts = None

        solar = sp.get("solar") if isinstance(sp.get("solar"), dict) else {}
        try:
            self._solar_illumination_pct = (
                float(solar.get("illumination_pct_init")) if self._solar_enabled and solar.get("illumination_pct_init") is not None else None
            )
        except Exception:
            self._solar_illumination_pct = None

        st = sp.get("star_tracker") if isinstance(sp.get("star_tracker"), dict) else {}
        if self._star_tracker_enabled:
            locked = st.get("locked_init")
            self._star_tracker_locked = None if locked is None else bool(locked)
            try:
                self._star_tracker_attitude_err_deg = (
                    float(st.get("attitude_err_deg_init")) if st.get("attitude_err_deg_init") is not None else None
                )
            except Exception:
                self._star_tracker_attitude_err_deg = None
        else:
            self._star_tracker_locked = None
            self._star_tracker_attitude_err_deg = None

        mag = sp.get("magnetometer") if isinstance(sp.get("magnetometer"), dict) else {}
        field_init = mag.get("field_ut_init") if isinstance(mag.get("field_ut_init"), dict) else None
        if self._magnetometer_enabled and isinstance(field_init, dict):
            try:
                self._mag_field_ut = {
                    "x": float(field_init.get("x", 0.0)),
                    "y": float(field_init.get("y", 0.0)),
                    "z": float(field_init.get("z", 0.0)),
                }
            except Exception:
                self._mag_field_ut = None
        else:
            self._mag_field_ut = None

        # NBL budgeter (scenario + limits).
        self.nbl_active = bool(pp.get("nbl_active_init", False))
        self._nbl_max_power_w = f("nbl_max_power_w", self._nbl_max_power_w)
        self._nbl_soc_min_pct = f("nbl_soc_min_pct", self._nbl_soc_min_pct)
        self._nbl_core_temp_max_c = f("nbl_core_temp_max_c", self._nbl_core_temp_max_c)
        self.nbl_allowed = False
        self.nbl_power_w = 0.0
        self.nbl_budget_w = 0.0

        # Thermal Plane parameters (single source of truth: bot_config.json).
        tp = hw.get("thermal_plane")
        if not isinstance(tp, dict):
            tp = {}

        self._thermal_enabled = bool(tp.get("enabled", False))
        try:
            self._thermal_ambient_exchange_w_per_c = float(tp.get("ambient_exchange_w_per_c", 0.0))
        except Exception:
            self._thermal_ambient_exchange_w_per_c = 0.0

        nodes = tp.get("nodes")
        if not isinstance(nodes, list):
            nodes = []

        self._thermal_nodes_order = []
        self._thermal_nodes = {}
        self._thermal_trip_state = {}
        for raw in nodes:
            if not isinstance(raw, dict):
                continue
            node_id = str(raw.get("id") or "").strip()
            if not node_id:
                continue
            if node_id in self._thermal_nodes:
                continue
            try:
                cap = float(raw.get("heat_capacity_j_per_c", 0.0))
            except Exception:
                cap = 0.0
            try:
                cool = float(raw.get("cooling_w_per_c", 0.0))
            except Exception:
                cool = 0.0
            try:
                t_init = float(raw.get("t_init_c", float(self.temp_external_c)))
            except Exception:
                t_init = float(self.temp_external_c)
            try:
                t_trip = float(raw.get("t_max_c", raw.get("t_trip_c", 0.0)))
            except Exception:
                t_trip = 0.0
            try:
                t_hys = float(raw.get("t_hysteresis_c", 0.0))
            except Exception:
                t_hys = 0.0

            cap = max(1.0, cap)
            cool = max(0.0, cool)
            t_init = max(-120.0, min(160.0, t_init))
            t_trip = float(t_trip)
            t_hys = max(0.0, t_hys)

            self._thermal_nodes_order.append(node_id)
            self._thermal_nodes[node_id] = {
                "temp_c": float(t_init),
                "cap_j_per_c": float(cap),
                "cool_w_per_c": float(cool),
                "trip_c": float(t_trip),
                "hys_c": float(t_hys),
            }
            self._thermal_trip_state[node_id] = False

        couplings = tp.get("couplings")
        if not isinstance(couplings, list):
            couplings = []
        self._thermal_couplings = {nid: [] for nid in self._thermal_nodes_order}
        for raw in couplings:
            if not isinstance(raw, dict):
                continue
            a = str(raw.get("a") or "").strip()
            b = str(raw.get("b") or "").strip()
            if not a or not b:
                continue
            if a not in self._thermal_nodes or b not in self._thermal_nodes:
                continue
            try:
                k = float(raw.get("k_w_per_c", 0.0))
            except Exception:
                k = 0.0
            k = max(0.0, k)
            if k <= 0.0:
                continue
            self._thermal_couplings.setdefault(a, []).append((b, k))
            self._thermal_couplings.setdefault(b, []).append((a, k))

        # Seed derived temps from nodes when available.
        if "core" in self._thermal_nodes:
            self.temp_core_c = float(self._thermal_nodes["core"]["temp_c"])
        if "dock_bridge" in self._thermal_nodes:
            self.dock_temp_c = float(self._thermal_nodes["dock_bridge"]["temp_c"])

        # Propulsion Plane (RCS) params (single SoT).
        pr = hw.get("propulsion_plane")
        if isinstance(pr, dict):
            self._rcs_enabled = bool(pr.get("enabled", False))
            self._rcs_thrusters_path = str(pr.get("thrusters_path", self._rcs_thrusters_path))
            try:
                self._rcs_propellant_kg = max(0.0, float(pr.get("propellant_kg_init", 0.0)))
            except Exception:
                self._rcs_propellant_kg = 0.0
            try:
                self._rcs_isp_s = max(0.0, float(pr.get("isp_s", 0.0)))
            except Exception:
                self._rcs_isp_s = 0.0
            try:
                self._rcs_power_w_at_100pct = max(0.0, float(pr.get("rcs_power_w_at_100pct", 0.0)))
            except Exception:
                self._rcs_power_w_at_100pct = 0.0
            try:
                self._rcs_heat_fraction_to_hull = max(
                    0.0, min(1.0, float(pr.get("heat_fraction_to_hull", 0.0)))
                )
            except Exception:
                self._rcs_heat_fraction_to_hull = 0.0
            try:
                self._rcs_pulse_window_s = max(0.0, float(pr.get("pulse_window_s", 0.0)))
            except Exception:
                self._rcs_pulse_window_s = 0.0
            try:
                self._rcs_ztt_torque_tol_nm = max(0.0, float(pr.get("ztt_torque_tol_nm", 0.0)))
            except Exception:
                self._rcs_ztt_torque_tol_nm = 0.0
        else:
            self._rcs_enabled = False

        # Load thrusters and precompute ZTT groups (no-mocks: if missing, leave unavailable).
        self._rcs_thrusters = []
        self._rcs_axis_groups = {}
        self._rcs_axis_group_max_proj_n = {}
        if self._rcs_enabled:
            self._rcs_load_thrusters()
            self._rcs_precompute_axis_groups()
        self.rcs_propellant_kg = float(self._rcs_propellant_kg)

    def _thermal_step(self, delta_time: float) -> None:
        if not self._thermal_enabled:
            return
        if not self._thermal_nodes_order:
            return
        dt = max(0.0, float(delta_time))
        if dt <= 0.0:
            return

        amb = float(self.temp_external_c)

        # Heat sources (W) derived from simulation state (no mocks).
        q: dict[str, float] = {nid: 0.0 for nid in self._thermal_nodes_order}
        cpu_frac = max(0.0, min(1.0, float(self.cpu_usage) / 100.0))
        mcqpu_w = cpu_frac * float(self._mcqpu_power_w_at_100pct)
        if "core" in q:
            q["core"] += 0.8 * mcqpu_w
            q["core"] += 0.7 * float(self.nbl_power_w)
        if "pdu" in q:
            q["pdu"] += 0.02 * float(self.power_out_w)
            q["pdu"] += 0.4 * (abs(float(self.power_bus_a)) ** 2)
        if "supercap" in q:
            q["supercap"] += 0.03 * (float(self.supercap_charge_w) + float(self.supercap_discharge_w))
        if "dock_bridge" in q:
            q["dock_bridge"] += 0.25 * (abs(float(self.dock_a)) ** 2)
        if "battery" in q:
            q["battery"] += 0.01 * abs(float(self.power_in_w) - float(self.power_out_w))
        if "hull" in q and self.rcs_power_w > 0.0:
            q["hull"] += float(self._rcs_heat_fraction_to_hull) * float(self.rcs_power_w)

        # Integrate temperatures (explicit Euler) on a thermal network.
        prev_t = {nid: float(self._thermal_nodes[nid]["temp_c"]) for nid in self._thermal_nodes_order}
        next_t: dict[str, float] = {}
        for nid in self._thermal_nodes_order:
            node = self._thermal_nodes[nid]
            t = prev_t[nid]
            cap = max(1.0, float(node["cap_j_per_c"]))
            cool = max(0.0, float(node["cool_w_per_c"])) + max(0.0, float(self._thermal_ambient_exchange_w_per_c))
            net_w = float(q.get(nid, 0.0))
            net_w -= cool * (t - amb)
            for other_id, k in self._thermal_couplings.get(nid, []):
                other_t = prev_t.get(other_id)
                if other_t is None:
                    continue
                net_w -= float(k) * (t - other_t)
            dT = (net_w / cap) * dt
            t2 = max(-120.0, min(160.0, t + dT))
            next_t[nid] = float(t2)

        for nid, t2 in next_t.items():
            self._thermal_nodes[nid]["temp_c"] = float(t2)

        # Update trip states with hysteresis and surface in faults list (no mocks).
        for nid in self._thermal_nodes_order:
            trip = float(self._thermal_nodes[nid].get("trip_c", 0.0))
            hys = float(self._thermal_nodes[nid].get("hys_c", 0.0))
            if trip <= 0.0:
                continue
            t = float(self._thermal_nodes[nid]["temp_c"])
            state = bool(self._thermal_trip_state.get(nid, False))
            if (not state) and t >= trip:
                state = True
            if state and t <= (trip - hys):
                state = False
            self._thermal_trip_state[nid] = state
            if state:
                self.power_faults.append(f"THERMAL_TRIP:{nid}")

        # Keep legacy top-level temps consistent with nodes when present.
        if "core" in self._thermal_nodes:
            self.temp_core_c = float(self._thermal_nodes["core"]["temp_c"])
        if "dock_bridge" in self._thermal_nodes:
            self.dock_temp_c = float(self._thermal_nodes["dock_bridge"]["temp_c"])

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

    def set_dock_connected(self, connected: bool) -> None:
        connected = bool(connected)
        if connected == bool(getattr(self, "dock_connected", False)):
            return
        self.dock_connected = connected
        if self._docking_enabled:
            self.docking_state = "docked" if connected else "undocked"
        if not connected:
            # Reset soft-start state when disconnecting.
            self._dock_since_s = 0.0
            self.dock_soft_start_pct = 0.0
            self.dock_power_w = 0.0
            self.dock_v = 0.0
            self.dock_a = 0.0
        else:
            # Restart soft-start ramp on a fresh connect.
            self._dock_since_s = 0.0
            self.dock_soft_start_pct = 0.0

    def set_docking_port(self, port: str | None) -> bool:
        if not self._docking_enabled:
            return False
        token = str(port or "").strip()
        if not token:
            self.docking_port = self._docking_default_port
            return True
        if token not in self._docking_ports:
            return False
        self.docking_port = token
        return True

    def set_nbl_active(self, active: bool) -> None:
        self.nbl_active = bool(active)

    def set_nbl_max_power_w(self, max_power_w: float) -> None:
        try:
            value = float(max_power_w)
        except Exception:
            return
        self._nbl_max_power_w = max(0.0, value)

    def set_rcs_command(self, axis: str | None, pct: float, duration_s: float) -> bool:
        """
        Set an RCS axis command directly (for NATS COMMANDS_CONTROL path).

        No-mocks: this only mutates simulation state; if RCS is disabled/unavailable,
        returns False (caller should report failure).
        """
        if not self._rcs_enabled:
            return False

        if axis is None:
            self._rcs_cmd_axis = None
            self._rcs_cmd_pct = 0.0
            self._rcs_cmd_time_left_s = 0.0
            return True

        axis_norm = (axis or "").strip().lower()
        if axis_norm not in {"forward", "aft", "port", "starboard", "up", "down"}:
            return False

        try:
            pct_f = float(pct)
            dur_f = float(duration_s)
        except Exception:
            return False

        pct_f = max(0.0, min(100.0, pct_f))
        # Safety: treat non-positive durations as "immediate stop" to avoid indefinite firing.
        if dur_f <= 0.0 or pct_f <= 0.0:
            self._rcs_cmd_axis = None
            self._rcs_cmd_pct = 0.0
            self._rcs_cmd_time_left_s = 0.0
            return True

        self._rcs_cmd_axis = axis_norm
        self._rcs_cmd_pct = pct_f
        self._rcs_cmd_time_left_s = max(0.0, dur_f)
        logger.info(f"RCS control command: {axis_norm} {pct_f:.1f}% for {dur_f:.2f}s")
        return True

    def update(self, command: ActuatorCommand):
        """
        Applies an actuator command to the world model, changing its state.
        """
        logger.debug(
            f"Applying command to WorldModel: {command.command_type} for {command.actuator_id.value}"
        )

        actuator_id = getattr(getattr(command, "actuator_id", None), "value", "")
        cmd_type = getattr(command, "command_type", None)
        which_value = None
        try:
            which_value = command.WhichOneof("command_value")
        except Exception:
            which_value = None

        def _as_pct() -> float | None:
            if which_value == "int_value":
                try:
                    return float(command.int_value)
                except Exception:
                    return None
            if which_value == "float_value":
                try:
                    return float(command.float_value)
                except Exception:
                    return None
            return None

        if actuator_id in ("motor_left", "motor_right"):
            if cmd_type in (ActuatorCommand.CommandType.SET_VELOCITY, "set_velocity_percent"):
                pct = _as_pct()
                if pct is None:
                    return
                pct = max(0.0, min(100.0, float(pct)))
                # Simple model: average speed of motors; max 1.0 m/s.
                self.speed = (pct / 100.0) * 1.0
                logger.debug(f"WorldModel speed set to {self.speed} m/s")
                return
            if cmd_type in (ActuatorCommand.CommandType.ROTATE, "rotate_degrees_per_sec"):
                pct = _as_pct()
                if pct is None:
                    return
                self.heading = (self.heading + float(pct)) % 360.0
                logger.debug(f"WorldModel heading set to {self.heading} degrees")
                return

        # RCS axis commands (virtual hardware; no-mocks).
        axis_map = {
            "rcs_forward": "forward",
            "rcs_aft": "aft",
            "rcs_port": "port",
            "rcs_starboard": "starboard",
            "rcs_up": "up",
            "rcs_down": "down",
        }
        axis = axis_map.get(str(actuator_id))
        if axis and cmd_type == ActuatorCommand.CommandType.SET_VELOCITY:
            pct = _as_pct()
            if pct is None:
                return
            pct = max(0.0, min(100.0, float(pct)))
            timeout_ms = int(getattr(command, "timeout_ms", 0) or 0)
            duration_s = max(0.0, float(timeout_ms) / 1000.0) if timeout_ms > 0 else 0.0
            self._rcs_cmd_axis = axis
            self._rcs_cmd_pct = pct
            self._rcs_cmd_time_left_s = duration_s
            logger.info(f"RCS command: {axis} {pct:.1f}% for {duration_s:.2f}s")
            return

        # Unknown / unsupported command types are ignored safely.
        return

    def step(self, delta_time: float):
        """
        Advances the simulation by a given delta_time.
        """
        self._sim_time_s += delta_time

        # Sensor Plane: integrate radiation dose (simulation-truth; no OS metrics).
        if self._radiation_enabled and self._radiation_dose_total_usv is not None:
            dt = max(0.0, float(delta_time))
            usvh = max(0.0, float(self.radiation_usvh))
            self._radiation_dose_total_usv += (usvh / 3600.0) * dt
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
        prev_roll = float(self.roll_rad)
        prev_pitch = float(self.pitch_rad)
        prev_yaw = float(self.yaw_rad)
        roll_amp = math.radians(2.0)
        pitch_amp = math.radians(1.5)
        self.roll_rad = roll_amp * math.sin(self._sim_time_s * 0.6)
        self.pitch_rad = pitch_amp * math.cos(self._sim_time_s * 0.4)
        self.yaw_rad = math.radians(self.heading)

        # IMU rates (derivatives) — only when IMU is enabled.
        if self._imu_enabled and float(delta_time) > 0.0:
            dt = float(delta_time)
            self._imu_roll_rate_rps = (float(self.roll_rad) - prev_roll) / dt
            self._imu_pitch_rate_rps = (float(self.pitch_rad) - prev_pitch) / dt
            self._imu_yaw_rate_rps = (float(self.yaw_rad) - prev_yaw) / dt
            self._imu_ok = True
        elif self._imu_enabled:
            self._imu_roll_rate_rps = None
            self._imu_pitch_rate_rps = None
            self._imu_yaw_rate_rps = None
            self._imu_ok = None
        else:
            self._imu_ok = None
            self._imu_roll_rate_rps = None
            self._imu_pitch_rate_rps = None
            self._imu_yaw_rate_rps = None

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
        self.dock_power_w = 0.0
        self.dock_v = 0.0
        self.dock_a = 0.0
        self.dock_soft_start_pct = 0.0
        self.nbl_allowed = False
        self.nbl_power_w = 0.0
        self.nbl_budget_w = 0.0

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

        # Thermal-based shedding (hysteresis state is maintained by thermal plane).
        if bool(self._thermal_trip_state.get("pdu")):
            self.radar_allowed = False
            self.transponder_allowed = False
            self.power_shed_loads.extend(["radar", "transponder"])
            self.power_shed_reasons.append("thermal_overheat")
        if bool(self._thermal_trip_state.get("core")):
            self.power_shed_loads.append("nbl")
            self.power_shed_reasons.append("thermal_overheat")

        # Motion + avionics loads (virtual hardware; driven by simulation inputs).
        motion_out = abs(self.speed) * self._motion_power_w_per_mps
        mcqpu_out = (float(self.cpu_usage) / 100.0) * self._mcqpu_power_w_at_100pct
        radar_out = self._radar_power_w if (self._radar_enabled and self.radar_allowed) else 0.0
        xpdr_out = (
            self._transponder_power_w
            if (self._transponder_active and self.transponder_allowed)
            else 0.0
        )
        # RCS (thrusters) electrical load — simulation truth.
        rcs_out = self._rcs_step(delta_time)

        # NBL: non-critical burst link power, constrained by SoC and thermal.
        nbl_allowed = bool(
            self.nbl_active
            and soc >= float(self._nbl_soc_min_pct)
            and float(self.temp_core_c) <= float(self._nbl_core_temp_max_c)
            and not bool(self._thermal_trip_state.get("core"))
            and not bool(self._thermal_trip_state.get("pdu"))
        )
        self.nbl_allowed = bool(nbl_allowed)
        self.nbl_budget_w = max(0.0, float(self._nbl_max_power_w)) if self.nbl_allowed else 0.0
        nbl_out = float(self.nbl_budget_w) if self.nbl_active and self.nbl_allowed else 0.0
        if self.nbl_active and not self.nbl_allowed:
            self.power_shed_loads.append("nbl")
            if bool(self._thermal_trip_state.get("core")) or bool(self._thermal_trip_state.get("pdu")):
                self.power_shed_reasons.append("thermal_overheat")
            else:
                self.power_shed_reasons.append("nbl_budget")

        power_out_wo_supercap = (
            self._base_power_out_w
            + motion_out
            + mcqpu_out
            + radar_out
            + xpdr_out
            + nbl_out
            + rcs_out
        )
        power_in = self._base_power_in_w

        # Dock Power Bridge: adds external power when connected (soft start + limits).
        if self.dock_connected:
            self._dock_since_s += max(0.0, float(delta_time))
            denom = max(0.001, float(self._dock_soft_start_s))
            self.dock_soft_start_pct = max(0.0, min(100.0, (self._dock_since_s / denom) * 100.0))
            ramp = self.dock_soft_start_pct / 100.0

            station_v = max(0.0, float(self._dock_station_bus_v))
            station_p_limit = max(0.0, float(self._dock_station_max_power_w))
            current_p_limit = max(0.0, float(self._dock_current_limit_a)) * station_v
            avail_w = min(station_p_limit, current_p_limit) if station_p_limit > 0.0 else current_p_limit
            dock_w = max(0.0, avail_w) * ramp

            self.dock_power_w = float(dock_w)
            self.dock_v = float(station_v)
            self.dock_a = 0.0 if station_v <= 0.0 else float(dock_w) / station_v
            power_in += float(dock_w)

        else:
            self._dock_since_s = 0.0

        # PDU: enforce max bus current by shedding non-critical loads, then throttling motion.
        if pdu_limit_w > 0.0 and power_out_wo_supercap > pdu_limit_w:
            if nbl_out > 0.0:
                nbl_out = 0.0
                self.nbl_allowed = False
                self.power_shed_loads.append("nbl")
                self.power_shed_reasons.append("pdu_overcurrent")
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

            power_out_wo_supercap = (
                self._base_power_out_w
                + motion_out
                + mcqpu_out
                + radar_out
                + xpdr_out
                + nbl_out
                + rcs_out
            )
            if power_out_wo_supercap > pdu_limit_w and motion_out > 0.0:
                excess = power_out_wo_supercap - pdu_limit_w
                reduced = min(excess, motion_out)
                motion_out -= reduced
                self.power_pdu_throttled = True
                self.power_throttled_loads.append("motion")
                power_out_wo_supercap = (
                    self._base_power_out_w
                    + motion_out
                    + mcqpu_out
                    + radar_out
                    + xpdr_out
                    + nbl_out
                    + rcs_out
                )

            # If still overcurrent, throttle RCS (virtual thrusters) before declaring fault.
            if power_out_wo_supercap > pdu_limit_w and rcs_out > 0.0:
                excess = power_out_wo_supercap - pdu_limit_w
                reduced = min(excess, rcs_out)
                if reduced > 0.0:
                    before = max(1e-9, float(rcs_out))
                    rcs_out -= reduced
                    ratio = max(0.0, min(1.0, float(rcs_out) / before))
                    self._rcs_apply_throttle_ratio(ratio, reason="pdu_overcurrent")
                    self.power_pdu_throttled = True
                    self.power_throttled_loads.append("rcs")
                    power_out_wo_supercap = (
                        self._base_power_out_w
                        + motion_out
                        + mcqpu_out
                        + radar_out
                        + xpdr_out
                        + nbl_out
                        + rcs_out
                    )

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

        # Finalize NBL telemetry values (post-PDU / post-shedding).
        self.nbl_power_w = float(nbl_out)
        if self.nbl_power_w <= 0.0:
            self.nbl_allowed = False
        # Finalize RCS telemetry values.
        self.rcs_power_w = float(rcs_out)
        # Thermal Plane (no-mocks): temperatures derived from a thermal node network.
        self._thermal_step(delta_time)
        # Thermal plane may append faults; keep stable order.
        self.power_faults = list(dict.fromkeys(self.power_faults))

    def _repo_root(self) -> Path:
        # /.../src/qiki/services/q_sim_service/core/world_model.py -> repo root is 5 parents up.
        return Path(__file__).resolve().parents[5]

    @staticmethod
    def _dot(a: Sequence[float], b: Sequence[float]) -> float:
        return float(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])

    @staticmethod
    def _norm(v: Sequence[float]) -> float:
        return math.sqrt(float(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]))

    @staticmethod
    def _cross(a: Sequence[float], b: Sequence[float]) -> list[float]:
        return [
            float(a[1] * b[2] - a[2] * b[1]),
            float(a[2] * b[0] - a[0] * b[2]),
            float(a[0] * b[1] - a[1] * b[0]),
        ]

    def _rcs_load_thrusters(self) -> None:
        path = Path(self._rcs_thrusters_path)
        if not path.is_absolute():
            path = self._repo_root() / path
        try:
            thrusters = load_thrusters_config(path)
        except Exception as exc:
            logger.warning(f"RCS thrusters config unavailable ({path}): {exc}")
            self._rcs_thrusters = []
            return
        self._rcs_thrusters = list(thrusters)

    def _rcs_precompute_axis_groups(self) -> None:
        self._rcs_axis_groups = {}
        self._rcs_axis_group_max_proj_n = {}
        if not self._rcs_thrusters:
            return

        axes: dict[str, list[float]] = {
            "forward": [1.0, 0.0, 0.0],
            "aft": [-1.0, 0.0, 0.0],
            "port": [0.0, 1.0, 0.0],
            "starboard": [0.0, -1.0, 0.0],
            "up": [0.0, 0.0, 1.0],
            "down": [0.0, 0.0, -1.0],
        }

        forces: list[list[float]] = []
        torques: list[list[float]] = []
        for t in self._rcs_thrusters:
            d = t.direction.as_list()
            pos = t.position_m.as_list()
            f = [float(d[0]) * float(t.f_max_newton), float(d[1]) * float(t.f_max_newton), float(d[2]) * float(t.f_max_newton)]
            forces.append(f)
            torques.append(self._cross(pos, f))

        idxs = list(range(len(self._rcs_thrusters)))
        torque_tol = float(self._rcs_ztt_torque_tol_nm)
        # Search 2- and 4-thruster groups; deterministic and fast for N=16.
        candidates: list[tuple[list[int], list[float], list[float]]] = []
        for k in (2, 4):
            for combo in combinations(idxs, k):
                net_f = [0.0, 0.0, 0.0]
                net_tau = [0.0, 0.0, 0.0]
                for i in combo:
                    f = forces[i]
                    tau = torques[i]
                    net_f[0] += f[0]; net_f[1] += f[1]; net_f[2] += f[2]
                    net_tau[0] += tau[0]; net_tau[1] += tau[1]; net_tau[2] += tau[2]
                candidates.append((list(combo), net_f, net_tau))

        for axis_name, axis_vec in axes.items():
            best_combo: list[int] | None = None
            best_proj = 0.0
            best_score = -1e18
            for combo, net_f, net_tau in candidates:
                proj = self._dot(net_f, axis_vec)
                if proj <= 0.0:
                    continue
                lateral = [net_f[0] - proj * axis_vec[0], net_f[1] - proj * axis_vec[1], net_f[2] - proj * axis_vec[2]]
                lateral_mag = self._norm(lateral)
                tau_mag = self._norm(net_tau)
                # Favor near-zero torque, but keep deterministic best-effort if none meet tol.
                over = max(0.0, tau_mag - torque_tol)
                score = float(proj) - 0.05 * float(lateral_mag) - 0.5 * float(over)
                if score > best_score:
                    best_score = score
                    best_combo = combo
                    best_proj = float(proj)
            if best_combo is None:
                continue
            self._rcs_axis_groups[axis_name] = list(best_combo)
            self._rcs_axis_group_max_proj_n[axis_name] = float(best_proj)

    def _rcs_step(self, delta_time: float) -> float:
        # Reset exposed state.
        self.rcs_active = False
        self.rcs_throttled = False
        self._rcs_thruster_state = {}
        self._rcs_net_force_n = [0.0, 0.0, 0.0]
        self._rcs_net_torque_nm = [0.0, 0.0, 0.0]
        self._rcs_last_axis = None
        self.rcs_propellant_kg = float(self._rcs_propellant_kg)

        if not self._rcs_enabled:
            return 0.0
        if not self._rcs_thrusters or not self._rcs_axis_groups:
            return 0.0
        if not self._rcs_cmd_axis or self._rcs_cmd_pct <= 0.0:
            return 0.0

        dt = max(0.0, float(delta_time))
        if dt <= 0.0:
            return 0.0

        dt_eff = dt
        # Respect command duration, but apply up to the remaining time in this tick.
        if self._rcs_cmd_time_left_s > 0.0:
            dt_eff = min(dt, float(self._rcs_cmd_time_left_s))

        axis = str(self._rcs_cmd_axis)
        group = self._rcs_axis_groups.get(axis)
        max_proj = float(self._rcs_axis_group_max_proj_n.get(axis, 0.0))
        if not group or max_proj <= 0.0:
            return 0.0

        # Convert command percent into duty scaling for the chosen ZTT group.
        cmd_pct = max(0.0, min(100.0, float(self._rcs_cmd_pct)))
        duty_scale = cmd_pct / 100.0

        # Compute deterministic PWM state.
        window = max(0.0, float(self._rcs_pulse_window_s))
        if window <= 1e-6:
            phase = 0.0
        else:
            phase = (float(self._sim_time_s) % window) / window

        # Per-thruster duty within group is uniform in MVP (scaled by duty_scale).
        duty_by_idx: dict[int, float] = {i: duty_scale for i in group}
        open_by_idx: dict[int, bool] = {}
        for idx in group:
            # Small deterministic per-index phase offset to avoid all valves in sync.
            phase_i = (phase + (idx * 0.07)) % 1.0
            open_by_idx[idx] = phase_i < duty_by_idx[idx]

        # Average forces/torques (use duty as average).
        net_f_avg = [0.0, 0.0, 0.0]
        net_tau_avg = [0.0, 0.0, 0.0]
        f_total_mag = 0.0
        for idx in group:
            t = self._rcs_thrusters[idx]
            d = t.direction.as_list()
            pos = t.position_m.as_list()
            duty = duty_by_idx[idx]
            f = [float(d[0]) * float(t.f_max_newton) * duty, float(d[1]) * float(t.f_max_newton) * duty, float(d[2]) * float(t.f_max_newton) * duty]
            tau = self._cross(pos, f)
            net_f_avg[0] += f[0]; net_f_avg[1] += f[1]; net_f_avg[2] += f[2]
            net_tau_avg[0] += tau[0]; net_tau_avg[1] += tau[1]; net_tau_avg[2] += tau[2]
            f_total_mag += float(self._norm(f))

        # Propellant consumption (MVP): proportional to total thrust magnitude.
        g0 = 9.80665
        isp = max(1e-6, float(self._rcs_isp_s))
        mdot = float(f_total_mag) / (isp * g0)
        m_used = mdot * dt_eff
        if m_used > 0.0:
            if self._rcs_propellant_kg <= 0.0:
                self._rcs_propellant_kg = 0.0
                self._rcs_cmd_pct = 0.0
                return 0.0
            if m_used >= self._rcs_propellant_kg:
                # Scale down last tick so we don't go negative.
                ratio = max(0.0, min(1.0, self._rcs_propellant_kg / m_used))
                for k in list(duty_by_idx.keys()):
                    duty_by_idx[k] *= ratio
                    open_by_idx[k] = open_by_idx[k] and (ratio > 0.0)
                self._rcs_propellant_kg = 0.0
                self._rcs_cmd_pct = 0.0
            else:
                self._rcs_propellant_kg -= float(m_used)

        # Electrical power draw (pulse-shaped by valve openness).
        base_w = float(self._rcs_power_w_at_100pct) * (cmd_pct / 100.0)
        if not group:
            rcs_w = 0.0
        else:
            open_frac = sum(1.0 for idx in group if open_by_idx.get(idx, False)) / float(len(group))
            rcs_w = base_w * float(open_frac)

        self.rcs_active = True
        self._rcs_last_axis = axis
        self._rcs_net_force_n = [float(net_f_avg[0]), float(net_f_avg[1]), float(net_f_avg[2])]
        self._rcs_net_torque_nm = [float(net_tau_avg[0]), float(net_tau_avg[1]), float(net_tau_avg[2])]
        self.rcs_propellant_kg = float(self._rcs_propellant_kg)

        for idx in group:
            t = self._rcs_thrusters[idx]
            self._rcs_thruster_state[idx] = {
                "index": int(t.index),
                "cluster_id": str(t.cluster_id),
                "duty_pct": float(duty_by_idx[idx] * 100.0),
                "valve_open": bool(open_by_idx[idx]),
                "f_max_newton": float(t.f_max_newton),
            }

        # Decrement remaining duration after applying this tick.
        if self._rcs_cmd_time_left_s > 0.0:
            self._rcs_cmd_time_left_s = max(0.0, float(self._rcs_cmd_time_left_s) - dt)
            if self._rcs_cmd_time_left_s <= 0.0:
                self._rcs_cmd_pct = 0.0

        return float(max(0.0, rcs_w))

    def _rcs_apply_throttle_ratio(self, ratio: float, *, reason: str) -> None:
        ratio = max(0.0, min(1.0, float(ratio)))
        if ratio >= 0.999:
            return
        self.rcs_throttled = True
        # Scale displayed duties to match throttling (no mocks).
        for idx, state in list(self._rcs_thruster_state.items()):
            try:
                duty_pct = float(state.get("duty_pct", 0.0)) * ratio
            except Exception:
                duty_pct = 0.0
            state["duty_pct"] = float(duty_pct)
            if float(duty_pct) <= 0.0:
                state["valve_open"] = False
            state["status"] = "throttled"
            state["reason"] = str(reason)
            self._rcs_thruster_state[idx] = state

    def get_state(self) -> Dict[str, Any]:
        """
        Returns the current state of the world model.
        """
        def _status_from_bool(ok: bool | None, *, enabled: bool, warn_on_false: bool = False) -> tuple[str, str]:
            if not enabled:
                return ("na", "disabled")
            if ok is None:
                return ("na", "no reading")
            if ok:
                return ("ok", "ok")
            return ("warn" if warn_on_false else "crit", "not ok")

        def _status_from_limits(value: float | None, *, enabled: bool, warn: float | None, crit: float | None) -> tuple[str, str, dict | None]:
            if not enabled:
                return ("na", "disabled", None)
            if value is None:
                return ("na", "no reading", None)
            if warn is None or crit is None:
                return ("na", "limits not configured", None)
            if float(value) >= float(crit):
                return ("crit", f"value>=crit ({value:.3g}>={crit:.3g})", {"warn_usvh": warn, "crit_usvh": crit})
            if float(value) >= float(warn):
                return ("warn", f"value>=warn ({value:.3g}>={warn:.3g})", {"warn_usvh": warn, "crit_usvh": crit})
            return ("ok", "within limits", {"warn_usvh": warn, "crit_usvh": crit})

        thermal_nodes: list[dict[str, float | str]] = []
        if self._thermal_enabled and self._thermal_nodes_order:
            for nid in self._thermal_nodes_order:
                node = self._thermal_nodes.get(nid)
                if not isinstance(node, dict):
                    continue
                thermal_nodes.append({"id": nid, "temp_c": float(node.get("temp_c", self.temp_external_c))})
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
                "dock_connected": bool(self.dock_connected),
                "dock_soft_start_pct": float(self.dock_soft_start_pct),
                "dock_power_w": float(self.dock_power_w),
                "dock_v": float(self.dock_v),
                "dock_a": float(self.dock_a),
                "dock_temp_c": float(self.dock_temp_c),
                "nbl_active": bool(self.nbl_active),
                "nbl_allowed": bool(self.nbl_allowed),
                "nbl_power_w": float(self.nbl_power_w),
                "nbl_budget_w": float(self.nbl_budget_w),
            },
            "propulsion": {
                "rcs": {
                    "enabled": bool(self._rcs_enabled),
                    "active": bool(self.rcs_active),
                    "throttled": bool(self.rcs_throttled),
                    "axis": self._rcs_last_axis,
                    "command_pct": float(self._rcs_cmd_pct),
                    "time_left_s": float(self._rcs_cmd_time_left_s),
                    "propellant_kg": float(self._rcs_propellant_kg),
                    "power_w": float(self.rcs_power_w),
                    "net_force_n": list(self._rcs_net_force_n),
                    "net_torque_nm": list(self._rcs_net_torque_nm),
                    "thrusters": [self._rcs_thruster_state[i] for i in sorted(self._rcs_thruster_state.keys())],
                }
            },
            "docking": {
                "enabled": bool(self._docking_enabled),
                "state": self.docking_state,
                "connected": bool(self.dock_connected),
                "port": self.docking_port,
                "ports": list(self._docking_ports),
            },
            "sensor_plane": {
                "enabled": bool(self._sensor_plane_enabled),
                "imu": {
                    "enabled": bool(self._imu_enabled),
                    "status": _status_from_bool(self._imu_ok, enabled=bool(self._imu_enabled))[0],
                    "reason": _status_from_bool(self._imu_ok, enabled=bool(self._imu_enabled))[1],
                    "ok": self._imu_ok,
                    "roll_rate_rps": self._imu_roll_rate_rps,
                    "pitch_rate_rps": self._imu_pitch_rate_rps,
                    "yaw_rate_rps": self._imu_yaw_rate_rps,
                },
                "radiation": {
                    "enabled": bool(self._radiation_enabled),
                    "background_usvh": float(self.radiation_usvh) if self._radiation_enabled else None,
                    "dose_total_usv": self._radiation_dose_total_usv,
                    "status": _status_from_limits(
                        float(self.radiation_usvh) if self._radiation_enabled else None,
                        enabled=bool(self._radiation_enabled),
                        warn=self._radiation_warn_usvh,
                        crit=self._radiation_crit_usvh,
                    )[0],
                    "reason": _status_from_limits(
                        float(self.radiation_usvh) if self._radiation_enabled else None,
                        enabled=bool(self._radiation_enabled),
                        warn=self._radiation_warn_usvh,
                        crit=self._radiation_crit_usvh,
                    )[1],
                    "limits": _status_from_limits(
                        float(self.radiation_usvh) if self._radiation_enabled else None,
                        enabled=bool(self._radiation_enabled),
                        warn=self._radiation_warn_usvh,
                        crit=self._radiation_crit_usvh,
                    )[2],
                },
                "proximity": {
                    "enabled": bool(self._proximity_enabled),
                    "min_range_m": self._proximity_min_range_m,
                    "contacts": self._proximity_contacts,
                },
                "solar": {
                    "enabled": bool(self._solar_enabled),
                    "illumination_pct": self._solar_illumination_pct,
                },
                "star_tracker": {
                    "enabled": bool(self._star_tracker_enabled),
                    "status": _status_from_bool(self._star_tracker_locked, enabled=bool(self._star_tracker_enabled), warn_on_false=True)[0],
                    "reason": _status_from_bool(self._star_tracker_locked, enabled=bool(self._star_tracker_enabled), warn_on_false=True)[1],
                    "locked": self._star_tracker_locked,
                    "attitude_err_deg": self._star_tracker_attitude_err_deg,
                },
                "magnetometer": {
                    "enabled": bool(self._magnetometer_enabled),
                    "field_ut": self._mag_field_ut,
                },
            },
        }
