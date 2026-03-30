from __future__ import annotations

from typing import Any

CANONICAL_KEYS: dict[str, list[str]] = {
    "comms.link_state": [
        "comms.link_state",
        "comms.link",
        "link.state",
        "comms.state",
        "xpdr.state",
    ],
    "comms.latency_ms": [
        "comms.latency_ms",
        "comms.latency",
        "link.latency_ms",
        "xpdr.latency_ms",
    ],
    "comms.packet_loss_pct": [
        "comms.packet_loss_pct",
        "comms.loss_pct",
        "link.loss_pct",
    ],
    "comms.rssi_dbm": [
        "comms.rssi_dbm",
        "link.rssi_dbm",
        "xpdr.rssi_dbm",
    ],
    "comms.snr_db": [
        "comms.snr_db",
        "link.snr_db",
        "xpdr.snr_db",
    ],
    "comms.tx_power_w": [
        "comms.tx_power_w",
        "link.tx_power_w",
        "xpdr.tx_power_w",
    ],
    "comms.data_rate_kbps": [
        "comms.data_rate_kbps",
        "link.data_rate_kbps",
        "xpdr.data_rate_kbps",
    ],
    "comms.antenna_status": [
        "comms.antenna_status",
        "link.antenna_status",
        "xpdr.antenna_status",
    ],
    "comms.last_seen_ts": [
        "comms.last_seen_ts",
        "link.last_seen_ts",
    ],
    "comms.age_s": [
        "comms.age_s",
        "link.age_s",
    ],
    "comms.plane_enabled": [
        "comms.plane_enabled",
        "comms_plane.enabled",
    ],
    "comms.plane_profile": [
        "comms.plane_profile",
        "comms_plane.profile",
        "comms_plane.mode",
    ],
    "thermal.core_c": [
        "thermal.core_c",
        "sensor_thermal.core_c",
        "sensor_thermal.temp_c",
        "thermal.temp_c",
        "temp_core_c",
    ],
    "thermal.radiator_c": [
        "thermal.radiator_c",
        "thermal.ambient_c",
        "sensor_thermal.ambient_c",
    ],
    "thermal.last_seen_ts": [
        "thermal.last_seen_ts",
        "thermal.ts",
    ],
    "thermal.age_s": [
        "thermal.age_s",
    ],
    "compute.last_seen_ts": [
        "compute.last_seen_ts",
        "compute.heartbeat_last_seen_ts",
        "mcqpu.heartbeat_ts",
        "mainboard.heartbeat_ts",
    ],
    "compute.heartbeat_age_s": [
        "compute.heartbeat_age_s",
        "mcqpu.age_s",
        "mainboard.age_s",
    ],
    "compute.cpu_pct": [
        "compute.cpu_pct",
        "mcqpu.cpu_pct",
        "mainboard.cpu_pct",
        "cpu_usage",
    ],
    "compute.ram_pct": [
        "compute.ram_pct",
        "mcqpu.ram_pct",
        "mainboard.ram_pct",
        "memory_usage",
        "compute.memory_pct",
    ],
    "compute.temp_c": [
        "compute.temp_c",
        "mcqpu.temp_c",
        "mainboard.temp_c",
    ],
    "compute.protocol_errors": [
        "compute.protocol_errors",
        "compute.proc_errors",
        "mainboard.protocol_errors",
        "mcqpu.protocol_errors",
    ],
}

# Backward compatibility alias for existing imports/usages.
KEY_ALIASES = CANONICAL_KEYS

SUBSYSTEM_KEYSETS: dict[str, set[str]] = {
    "power": {
        "power.soc",
        "power.bus_v",
        "power.bus_a",
        "power.draw_w",
        "power.available_w",
        "power.battery_wh",
        "power.load_shedding",
        "power.shed_reasons",
        "power.limit_mode",
        "power.dock_bridge_state",
        "power_budgeter.state",
        "pdu.state",
    },
    "thermal": {
        "thermal.core_c",
        "thermal.radiator_c",
        "thermal.delta_c",
        "thermal.trend",
        "thermal.core_state",
        "thermal.warn_nodes",
        "thermal.trip_nodes",
        "thermal.core_warn_c",
        "thermal.core_trip_c",
        "thermal.core_hys_c",
        "thermal.last_seen_ts",
        "thermal.age_s",
    },
    "comms": {
        "comms.link_state",
        "comms.latency_ms",
        "comms.packet_loss_pct",
        "comms.rssi_dbm",
        "comms.snr_db",
        "comms.tx_power_w",
        "comms.data_rate_kbps",
        "comms.antenna_status",
        "comms.last_seen_ts",
        "comms.age_s",
        "comms.plane_enabled",
        "comms.plane_profile",
    },
    "docking": {
        "docking.state",
        "docking.target",
        "docking.distance_m",
        "docking.approach_mps",
        "docking.alignment_error_deg",
        "docking.lock_state",
        "docking.capture",
        "sensor_docking.status",
    },
    "navigation": {
        "navigation.pos_x",
        "navigation.pos_y",
        "navigation.pos_z",
        "navigation.vel_x",
        "navigation.vel_y",
        "navigation.vel_z",
        "navigation.speed_mps",
        "navigation.heading_deg",
        "navigation.pitch_deg",
        "navigation.yaw_deg",
        "navigation.roll_deg",
        "navigation.p_rate_dps",
        "navigation.y_rate_dps",
        "navigation.r_rate_dps",
        "navigation.mode",
        "navigation.confidence",
        "sensor_star_tracker.status",
    },
    "compute": {
        "compute.last_seen_ts",
        "compute.heartbeat_age_s",
        "compute.cpu_pct",
        "compute.ram_pct",
        "compute.temp_c",
        "compute.protocol_errors",
    },
    "sensors": {
        "sensor.radar_360.status",
        "sensor.lidar_front.status",
        "sensor.lidar.status",
        "sensor.imu_main.status",
        "sensor.sensor_thermal.status",
        "sensor.sensor_radiation.status",
        "sensor.sensor_proximity.status",
        "sensor.sensor_solar.status",
        "sensor.sensor_star_tracker.status",
        "sensor.spectrometer.status",
        "sensor.magnetometer.status",
    },
    "hull": {
        "hull.integrity_pct",
        "hull.hp",
        "hull.hp_max",
        "hull.sector_damage",
        "hull.stress",
    },
    "shields": {
        "shields.level_pct",
        "shields.hp",
        "shields.hp_max",
        "shields.state",
        "shields.draw_w",
        "shields.recharge_w",
    },
    "propulsion": {
        "propulsion.fuel_pct",
        "propulsion.fuel_total_g",
        "propulsion.fuel_rate_gs",
        "rcs.total_thrust_n",
        "motor_left.rpm",
        "motor_right.rpm",
        "motor_left.temp_c",
        "motor_right.temp_c",
    },
}


def canonicalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(snapshot)
    for canonical_key, aliases in CANONICAL_KEYS.items():
        current_value = _get_value(canonical, canonical_key)
        if current_value is not None:
            continue
        for alias in aliases:
            alias_value = _get_value(snapshot, alias)
            if alias_value is not None:
                canonical[canonical_key] = alias_value
                break
    return canonical


def _get_value(snapshot: dict[str, Any], dotted_key: str) -> Any:
    if dotted_key in snapshot:
        return snapshot[dotted_key]
    current: Any = snapshot
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current
