"""IF-RCS-CMD-001 (§14) shared RCS command-validation contract + mapper.

Single source of truth for the RCS command validation record and its pure derivation,
imported by BOTH q_sim (producer) and ORION operator_console (read-only projection). Part
of the producer->transport->ORION evidence path: q_sim emits this record, ORION consumes it
(it must NOT re-derive §14 evidence from raw RCS state). No q_sim / protobuf deps. Reuses the
shared thermal state helper for the RCS cluster-hot gate.

VERBATIM extract: only the reason codes the current mapper actually appends are defined here
(COM_INVALID / INERTIA_UNMODELED are §14.6 vocabulary but the current mapper does not emit
them — adding that validation is a separate explicit behavior task, not this extract).
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from qiki.shared.models.thermal import _thermal_state_from_node

# §14.6 reason codes emitted by the current mapper.
RCS_UNAVAILABLE = "RCS_UNAVAILABLE"
THRUST_MAP_MISSING = "THRUST_MAP_MISSING"
TORQUE_MAP_MISSING = "TORQUE_MAP_MISSING"
RCS_CLUSTER_HOT = "RCS_CLUSTER_HOT"
WORKING_MASS_LOW = "WORKING_MASS_LOW"
BAYONET_SOFT_CAPTURE_ONLY = "BAYONET_SOFT_CAPTURE_ONLY"
BRIDGE_ACTIVE_RESTRICTED_MOTION = "BRIDGE_ACTIVE_RESTRICTED_MOTION"
CAP_LOW = "CAP_LOW"
SAFE_LOCKED = "SAFE_LOCKED"


@dataclass(frozen=True, slots=True)
class RcsCommandRecord:
    """IF-RCS-CMD-001 target-only validation projection from q_sim RCS state."""

    command_id: str
    RCS_mode: str
    requested_delta_v: Any
    requested_torque: Any
    duration_s: float | None
    active_clusters: tuple[str, ...]
    required_thrusters: tuple[str, ...]
    SoC_cap_required: float | None
    thermal_nodes: tuple[str, ...]
    working_mass_required: float | None
    CoM_class: str
    inertia_class: str
    bayonet_state: str
    bridge_state: str
    Thrust_Map_status: str
    Torque_Map_status: str
    validation_status: str
    reason_codes: tuple[str, ...]


def _num_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rcs_thruster_ids(rcs: dict[str, Any]) -> tuple[str, ...]:
    thrusters = rcs.get("thrusters")
    if not isinstance(thrusters, list):
        return ()
    ids: list[str] = []
    for raw in thrusters:
        if not isinstance(raw, dict):
            continue
        if raw.get("index") is not None:
            ids.append(str(raw.get("index")))
    return tuple(dict.fromkeys(ids))


def _rcs_active_clusters(rcs: dict[str, Any]) -> tuple[str, ...]:
    thrusters = rcs.get("thrusters")
    if not isinstance(thrusters, list):
        return ()
    clusters: list[str] = []
    for raw in thrusters:
        if not isinstance(raw, dict):
            continue
        cluster = str(raw.get("cluster_id") or "").strip()
        if cluster:
            clusters.append(cluster)
    return tuple(dict.fromkeys(clusters))


def _rcs_hot_nodes(thermal: dict[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(thermal, dict):
        return ()
    nodes = thermal.get("nodes")
    if not isinstance(nodes, list):
        return ()
    hot: list[str] = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or "").strip()
        if not node_id:
            continue
        if "rcs" not in node_id.lower():
            continue
        if _thermal_state_from_node(raw) in {"hot", "critical"}:
            hot.append(node_id)
    return tuple(dict.fromkeys(hot))


def _rcs_bridge_state(power: dict[str, Any] | None) -> str:
    if not isinstance(power, dict):
        return "missing"
    if power.get("dock_connected") is True:
        return "active_unrated"
    if power.get("dock_connected") is False:
        return "inactive"
    return "missing"


def _rcs_bayonet_state(docking: dict[str, Any] | None) -> str:
    if not isinstance(docking, dict):
        return "missing"
    return str(docking.get("state") or "missing")


def _rcs_reason_codes(
    *,
    rcs: dict[str, Any],
    thrust_map_status: str,
    torque_map_status: str,
    thermal_nodes: tuple[str, ...],
    power: dict[str, Any] | None,
    bayonet_state: str,
    bridge_state: str,
    safe_state: str,
    working_mass_required: float | None,
) -> tuple[str, ...]:
    reason_codes: list[str] = []
    if not bool(rcs.get("enabled")):
        reason_codes.append(RCS_UNAVAILABLE)
    if thrust_map_status == "missing":
        reason_codes.append(THRUST_MAP_MISSING)
    if torque_map_status == "missing":
        reason_codes.append(TORQUE_MAP_MISSING)
    if thermal_nodes:
        reason_codes.append(RCS_CLUSTER_HOT)
    propellant = _num_or_none(rcs.get("propellant_kg"))
    if propellant is not None and propellant <= 0.0:
        reason_codes.append(WORKING_MASS_LOW)
    if working_mass_required is not None and propellant is not None and propellant < working_mass_required:
        reason_codes.append(WORKING_MASS_LOW)
    if bayonet_state == "soft_capture":
        reason_codes.append(BAYONET_SOFT_CAPTURE_ONLY)
    if bridge_state == "active_unrated":
        reason_codes.append(BRIDGE_ACTIVE_RESTRICTED_MOTION)
    if safe_state == "locked":
        reason_codes.append(SAFE_LOCKED)
    soc_cap = _num_or_none(power.get("supercap_soc_pct")) if isinstance(power, dict) else None
    if soc_cap is not None and soc_cap <= 0.0:
        reason_codes.append(CAP_LOW)
    return tuple(dict.fromkeys(reason_codes))


def rcs_command_from_runtime_state(
    rcs: dict[str, Any] | None,
    *,
    power: dict[str, Any] | None = None,
    thermal: dict[str, Any] | None = None,
    docking: dict[str, Any] | None = None,
    command_id: str = "missing",
    requested_delta_v: Any = None,
    requested_torque: Any = None,
    duration_s: float | None = None,
    SoC_cap_required: float | None = None,
    working_mass_required: float | None = None,
    CoM_class: str = "missing",
    inertia_class: str = "missing",
    safe_state: str = "unknown",
) -> RcsCommandRecord:
    """Map q_sim RCS runtime state into IF-RCS-CMD-001 validation record.

    This does not claim ACK or effect confirmation; it only projects command validation inputs
    and blockers that are observable in q_sim runtime state.
    """
    rcs = rcs if isinstance(rcs, dict) else {}
    required_thrusters = _rcs_thruster_ids(rcs)
    active_clusters = _rcs_active_clusters(rcs)
    thrust_map_status = "available" if bool(rcs.get("enabled")) and required_thrusters else "missing"
    torque_map_status = "available" if bool(rcs.get("enabled")) and required_thrusters else "missing"
    thermal_nodes = _rcs_hot_nodes(thermal)
    bayonet_state = _rcs_bayonet_state(docking)
    bridge_state = _rcs_bridge_state(power)
    reason_codes = _rcs_reason_codes(
        rcs=rcs,
        thrust_map_status=thrust_map_status,
        torque_map_status=torque_map_status,
        thermal_nodes=thermal_nodes,
        power=power,
        bayonet_state=bayonet_state,
        bridge_state=bridge_state,
        safe_state=safe_state,
        working_mass_required=working_mass_required,
    )
    rcs_mode = str(rcs.get("axis") or "missing")
    return RcsCommandRecord(
        command_id=str(command_id or "missing"),
        RCS_mode=rcs_mode,
        requested_delta_v=requested_delta_v,
        requested_torque=requested_torque,
        duration_s=duration_s,
        active_clusters=active_clusters,
        required_thrusters=required_thrusters,
        SoC_cap_required=SoC_cap_required,
        thermal_nodes=thermal_nodes,
        working_mass_required=working_mass_required,
        CoM_class=str(CoM_class or "missing"),
        inertia_class=str(inertia_class or "missing"),
        bayonet_state=bayonet_state,
        bridge_state=bridge_state,
        Thrust_Map_status=thrust_map_status,
        Torque_Map_status=torque_map_status,
        validation_status="rejected" if reason_codes else "allowed",
        reason_codes=reason_codes,
    )


_RECORD_FIELD_NAMES = frozenset(f.name for f in fields(RcsCommandRecord))


def rcs_record_from_mapping(mapping: dict[str, Any]) -> RcsCommandRecord:
    """Reconstruct an RcsCommandRecord from an emitted/transported payload dict.

    Only the known §14.4 fields are read; unknown/extra keys are ignored (forward-compatible).
    Tuple fields (active_clusters / required_thrusters / thermal_nodes / reason_codes) survive
    the JSON list round-trip (list -> tuple).
    """
    data = {name: mapping.get(name) for name in _RECORD_FIELD_NAMES}
    for name in ("active_clusters", "required_thrusters", "thermal_nodes", "reason_codes"):
        value = data.get(name)
        data[name] = tuple(value) if isinstance(value, (list, tuple)) else ()
    return RcsCommandRecord(**data)
