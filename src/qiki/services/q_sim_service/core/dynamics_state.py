from __future__ import annotations

"""Canonical dynamics state contract for q-sim.

Layer 05 (Dynamics) turns actual actuation effects into physical motion.
Desired commands never enter this contract directly: only the post-propellant,
post-PDU Layer-04 actual force/torque is allowed to change velocity, position,
angular velocity and attitude.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from qiki.services.q_sim_service.core.actuation_state import vector3_mapping


DYNAMICS_SCHEMA_VERSION = 1


def _finite_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(default)
    try:
        parsed = float(value)
    except Exception:
        return float(default)
    if parsed != parsed or parsed in (float("inf"), float("-inf")):
        return float(default)
    return float(parsed)


def _vec3(value: Sequence[float] | Mapping[str, Any] | None) -> dict[str, float]:
    return vector3_mapping(value)


@dataclass(frozen=True, slots=True)
class DynamicsState:
    world_tick_id: str | int | None = None
    world_snapshot_id: str | None = None
    source_world_snapshot_id: str | None = None
    sim_time_s: float | None = None
    mass_kg: float = 1.0
    dry_mass_kg: float = 1.0
    propellant_mass_kg: float = 0.0
    inertia_diag_kg_m2: Mapping[str, Any] | Sequence[float] = field(
        default_factory=lambda: {"x": 1.0, "y": 1.0, "z": 1.0}
    )
    position_xyz_m: Mapping[str, Any] | Sequence[float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    velocity_xyz_m_s: Mapping[str, Any] | Sequence[float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    integrated_rcs_velocity_xyz_m_s: Mapping[str, Any] | Sequence[float] = field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}
    )
    legacy_kinematic_velocity_xyz_m_s: Mapping[str, Any] | Sequence[float] = field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}
    )
    acceleration_xyz_m_s2: Mapping[str, Any] | Sequence[float] = field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}
    )
    angular_velocity_rad_s: Mapping[str, Any] | Sequence[float] = field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}
    )
    angular_acceleration_rad_s2: Mapping[str, Any] | Sequence[float] = field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0}
    )
    attitude_rad: Mapping[str, Any] | Sequence[float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    actual_force_body_n: Mapping[str, Any] | Sequence[float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    actual_torque_body_nm: Mapping[str, Any] | Sequence[float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    actual_force_world_n: Mapping[str, Any] | Sequence[float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    actual_torque_world_nm: Mapping[str, Any] | Sequence[float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    force_source: str = "none"
    torque_source: str = "none"
    burn_id: str | None = None
    command_id: str | None = None
    frame_transform_status: str = "unknown"
    evidence: tuple[str, ...] = field(default_factory=tuple)
    schema_version: int = DYNAMICS_SCHEMA_VERSION

    def to_mapping(self) -> dict[str, Any]:
        inertia = _vec3(self.inertia_diag_kg_m2)
        pos = _vec3(self.position_xyz_m)
        vel = _vec3(self.velocity_xyz_m_s)
        rcs_vel = _vec3(self.integrated_rcs_velocity_xyz_m_s)
        legacy_vel = _vec3(self.legacy_kinematic_velocity_xyz_m_s)
        accel = _vec3(self.acceleration_xyz_m_s2)
        ang_vel = _vec3(self.angular_velocity_rad_s)
        ang_accel = _vec3(self.angular_acceleration_rad_s2)
        attitude_raw = _vec3(self.attitude_rad)
        body_force = _vec3(self.actual_force_body_n)
        body_torque = _vec3(self.actual_torque_body_nm)
        world_force = _vec3(self.actual_force_world_n)
        world_torque = _vec3(self.actual_torque_world_nm)
        speed = (vel["x"] ** 2 + vel["y"] ** 2 + vel["z"] ** 2) ** 0.5
        return {
            "schema_version": int(self.schema_version),
            "world_tick_id": self.world_tick_id,
            "world_snapshot_id": self.world_snapshot_id,
            "source_world_snapshot_id": self.source_world_snapshot_id or self.world_snapshot_id,
            "sim_time_s": self.sim_time_s,
            "source_path": "q_sim_service.WorldModel.dynamics",
            "mass_kg": max(0.0, _finite_float(self.mass_kg, 0.0)),
            "dry_mass_kg": max(0.0, _finite_float(self.dry_mass_kg, 0.0)),
            "propellant_mass_kg": max(0.0, _finite_float(self.propellant_mass_kg, 0.0)),
            "inertia_diag_kg_m2": inertia,
            "position_xyz_m": pos,
            "velocity_xyz_m_s": vel,
            "speed_m_s": float(speed),
            "integrated_rcs_velocity_xyz_m_s": rcs_vel,
            "legacy_kinematic_velocity_xyz_m_s": legacy_vel,
            "acceleration_xyz_m_s2": accel,
            "angular_velocity_rad_s": ang_vel,
            "angular_acceleration_rad_s2": ang_accel,
            "attitude_rad": {
                "roll": attitude_raw["x"],
                "pitch": attitude_raw["y"],
                "yaw": attitude_raw["z"],
                # Compatibility aliases for vector consumers.
                "x": attitude_raw["x"],
                "y": attitude_raw["y"],
                "z": attitude_raw["z"],
            },
            "actual_force_body_n": body_force,
            "actual_torque_body_nm": body_torque,
            "actual_force_world_n": world_force,
            "actual_torque_world_nm": world_torque,
            # Layer-05 canonical aliases used by newer consumers.
            "body_frame_force_n": body_force,
            "body_frame_torque_nm": body_torque,
            "world_frame_force_n": world_force,
            "world_frame_torque_nm": world_torque,
            "force_source": str(self.force_source or "none"),
            "torque_source": str(self.torque_source or "none"),
            "burn_id": self.burn_id,
            "command_id": self.command_id,
            "frame_transform_status": str(self.frame_transform_status or "unknown"),
            "evidence": list(self.evidence),
        }


__all__ = ["DYNAMICS_SCHEMA_VERSION", "DynamicsState"]
