from __future__ import annotations

"""Canonical actuation state contract for q-sim.

Layer 04 (Actuation) is the boundary between command intent and physical
movement.  It records desired actuator state separately from the actual effect
produced after lower constraints such as PDU limits and propellant availability.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence


ACTUATION_SCHEMA_VERSION = 1


class ActuationEffectStatus(StrEnum):
    IDLE = "IDLE"
    COMMANDED = "COMMANDED"
    APPLIED = "APPLIED"
    THROTTLED = "THROTTLED"
    REJECTED = "REJECTED"
    UNAVAILABLE = "UNAVAILABLE"


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


def _text(value: Any) -> str:
    return str(value or "").strip()


def vector3_mapping(value: Sequence[float] | Mapping[str, Any] | None) -> dict[str, float]:
    if isinstance(value, Mapping):
        return {"x": _finite_float(value.get("x")), "y": _finite_float(value.get("y")), "z": _finite_float(value.get("z"))}
    seq = list(value or [])
    return {
        "x": _finite_float(seq[0] if len(seq) > 0 else 0.0),
        "y": _finite_float(seq[1] if len(seq) > 1 else 0.0),
        "z": _finite_float(seq[2] if len(seq) > 2 else 0.0),
    }


@dataclass(frozen=True, slots=True)
class RcsThrusterActuation:
    index: int
    cluster_id: str
    duty_pct: float
    valve_open: bool
    f_max_newton: float
    status: str = "nominal"
    reason: str = ""

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RcsThrusterActuation":
        return cls(
            index=int(_finite_float(data.get("index"), 0.0)),
            cluster_id=_text(data.get("cluster_id")),
            duty_pct=max(0.0, min(100.0, _finite_float(data.get("duty_pct"), 0.0))),
            valve_open=bool(data.get("valve_open", False)),
            f_max_newton=max(0.0, _finite_float(data.get("f_max_newton"), 0.0)),
            status=_text(data.get("status")) or "nominal",
            reason=_text(data.get("reason")),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "index": int(self.index),
            "cluster_id": self.cluster_id,
            "duty_pct": float(self.duty_pct),
            "valve_open": bool(self.valve_open),
            "f_max_newton": float(self.f_max_newton),
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RcsActuationState:
    enabled: bool
    active: bool
    desired_axis: str | None = None
    desired_pct: float = 0.0
    desired_duration_s: float = 0.0
    desired_time_left_s: float = 0.0
    actual_axis: str | None = None
    actual_pct: float = 0.0
    burn_id: str | None = None
    command_id: str | None = None
    effect_status: ActuationEffectStatus = ActuationEffectStatus.IDLE
    started_at_sim_time_s: float | None = None
    last_effect_at_sim_time_s: float | None = None
    propellant_kg: float = 0.0
    propellant_used_kg: float = 0.0
    propellant_used_last_tick_kg: float = 0.0
    fuel_rate_gs: float = 0.0
    power_w: float = 0.0
    heat_w: float = 0.0
    body_frame_force_n: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    body_frame_torque_nm: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    throttled: bool = False
    throttle_reason: str = ""
    thrusters: tuple[RcsThrusterActuation, ...] = field(default_factory=tuple)
    faults: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def to_mapping(self) -> dict[str, Any]:
        net_force = [self.body_frame_force_n["x"], self.body_frame_force_n["y"], self.body_frame_force_n["z"]]
        net_torque = [self.body_frame_torque_nm["x"], self.body_frame_torque_nm["y"], self.body_frame_torque_nm["z"]]
        return {
            "enabled": bool(self.enabled),
            "active": bool(self.active),
            "desired_axis": self.desired_axis,
            "desired_pct": float(self.desired_pct),
            "desired_duration_s": float(self.desired_duration_s),
            "desired_time_left_s": float(self.desired_time_left_s),
            "actual_axis": self.actual_axis,
            "actual_pct": float(self.actual_pct),
            "burn_id": self.burn_id,
            "command_id": self.command_id,
            "effect_status": self.effect_status.value,
            "started_at_sim_time_s": self.started_at_sim_time_s,
            "last_effect_at_sim_time_s": self.last_effect_at_sim_time_s,
            "propellant_kg": float(self.propellant_kg),
            "propellant_used_kg": float(self.propellant_used_kg),
            "propellant_used_last_tick_kg": float(self.propellant_used_last_tick_kg),
            "fuel_rate_gs": float(self.fuel_rate_gs),
            "power_w": float(self.power_w),
            "heat_w": float(self.heat_w),
            "body_frame_force_n": dict(self.body_frame_force_n),
            "body_frame_torque_nm": dict(self.body_frame_torque_nm),
            "net_force_n": net_force,
            "net_torque_nm": net_torque,
            "throttled": bool(self.throttled),
            "throttle_reason": self.throttle_reason,
            "thrusters": [t.to_mapping() for t in self.thrusters],
            "faults": list(self.faults),
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class ActuationState:
    rcs: RcsActuationState
    docking: dict[str, Any]
    nbl: dict[str, Any]
    xpdr: dict[str, Any]
    world_tick_id: str | int | None = None
    world_snapshot_id: str | None = None
    source_world_snapshot_id: str | None = None
    sim_time_s: float | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    schema_version: int = ACTUATION_SCHEMA_VERSION

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "world_tick_id": self.world_tick_id,
            "world_snapshot_id": self.world_snapshot_id,
            "source_world_snapshot_id": self.source_world_snapshot_id or self.world_snapshot_id,
            "sim_time_s": self.sim_time_s,
            "source_path": "q_sim_service.WorldModel.actuation",
            "rcs": self.rcs.to_mapping(),
            "docking": dict(self.docking or {}),
            "nbl": dict(self.nbl or {}),
            "xpdr": dict(self.xpdr or {}),
            "evidence": list(self.evidence),
        }
