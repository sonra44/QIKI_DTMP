from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Sequence

import math
import time

from qiki.services.q_sim_service.logger import logger
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import Vector3

from qiki.services.q_sim_service.core.mcqpu_telemetry import MCQPUTelemetry
from qiki.shared.config.loaders import ThrusterConfig, load_thrusters_config

POWER_TELEM_MISSING = "POWER_TELEM_MISSING"
THERMAL_TELEM_MISSING = "THERMAL_TELEM_MISSING"
THERMAL_NODE_HOT = "THERMAL_NODE_HOT"
THERMAL_NODE_CRITICAL = "THERMAL_NODE_CRITICAL"
PDU_THERMAL_BLOCK = "PDU_THERMAL_BLOCK"
RCS_CLUSTER_HOT = "RCS_CLUSTER_HOT"
SENSOR_HEAD_HOT = "SENSOR_HEAD_HOT"
COMMS_HOT = "COMMS_HOT"
BAYONET_THERMAL_BLOCK = "BAYONET_THERMAL_BLOCK"
MODULE_THERMAL_BLOCK = "MODULE_THERMAL_BLOCK"
PDU_DENIED = "PDU_DENIED"
PDU_OVERLOAD = "PDU_OVERLOAD"
PDU_PEAK_DENIED = "PDU_PEAK_DENIED"
CAP_LOW = "CAP_LOW"
BAT_LOW = "BAT_LOW"
BUS_UNSTABLE = "BUS_UNSTABLE"
LOAD_SHED_ACTIVE = "LOAD_SHED_ACTIVE"
THERMAL_BLOCK = "THERMAL_BLOCK"
SAFE_LOCKED = "SAFE_LOCKED"
SENSOR_MISSING = "SENSOR_MISSING"
SENSOR_STALE = "SENSOR_STALE"
SENSOR_CONFLICTING = "SENSOR_CONFLICTING"
SENSOR_BLIND = "SENSOR_BLIND"
SENSOR_DEGRADED = "SENSOR_DEGRADED"
SENSOR_BLOCKED_BY_MODULE = "SENSOR_BLOCKED_BY_MODULE"
SENSOR_THERMAL_BLOCK = "SENSOR_THERMAL_BLOCK"
SENSOR_AFFECTED_BY_FIELD = "SENSOR_AFFECTED_BY_FIELD"
SENSOR_AFFECTED_BY_MOTION = "SENSOR_AFFECTED_BY_MOTION"
COMMS_UNAVAILABLE = "COMMS_UNAVAILABLE"
COMMS_DEGRADED = "COMMS_DEGRADED"
EMCON_BLOCK = "EMCON_BLOCK"
COMMS_POWER_BLOCK = "COMMS_POWER_BLOCK"
COMMS_THERMAL_BLOCK = "COMMS_THERMAL_BLOCK"
COMMS_UNAUTHORIZED = "COMMS_UNAUTHORIZED"
COMMS_NOT_IMPLEMENTED = "COMMS_NOT_IMPLEMENTED"
RCS_UNAVAILABLE = "RCS_UNAVAILABLE"
THRUST_MAP_MISSING = "THRUST_MAP_MISSING"
TORQUE_MAP_MISSING = "TORQUE_MAP_MISSING"
RCS_CLUSTER_HOT = "RCS_CLUSTER_HOT"
WORKING_MASS_LOW = "WORKING_MASS_LOW"
COM_INVALID = "COM_INVALID"
INERTIA_UNMODELED = "INERTIA_UNMODELED"
BAYONET_SOFT_CAPTURE_ONLY = "BAYONET_SOFT_CAPTURE_ONLY"
BRIDGE_ACTIVE_RESTRICTED_MOTION = "BRIDGE_ACTIVE_RESTRICTED_MOTION"
NBL_NOT_CRITICAL = "NBL_NOT_CRITICAL"
NBL_PAYLOAD_TOO_LARGE = "NBL_PAYLOAD_TOO_LARGE"
NBL_CAP_LOW = "NBL_CAP_LOW"
NBL_PDU_DENIED = "NBL_PDU_DENIED"
NBL_THERMAL_BLOCK = "NBL_THERMAL_BLOCK"
NBL_NOT_IMPLEMENTED = "NBL_NOT_IMPLEMENTED"
NBL_RULES_ONLY = "NBL_RULES_ONLY"
BLACKBOX_TARGET_ONLY = "BLACKBOX_TARGET_ONLY"
BLACKBOX_NOT_RECORDED = "BLACKBOX_NOT_RECORDED"
BLACKBOX_TRIGGER_MISSING = "BLACKBOX_TRIGGER_MISSING"
BLACKBOX_TRIGGER_DETECTED = "BLACKBOX_TRIGGER_DETECTED"
BAYONET_STATE_UNKNOWN = "BAYONET_STATE_UNKNOWN"
BAYONET_SOFT_CAPTURE_ONLY = "BAYONET_SOFT_CAPTURE_ONLY"
BAYONET_HARD_LOCK_MISSING = "BAYONET_HARD_LOCK_MISSING"
BAYONET_STRUCTURAL_CHECK_FAILED = "BAYONET_STRUCTURAL_CHECK_FAILED"
BAYONET_DEGRADED_LOCK = "BAYONET_DEGRADED_LOCK"
BAYONET_EMERGENCY_DETACH_PENDING = "BAYONET_EMERGENCY_DETACH_PENDING"
BAYONET_CONNECTED_OBJECT_UNKNOWN = "BAYONET_CONNECTED_OBJECT_UNKNOWN"
BRIDGE_HARD_LOCK_MISSING = "BRIDGE_HARD_LOCK_MISSING"
BRIDGE_STRUCTURAL_CHECK_MISSING = "BRIDGE_STRUCTURAL_CHECK_MISSING"
BRIDGE_ELECTRICAL_UNSAFE = "BRIDGE_ELECTRICAL_UNSAFE"
BRIDGE_UMBILICAL_MISSING = "BRIDGE_UMBILICAL_MISSING"
BRIDGE_PASSPORT_MISSING = "BRIDGE_PASSPORT_MISSING"
BRIDGE_PASSPORT_INVALID = "BRIDGE_PASSPORT_INVALID"
BRIDGE_PDU_DENIED = "BRIDGE_PDU_DENIED"
BRIDGE_THERMAL_BLOCK = "BRIDGE_THERMAL_BLOCK"
BRIDGE_SAFE_BLOCK = "BRIDGE_SAFE_BLOCK"
BRIDGE_ACTIVE_RESTRICTED_MOTION = "BRIDGE_ACTIVE_RESTRICTED_MOTION"
SAFE_POWER_LOW = "SAFE_POWER_LOW"
SAFE_CAP_LOW = "SAFE_CAP_LOW"
SAFE_THERMAL_CRITICAL = "SAFE_THERMAL_CRITICAL"
SAFE_SENSOR_CONFLICT = "SAFE_SENSOR_CONFLICT"
SAFE_ORIENTATION_LOST = "SAFE_ORIENTATION_LOST"
SAFE_BAYONET_UNSAFE = "SAFE_BAYONET_UNSAFE"
SAFE_PDU_FAULT = "SAFE_PDU_FAULT"
SAFE_COMMS_LOSS = "SAFE_COMMS_LOSS"
SAFE_DAMAGE_CRITICAL = "SAFE_DAMAGE_CRITICAL"
SAFE_BLACKBOX_CRITICAL = "SAFE_BLACKBOX_CRITICAL"


@dataclass(frozen=True, slots=True)
class PowerTelemetryRecord:
    """IF-POWER-TELEM-001 target-only projection from q_sim power truth."""

    battery_soc_pct: float | None
    battery_capacity_Wh: float | None
    battery_charge_W: float | None
    battery_discharge_W: float | None
    battery_temp_state: str
    supercap_soc_pct: float | None
    supercap_capacity_Wh: float | None
    supercap_charge_W: float | None
    supercap_discharge_W: float | None
    supercap_temp_state: str
    source_generation_W: float | None
    bus_voltage_V: float | None
    bus_current_A: float | None
    loads_W: dict[str, float]
    spill_W: float | None
    unserved_W: float | None
    timestamp: float | None
    freshness: str
    source: str
    trust_status: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ThermalTelemetryRecord:
    """IF-THERMAL-TELEM-001 target-only projection from q_sim thermal truth."""

    thermal_node_id: str
    temp_current: float | None
    thermal_state: str
    temp_warning: float | None
    temp_critical: float | None
    heat_active_W: float | None
    cooldown_state: str
    blocked_commands: tuple[str, ...]
    timestamp: float | None
    freshness: str
    source: str
    trust_status: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PduPermissionRecord:
    """IF-PDU-POWER-001 target-only projection from q_sim power/thermal gates."""

    load_id: str
    load_class: str
    requested_power_W: float | None
    peak_required: bool
    duration_s: float | None
    SoC_bat: float | None
    SoC_cap: float | None
    bus_voltage_V: float | None
    bus_current_A: float | None
    PDU_state: str
    thermal_clearance: str
    SAFE_state: str
    allowance_state: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SensorTelemetryRecord:
    """IF-SENSOR-TELEM-001 target-only projection from q_sim sensor truth."""

    sensor_id: str
    sensor_class: str
    measured_quantity: str
    value: Any
    unit: str
    timestamp: float | None
    freshness: str
    latency: float | None
    accuracy: float | None
    source: str
    trust_status: str
    field_of_view: str | None
    mount_point: str | None
    blocked_by_module: bool | None
    affected_by_motion: bool | None
    affected_by_field: bool | None
    affected_by_emcon: bool | None
    thermal_state: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CommsChannelRecord:
    """IF-COMMS-001 target-only projection from q_sim comms truth."""

    channel_id: str
    channel_class: str
    direction: str
    bandwidth_class: str
    latency: float | None
    power_cost_W: float | None
    thermal_node: str | None
    signature_class: str
    EMCON_state: str
    delivery_state: str
    timestamp: float | None
    freshness: str
    trust_status: str
    reason_codes: tuple[str, ...]


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


@dataclass(frozen=True, slots=True)
class NblPacketRecord:
    """IF-NBL-001 rules-only / target-only projection from q_sim power gates."""

    packet_id: str
    status: str
    criticality: str
    payload_class: str
    payload_size_bits: int | None
    transmit_attempts: int
    SoC_cap_cost: float | None
    power_cost: float | None
    thermal_node: str | None
    expected_latency: str
    delivery_confidence: str
    audit_required: bool
    blackbox_relevance: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BlackboxRecord:
    """IF-BLACKBOX-001 target-only projection; no runtime store is claimed."""

    record_id: str
    recorded_state: str
    timestamp: float | None
    trigger_event: str
    severity: str
    body_state_snapshot: dict[str, Any]
    power_snapshot: dict[str, Any]
    thermal_snapshot: dict[str, Any]
    motion_snapshot: dict[str, Any]
    sensor_snapshot: dict[str, Any]
    command_chain: tuple[str, ...]
    audit_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]
    loss_context: str
    recovery_notes: str


@dataclass(frozen=True, slots=True)
class SafeStateRecord:
    """IF-SAFE-001 target-only survival-state projection; no SAFE engine is claimed."""

    SAFE_state: str
    SAFE_reason: str
    blocked_commands: tuple[str, ...]
    allowed_commands: tuple[str, ...]
    exit_conditions: tuple[str, ...]
    power_state: str
    thermal_state: str
    sensor_state: str
    bayonet_state: str
    damage_state: str
    timestamp: float | None
    reason_codes: tuple[str, ...]
    blackbox_relevance: bool


@dataclass(frozen=True, slots=True)
class BayonetMechRecord:
    """IF-BAYONET-MECH-001 target-only projection from docking/mechanical state."""

    bayonet_id: str
    state: str
    state_timestamp: float | None
    state_source: str
    lock_quality: str
    structural_rating: str
    degraded_reason: str
    connected_object_id: str
    mechanical_load_class: str
    emergency_detach_available: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BayonetBridgeRecord:
    """IF-BAYONET-BRIDGE-001 target-only validation projection."""

    bayonet_id: str
    connected_object_id: str
    bridge_state: str
    mechanical_state: str
    structural_check: str
    electrical_safety_state: str
    umbilical_state: str
    passport_state: str
    power_direction: str
    power_limit_W: float | None
    data_link_state: str
    thermal_node: str
    reason_codes: tuple[str, ...]


def _num_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _numeric_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, raw in value.items():
        num = _num_or_none(raw)
        if num is not None:
            out[str(key)] = num
    return out


def power_telemetry_from_power_state(
    power: dict[str, Any] | None,
    *,
    timestamp: float | None = None,
    freshness: str = "fresh",
    source: str = "q_sim_service.world_model.power",
) -> PowerTelemetryRecord:
    """Map WorldModel power state into IF-POWER-TELEM-001 without merging bat/cap."""
    power = power if isinstance(power, dict) else {}
    sources = _numeric_mapping(power.get("sources_w"))
    source_generation_w = sum(
        value for key, value in sources.items() if key != "supercap_discharge"
    )
    if not sources and "power_in_w" in power:
        source_generation_w = _num_or_none(power.get("power_in_w"))

    reason_codes: list[str] = []
    required = (
        "soc_pct",
        "supercap_soc_pct",
        "bus_v",
        "bus_a",
        "loads_w",
    )
    if any(key not in power for key in required):
        reason_codes.append(POWER_TELEM_MISSING)

    return PowerTelemetryRecord(
        battery_soc_pct=_num_or_none(power.get("soc_pct")),
        battery_capacity_Wh=_num_or_none(power.get("battery_capacity_wh")),
        battery_charge_W=_num_or_none(power.get("battery_charge_w")),
        battery_discharge_W=_num_or_none(power.get("battery_discharge_w")),
        battery_temp_state=str(power.get("battery_temp_state") or "missing"),
        supercap_soc_pct=_num_or_none(power.get("supercap_soc_pct")),
        supercap_capacity_Wh=_num_or_none(power.get("supercap_capacity_wh")),
        supercap_charge_W=_num_or_none(power.get("supercap_charge_w")),
        supercap_discharge_W=_num_or_none(power.get("supercap_discharge_w")),
        supercap_temp_state=str(power.get("supercap_temp_state") or "missing"),
        source_generation_W=source_generation_w,
        bus_voltage_V=_num_or_none(power.get("bus_v")),
        bus_current_A=_num_or_none(power.get("bus_a")),
        loads_W=_numeric_mapping(power.get("loads_w")),
        spill_W=_num_or_none(power.get("battery_spill_w")),
        unserved_W=_num_or_none(power.get("battery_unserved_w")),
        timestamp=timestamp,
        freshness=freshness,
        source=source,
        trust_status="trusted" if not reason_codes else "missing",
        reason_codes=tuple(reason_codes),
    )


def _thermal_state_from_node(node: dict[str, Any]) -> str:
    if bool(node.get("tripped")):
        return "critical"
    if bool(node.get("warned")):
        return "hot"
    temp = _num_or_none(node.get("temp_c"))
    warn = _num_or_none(node.get("warn_c"))
    if temp is None:
        return "unknown"
    if warn is not None and warn > 0.0 and temp >= warn:
        return "hot"
    return "nominal"


def _thermal_reason_codes(node_id: str, thermal_state: str) -> tuple[str, ...]:
    reason_codes: list[str] = []
    if thermal_state == "hot":
        reason_codes.append(THERMAL_NODE_HOT)
    if thermal_state == "critical":
        reason_codes.append(THERMAL_NODE_CRITICAL)

    active = thermal_state in {"hot", "critical"}
    if not active:
        return tuple(reason_codes)

    node_key = node_id.lower()
    if node_key == "pdu":
        reason_codes.append(PDU_THERMAL_BLOCK)
    if "rcs" in node_key:
        reason_codes.append(RCS_CLUSTER_HOT)
    if "sensor" in node_key or node_key in {"sensor_head", "head"}:
        reason_codes.append(SENSOR_HEAD_HOT)
    if "comms" in node_key or "comm" in node_key or "transponder" in node_key:
        reason_codes.append(COMMS_HOT)
    if "bayonet" in node_key:
        reason_codes.append(BAYONET_THERMAL_BLOCK)
    if "module" in node_key:
        reason_codes.append(MODULE_THERMAL_BLOCK)
    return tuple(dict.fromkeys(reason_codes))


def _thermal_blocked_commands(node_id: str, thermal_state: str) -> tuple[str, ...]:
    if thermal_state != "critical":
        return ()
    node_key = node_id.lower()
    if node_key == "core":
        return ("nbl",)
    if node_key == "pdu":
        return ("radar", "transponder", "nbl")
    if "rcs" in node_key:
        return ("rcs",)
    if "sensor" in node_key or node_key in {"sensor_head", "head"}:
        return ("sensor_scan",)
    if "comms" in node_key or "comm" in node_key or "transponder" in node_key:
        return ("comms",)
    if "bayonet" in node_key or "module" in node_key:
        return ("module_attach",)
    return ()


def thermal_telemetry_from_thermal_state(
    thermal: dict[str, Any] | None,
    *,
    timestamp: float | None = None,
    freshness: str = "fresh",
    source: str = "q_sim_service.world_model.thermal",
) -> tuple[ThermalTelemetryRecord, ...]:
    """Map WorldModel thermal state into per-node IF-THERMAL-TELEM-001 records."""
    thermal = thermal if isinstance(thermal, dict) else {}
    nodes = thermal.get("nodes")
    if not isinstance(nodes, list):
        nodes = []

    records: list[ThermalTelemetryRecord] = []
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or "").strip()
        if not node_id:
            continue
        thermal_state = _thermal_state_from_node(raw)
        reason_codes = _thermal_reason_codes(node_id, thermal_state)
        records.append(
            ThermalTelemetryRecord(
                thermal_node_id=node_id,
                temp_current=_num_or_none(raw.get("temp_c")),
                thermal_state=thermal_state,
                temp_warning=_num_or_none(raw.get("warn_c")),
                temp_critical=_num_or_none(raw.get("trip_c")),
                heat_active_W=_num_or_none(raw.get("heat_active_w")),
                cooldown_state=str(raw.get("cooldown_state") or "missing"),
                blocked_commands=_thermal_blocked_commands(node_id, thermal_state),
                timestamp=timestamp,
                freshness=freshness,
                source=source,
                trust_status="trusted" if thermal_state != "unknown" else "missing",
                reason_codes=reason_codes,
            )
        )

    if records:
        return tuple(records)

    return (
        ThermalTelemetryRecord(
            thermal_node_id="missing",
            temp_current=None,
            thermal_state="unknown",
            temp_warning=None,
            temp_critical=None,
            heat_active_W=None,
            cooldown_state="missing",
            blocked_commands=(),
            timestamp=timestamp,
            freshness=freshness,
            source=source,
            trust_status="missing",
            reason_codes=(THERMAL_TELEM_MISSING,),
        ),
    )


_PDU_PEAK_LOADS = {"motion", "rcs", "nbl"}
_PDU_LOAD_CLASSES = {
    "base": "base",
    "mcqpu": "compute",
    "radar": "sensor",
    "transponder": "comms",
    "nbl": "peak",
    "motion": "peak",
    "rcs": "peak",
}


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return () if not value else (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value if str(item))
    return ()


def _thermal_blocked_loads(thermal: dict[str, Any] | None) -> tuple[str, ...]:
    records = thermal_telemetry_from_thermal_state(thermal)
    blocked: list[str] = []
    for record in records:
        blocked.extend(record.blocked_commands)
    return tuple(dict.fromkeys(blocked))


def _pdu_state(power: dict[str, Any], safe_state: str) -> str:
    if safe_state == "locked":
        return "PDU_safe_mode"
    faults = set(_string_tuple(power.get("faults")))
    if "BUS_V_ZERO" in faults or _num_or_none(power.get("bus_v")) == 0.0:
        return "bus_unstable"
    if "PDU_OVERCURRENT" in faults:
        return "overcurrent"
    if bool(power.get("pdu_throttled")):
        return "throttling"
    if bool(power.get("load_shedding")) or _string_tuple(power.get("shed_loads")):
        return "load_shedding"
    return "nominal"


def _pdu_reason_codes(
    load_id: str,
    *,
    peak_required: bool,
    power: dict[str, Any],
    thermal_blocked: tuple[str, ...],
    allowance_state: str,
    safe_state: str,
) -> tuple[str, ...]:
    reason_codes: list[str] = []
    shed_reasons = set(_string_tuple(power.get("shed_reasons")))
    faults = set(_string_tuple(power.get("faults")))
    if safe_state == "locked":
        reason_codes.append(SAFE_LOCKED)
    if "pdu_overcurrent" in shed_reasons or "PDU_OVERCURRENT" in faults:
        reason_codes.append(PDU_OVERLOAD)
    if "low_soc" in shed_reasons:
        reason_codes.append(BAT_LOW)
    if allowance_state == "load_shed":
        reason_codes.append(LOAD_SHED_ACTIVE)
    if "thermal_overheat" in shed_reasons or load_id in thermal_blocked:
        reason_codes.append(THERMAL_BLOCK)
    if "BUS_V_ZERO" in faults or _num_or_none(power.get("bus_v")) == 0.0:
        reason_codes.append(BUS_UNSTABLE)

    soc_cap = _num_or_none(power.get("supercap_soc_pct"))
    if peak_required and soc_cap is not None and soc_cap <= 0.0:
        reason_codes.append(CAP_LOW)
        reason_codes.append(PDU_PEAK_DENIED)

    if allowance_state in {"load_rejected", "PDU_safe_mode"} and not reason_codes:
        reason_codes.append(PDU_DENIED)
    return tuple(dict.fromkeys(reason_codes))


def _pdu_allowance_state(load_id: str, power: dict[str, Any], safe_state: str) -> str:
    if safe_state == "locked":
        return "PDU_safe_mode"
    if load_id in _string_tuple(power.get("shed_loads")):
        return "load_shed"
    if load_id in _string_tuple(power.get("throttled_loads")):
        return "load_allowed_limited"
    if load_id == "nbl" and power.get("nbl_allowed") is False:
        return "load_rejected"
    return "load_allowed"


def pdu_permissions_from_power_state(
    power: dict[str, Any] | None,
    *,
    thermal: dict[str, Any] | None = None,
    duration_s: float | None = None,
    safe_state: str = "unknown",
) -> tuple[PduPermissionRecord, ...]:
    """Map q_sim power/thermal outcomes into per-load IF-PDU-POWER-001 records."""
    power = power if isinstance(power, dict) else {}
    loads = _numeric_mapping(power.get("loads_w"))
    if not loads:
        return (
            PduPermissionRecord(
                load_id="missing",
                load_class="missing",
                requested_power_W=None,
                peak_required=False,
                duration_s=duration_s,
                SoC_bat=_num_or_none(power.get("soc_pct")),
                SoC_cap=_num_or_none(power.get("supercap_soc_pct")),
                bus_voltage_V=_num_or_none(power.get("bus_v")),
                bus_current_A=_num_or_none(power.get("bus_a")),
                PDU_state="missing",
                thermal_clearance="missing",
                SAFE_state=safe_state,
                allowance_state="load_degraded",
                reason_codes=(PDU_DENIED,),
            ),
        )

    thermal_blocked = _thermal_blocked_loads(thermal)
    pdu_state = _pdu_state(power, safe_state)
    thermal_nodes = thermal.get("nodes") if isinstance(thermal, dict) else None
    has_thermal_source = isinstance(thermal_nodes, list) and bool(thermal_nodes)
    shed_loads = _string_tuple(power.get("shed_loads"))
    shed_reasons = _string_tuple(power.get("shed_reasons"))
    records: list[PduPermissionRecord] = []
    for load_id, requested_w in loads.items():
        peak_required = load_id in _PDU_PEAK_LOADS
        allowance_state = _pdu_allowance_state(load_id, power, safe_state)
        if load_id in thermal_blocked or ("thermal_overheat" in shed_reasons and load_id in shed_loads):
            thermal_clearance = "blocked"
        elif has_thermal_source:
            thermal_clearance = "clear"
        else:
            thermal_clearance = "missing"
        reason_codes = _pdu_reason_codes(
            load_id,
            peak_required=peak_required,
            power=power,
            thermal_blocked=thermal_blocked,
            allowance_state=allowance_state,
            safe_state=safe_state,
        )
        if peak_required and CAP_LOW in reason_codes and allowance_state == "load_allowed":
            allowance_state = "load_rejected"
        records.append(
            PduPermissionRecord(
                load_id=load_id,
                load_class=_PDU_LOAD_CLASSES.get(load_id, "load"),
                requested_power_W=requested_w,
                peak_required=peak_required,
                duration_s=duration_s,
                SoC_bat=_num_or_none(power.get("soc_pct")),
                SoC_cap=_num_or_none(power.get("supercap_soc_pct")),
                bus_voltage_V=_num_or_none(power.get("bus_v")),
                bus_current_A=_num_or_none(power.get("bus_a")),
                PDU_state=pdu_state,
                thermal_clearance=thermal_clearance,
                SAFE_state=safe_state,
                allowance_state=allowance_state,
                reason_codes=reason_codes,
            )
        )
    return tuple(records)


def _sensor_thermal_state(thermal: dict[str, Any] | None) -> str:
    if not isinstance(thermal, dict):
        return "unknown"
    nodes = thermal.get("nodes")
    if not isinstance(nodes, list):
        return "unknown"
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or "").lower()
        if "sensor" in node_id or node_id == "head":
            return _thermal_state_from_node(raw)
    return "unknown"


def _sensor_reason_codes(
    *,
    enabled: bool,
    value: Any,
    source: str,
    freshness: str,
    status: str | None = None,
    blind: bool = False,
    thermal_state: str = "unknown",
) -> tuple[str, ...]:
    reason_codes: list[str] = []
    if not enabled or value is None or source == "missing":
        reason_codes.append(SENSOR_MISSING)
    if freshness == "stale":
        reason_codes.append(SENSOR_STALE)
    if blind:
        reason_codes.append(SENSOR_BLIND)
    if status in {"warn", "crit"}:
        reason_codes.append(SENSOR_DEGRADED)
    if thermal_state in {"hot", "critical"}:
        reason_codes.append(SENSOR_THERMAL_BLOCK)
    return tuple(dict.fromkeys(reason_codes))


def _sensor_trust_status(reason_codes: tuple[str, ...], *, blind: bool = False) -> str:
    if SENSOR_MISSING in reason_codes:
        return "missing"
    if SENSOR_STALE in reason_codes:
        return "stale"
    if blind or SENSOR_BLIND in reason_codes:
        return "blind"
    if SENSOR_DEGRADED in reason_codes or SENSOR_THERMAL_BLOCK in reason_codes:
        return "degraded"
    return "trusted"


def _sensor_record(
    *,
    sensor_id: str,
    sensor_class: str,
    measured_quantity: str,
    value: Any,
    unit: str,
    enabled: bool,
    status: str | None,
    source: str,
    timestamp: float | None,
    freshness: str,
    thermal_state: str,
    blind: bool = False,
    field_of_view: str | None = None,
    mount_point: str | None = None,
) -> SensorTelemetryRecord:
    source = str(source or "").strip() or "missing"
    if source == "missing":
        value = None
        freshness = "unknown"
    reason_codes = _sensor_reason_codes(
        enabled=enabled,
        value=value,
        source=source,
        freshness=freshness,
        status=status,
        blind=blind,
        thermal_state=thermal_state,
    )
    return SensorTelemetryRecord(
        sensor_id=sensor_id,
        sensor_class=sensor_class,
        measured_quantity=measured_quantity,
        value=value,
        unit=unit,
        timestamp=timestamp,
        freshness=freshness,
        latency=None,
        accuracy=None,
        source=source,
        trust_status=_sensor_trust_status(reason_codes, blind=blind),
        field_of_view=field_of_view,
        mount_point=mount_point,
        blocked_by_module=None,
        affected_by_motion=None,
        affected_by_field=None,
        affected_by_emcon=None,
        thermal_state=thermal_state,
        reason_codes=reason_codes,
    )


def sensor_telemetry_from_sensor_plane(
    sensor_plane: dict[str, Any] | None,
    *,
    thermal: dict[str, Any] | None = None,
    timestamp: float | None = None,
    freshness: str = "fresh",
    source: str = "q_sim_service.world_model.sensor_plane",
) -> tuple[SensorTelemetryRecord, ...]:
    """Map WorldModel sensor plane state into per-sensor IF-SENSOR-TELEM-001 records."""
    if not isinstance(sensor_plane, dict):
        return (
            _sensor_record(
                sensor_id="missing",
                sensor_class="missing",
                measured_quantity="missing",
                value=None,
                unit="missing",
                enabled=False,
                status=None,
                source="missing",
                timestamp=timestamp,
                freshness="unknown",
                thermal_state="unknown",
            ),
        )

    source = str(source or "").strip() or "missing"
    thermal_state = _sensor_thermal_state(thermal)
    records: list[SensorTelemetryRecord] = []

    imu = sensor_plane.get("imu") if isinstance(sensor_plane.get("imu"), dict) else {}
    imu_value = {
        "roll_rate_rps": _num_or_none(imu.get("roll_rate_rps")),
        "pitch_rate_rps": _num_or_none(imu.get("pitch_rate_rps")),
        "yaw_rate_rps": _num_or_none(imu.get("yaw_rate_rps")),
    }
    if any(value is None for value in imu_value.values()):
        imu_value = None
    records.append(
        _sensor_record(
            sensor_id="imu",
            sensor_class="motion",
            measured_quantity="angular_rate",
            value=imu_value,
            unit="rad/s",
            enabled=bool(imu.get("enabled")),
            status=str(imu.get("status") or ""),
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
        )
    )

    radiation = sensor_plane.get("radiation") if isinstance(sensor_plane.get("radiation"), dict) else {}
    records.append(
        _sensor_record(
            sensor_id="radiation",
            sensor_class="radiation",
            measured_quantity="radiation_background",
            value=_num_or_none(radiation.get("background_usvh")),
            unit="uSv/h",
            enabled=bool(radiation.get("enabled")),
            status=str(radiation.get("status") or ""),
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
        )
    )

    proximity = sensor_plane.get("proximity") if isinstance(sensor_plane.get("proximity"), dict) else {}
    proximity_value = {
        "min_range_m": _num_or_none(proximity.get("min_range_m")),
        "contacts": _num_or_none(proximity.get("contacts")),
    }
    if all(value is None for value in proximity_value.values()):
        proximity_value = None
    records.append(
        _sensor_record(
            sensor_id="proximity",
            sensor_class="proximity",
            measured_quantity="proximity_contact",
            value=proximity_value,
            unit="m/count",
            enabled=bool(proximity.get("enabled")),
            status=None,
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
            field_of_view="local",
        )
    )

    solar = sensor_plane.get("solar") if isinstance(sensor_plane.get("solar"), dict) else {}
    records.append(
        _sensor_record(
            sensor_id="solar",
            sensor_class="illumination",
            measured_quantity="illumination",
            value=_num_or_none(solar.get("illumination_pct")),
            unit="percent",
            enabled=bool(solar.get("enabled")),
            status=None,
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
            field_of_view="external",
        )
    )

    star_tracker = sensor_plane.get("star_tracker") if isinstance(sensor_plane.get("star_tracker"), dict) else {}
    locked = star_tracker.get("locked")
    star_value = None if locked is None else {
        "locked": bool(locked),
        "attitude_err_deg": _num_or_none(star_tracker.get("attitude_err_deg")),
    }
    records.append(
        _sensor_record(
            sensor_id="star_tracker",
            sensor_class="attitude",
            measured_quantity="attitude_lock",
            value=star_value,
            unit="bool/deg",
            enabled=bool(star_tracker.get("enabled")),
            status=str(star_tracker.get("status") or ""),
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
            blind=locked is False,
            field_of_view="stellar",
        )
    )

    magnetometer = sensor_plane.get("magnetometer") if isinstance(sensor_plane.get("magnetometer"), dict) else {}
    field = magnetometer.get("field_ut")
    records.append(
        _sensor_record(
            sensor_id="magnetometer",
            sensor_class="field",
            measured_quantity="magnetic_field",
            value=dict(field) if isinstance(field, dict) else None,
            unit="uT",
            enabled=bool(magnetometer.get("enabled")),
            status=None,
            source=source,
            timestamp=timestamp,
            freshness=freshness,
            thermal_state=thermal_state,
        )
    )

    return tuple(records)


def _comms_bandwidth_class(data_rate_kbps: float | None) -> str:
    if data_rate_kbps is None or data_rate_kbps <= 0.0:
        return "none"
    if data_rate_kbps < 64.0:
        return "low"
    if data_rate_kbps < 256.0:
        return "medium"
    return "high"


def _comms_thermal_blocked(thermal: dict[str, Any] | None) -> bool:
    if not isinstance(thermal, dict):
        return False
    nodes = thermal.get("nodes")
    if not isinstance(nodes, list):
        return False
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or "").lower()
        if ("comms" in node_id or "comm" in node_id or "transponder" in node_id) and _thermal_state_from_node(raw) in {
            "hot",
            "critical",
        }:
            return True
    return False


def _comms_power_blocked(power: dict[str, Any] | None) -> bool:
    if not isinstance(power, dict):
        return False
    return "transponder" in _string_tuple(power.get("shed_loads"))


def _comms_delivery_state(
    *,
    comms_enabled: bool,
    xpdr_allowed: bool,
    link: str,
    emcon_state: str,
    power_blocked: bool,
    thermal_blocked: bool,
) -> str:
    if not comms_enabled:
        return "not_implemented"
    if emcon_state == "EMCON_block":
        return "EMCON_block"
    if thermal_blocked:
        return "thermal_block"
    if power_blocked or not xpdr_allowed:
        return "power_block"
    if link == "online":
        return "online"
    if link == "degraded":
        return "channel_degraded"
    return "not_implemented"


def _comms_reason_codes(delivery_state: str) -> tuple[str, ...]:
    if delivery_state == "online":
        return ()
    mapping = {
        "not_implemented": COMMS_NOT_IMPLEMENTED,
        "EMCON_block": EMCON_BLOCK,
        "power_block": COMMS_POWER_BLOCK,
        "thermal_block": COMMS_THERMAL_BLOCK,
        "SAFE_block": COMMS_UNAVAILABLE,
        "channel_degraded": COMMS_DEGRADED,
        "authorization_missing": COMMS_UNAUTHORIZED,
    }
    return (mapping.get(delivery_state, COMMS_UNAVAILABLE),)


def _comms_delivery_state_from_reason_codes(reason_codes: tuple[str, ...]) -> str:
    if EMCON_BLOCK in reason_codes:
        return "EMCON_block"
    if COMMS_THERMAL_BLOCK in reason_codes:
        return "thermal_block"
    if COMMS_POWER_BLOCK in reason_codes:
        return "power_block"
    if COMMS_DEGRADED in reason_codes:
        return "channel_degraded"
    if COMMS_UNAUTHORIZED in reason_codes:
        return "authorization_missing"
    if COMMS_NOT_IMPLEMENTED in reason_codes:
        return "not_implemented"
    return "not_implemented"


def _comms_trust_status(delivery_state: str) -> str:
    if delivery_state == "online":
        return "trusted"
    if delivery_state == "not_implemented":
        return "missing"
    return "degraded"


def comms_channels_from_comms_state(
    comms: dict[str, Any] | None,
    *,
    power: dict[str, Any] | None = None,
    thermal: dict[str, Any] | None = None,
    timestamp: float | None = None,
    freshness: str = "fresh",
) -> tuple[CommsChannelRecord, ...]:
    """Map q_sim comms payload into per-channel IF-COMMS-001 records."""
    if not isinstance(comms, dict):
        return (
            CommsChannelRecord(
                channel_id="missing",
                channel_class="missing",
                direction="missing",
                bandwidth_class="none",
                latency=None,
                power_cost_W=None,
                thermal_node=None,
                signature_class="missing",
                EMCON_state="missing",
                delivery_state="not_implemented",
                timestamp=timestamp,
                freshness="unknown",
                trust_status="missing",
                reason_codes=(COMMS_NOT_IMPLEMENTED,),
            ),
        )

    xpdr = comms.get("xpdr") if isinstance(comms.get("xpdr"), dict) else {}
    comms_enabled = bool(comms.get("enabled", comms.get("plane_enabled", False)))
    xpdr_allowed = bool(xpdr.get("allowed", False))
    link = str(comms.get("link") or comms.get("link_state") or "").strip().lower()
    emcon_state = str(comms.get("EMCON_state") or comms.get("emcon_state") or "missing")
    source_reason_codes = _string_tuple(comms.get("reason_codes"))
    availability = comms.get("available")
    availability_state = str(availability).strip().lower() if availability is not None else "unknown"
    power_blocked = _comms_power_blocked(power)
    thermal_blocked = _comms_thermal_blocked(thermal)
    if source_reason_codes:
        delivery_state = _comms_delivery_state_from_reason_codes(source_reason_codes)
    elif availability is False or availability_state == "unknown":
        delivery_state = _comms_delivery_state_from_reason_codes(source_reason_codes)
    else:
        delivery_state = _comms_delivery_state(
            comms_enabled=comms_enabled,
            xpdr_allowed=xpdr_allowed,
            link=link,
            emcon_state=emcon_state,
            power_blocked=power_blocked,
            thermal_blocked=thermal_blocked,
    )
    data_rate = _num_or_none(comms.get("data_rate_kbps"))
    mode = str(xpdr.get("mode") or comms.get("plane_profile") or "missing").strip().lower() or "missing"
    reason_codes = source_reason_codes if source_reason_codes else _comms_reason_codes(delivery_state)

    return (
        CommsChannelRecord(
            channel_id="transponder" if comms_enabled else "missing",
            channel_class="transponder" if comms_enabled else "missing",
            direction="tx" if comms_enabled else "missing",
            bandwidth_class=_comms_bandwidth_class(data_rate),
            latency=_num_or_none(comms.get("latency_ms")),
            power_cost_W=_num_or_none(comms.get("tx_power_w")),
            thermal_node="comms" if comms_enabled else None,
            signature_class=mode,
            EMCON_state=emcon_state,
            delivery_state=delivery_state,
            timestamp=timestamp,
            freshness=freshness if comms_enabled else "unknown",
            trust_status=_comms_trust_status(delivery_state),
            reason_codes=reason_codes,
        ),
    )


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


_NBL_CRITICALITIES = {"critical", "emergency", "distress"}
_NBL_BLACKBOX_PAYLOADS = {"distress_packet", "emergency_beacon", "last_state_packet"}


def _nbl_thermal_node(thermal: dict[str, Any] | None, power: dict[str, Any]) -> str | None:
    shed_reasons = _string_tuple(power.get("shed_reasons"))
    shed_loads = _string_tuple(power.get("shed_loads"))
    if "thermal_overheat" in shed_reasons and "nbl" in shed_loads:
        return "core"
    if not isinstance(thermal, dict):
        return None
    nodes = thermal.get("nodes")
    if not isinstance(nodes, list):
        return None
    for raw in nodes:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("id") or "").strip()
        if node_id.lower() not in {"core", "pdu", "nbl"}:
            continue
        if _thermal_state_from_node(raw) in {"hot", "critical"}:
            return node_id
    return None


def _nbl_reason_codes(
    *,
    power: dict[str, Any],
    criticality: str,
    payload_size_bits: int | None,
    max_payload_bits: int,
    thermal_node: str | None,
    safe_state: str,
) -> tuple[str, ...]:
    reason_codes: list[str] = []
    if criticality not in _NBL_CRITICALITIES:
        reason_codes.append(NBL_NOT_CRITICAL)
    if payload_size_bits is not None and payload_size_bits > max_payload_bits:
        reason_codes.append(NBL_PAYLOAD_TOO_LARGE)
    soc_cap = _num_or_none(power.get("supercap_soc_pct"))
    if soc_cap is not None and soc_cap <= 0.0:
        reason_codes.append(NBL_CAP_LOW)
    if power.get("nbl_allowed") is False:
        reason_codes.append(NBL_PDU_DENIED)
    if thermal_node:
        reason_codes.append(NBL_THERMAL_BLOCK)
    reason_codes.append(NBL_RULES_ONLY)
    return tuple(dict.fromkeys(reason_codes))


def nbl_packet_from_runtime_state(
    power: dict[str, Any] | None,
    *,
    thermal: dict[str, Any] | None = None,
    packet_id: str = "missing",
    criticality: str = "missing",
    payload_class: str = "missing",
    payload_size_bits: int | None = None,
    transmit_attempts: int = 0,
    safe_state: str = "unknown",
    max_payload_bits: int = 1024,
) -> NblPacketRecord:
    """Map q_sim NBL rules/power gates into IF-NBL-001 without claiming delivery."""
    if not isinstance(power, dict):
        return NblPacketRecord(
            packet_id=str(packet_id or "missing"),
            status="not_implemented",
            criticality=str(criticality or "missing"),
            payload_class=str(payload_class or "missing"),
            payload_size_bits=payload_size_bits,
            transmit_attempts=max(0, int(transmit_attempts)),
            SoC_cap_cost=None,
            power_cost=None,
            thermal_node=None,
            expected_latency="unknown",
            delivery_confidence="unknown",
            audit_required=False,
            blackbox_relevance=False,
            reason_codes=(NBL_NOT_IMPLEMENTED, NBL_RULES_ONLY),
        )

    criticality_text = str(criticality or "missing").strip().lower() or "missing"
    payload_text = str(payload_class or "missing").strip() or "missing"
    thermal_node = _nbl_thermal_node(thermal, power)
    reason_codes = _nbl_reason_codes(
        power=power,
        criticality=criticality_text,
        payload_size_bits=payload_size_bits,
        max_payload_bits=max_payload_bits,
        thermal_node=thermal_node,
        safe_state=safe_state,
    )
    blocking_reasons = tuple(reason for reason in reason_codes if reason != NBL_RULES_ONLY)
    status = "packet_allowed" if not blocking_reasons else "packet_rejected"
    if not bool(power.get("nbl_active", False)) and status == "packet_allowed":
        status = "critical_only"

    power_cost = _num_or_none(power.get("nbl_budget_w"))
    if power_cost is None:
        power_cost = _num_or_none(power.get("nbl_power_w"))
    blackbox_relevance = criticality_text in _NBL_CRITICALITIES and payload_text in _NBL_BLACKBOX_PAYLOADS
    return NblPacketRecord(
        packet_id=str(packet_id or "missing"),
        status=status,
        criticality=criticality_text,
        payload_class=payload_text,
        payload_size_bits=payload_size_bits,
        transmit_attempts=max(0, int(transmit_attempts)),
        SoC_cap_cost=None,
        power_cost=power_cost,
        thermal_node=thermal_node,
        expected_latency="unknown",
        delivery_confidence="unknown",
        audit_required=criticality_text in _NBL_CRITICALITIES,
        blackbox_relevance=blackbox_relevance,
        reason_codes=reason_codes,
    )


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    return (str(value),)


def _mapping_snapshot(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _blackbox_power_is_critical(power: dict[str, Any]) -> bool:
    faults = {str(fault) for fault in power.get("faults", ()) if fault is not None}
    if faults.intersection({"BUS_V_ZERO", "CRITICAL_POWER_LOSS", "BODY_POWER_LOSS"}):
        return True
    battery_soc = _num_or_none(power.get("soc_pct"))
    cap_soc = _num_or_none(power.get("supercap_soc_pct"))
    return battery_soc == 0.0 or cap_soc == 0.0


def _blackbox_thermal_is_critical(thermal: dict[str, Any]) -> bool:
    nodes = thermal.get("nodes")
    if isinstance(nodes, dict):
        node_values = nodes.values()
    elif isinstance(nodes, Sequence) and not isinstance(nodes, str):
        node_values = nodes
    else:
        return False
    for raw in node_values:
        if not isinstance(raw, dict):
            continue
        if bool(raw.get("tripped")):
            return True
        if _thermal_state_from_node(raw) == "critical":
            return True
    return False


def _blackbox_trigger_from_event(
    event: dict[str, Any],
    *,
    power: dict[str, Any],
    thermal: dict[str, Any],
) -> tuple[str, str]:
    event_type = str(event.get("event_type") or "").strip().lower()
    if _blackbox_power_is_critical(power):
        return "critical power loss", "critical"
    if _blackbox_thermal_is_critical(thermal):
        return "critical thermal event", "critical"
    if event_type == "nbl_packet" or bool(event.get("blackbox_relevance")):
        return "NBL emergency packet", "critical"
    if event_type in {"safe_escalation", "emergency_detach", "postmortem_marker"}:
        return event_type.replace("_", " "), "critical"
    if event_type in {"failed_critical_command", "sensor_conflict_critical_cmd"}:
        return event_type.replace("_", " "), "critical"
    return "missing", "missing"


def blackbox_record_from_runtime_event(
    event: dict[str, Any] | None,
    *,
    state: dict[str, Any] | None = None,
    command_chain: Sequence[str] | None = None,
    audit_refs: Sequence[str] | None = None,
    loss_context: str = "target-only",
    recovery_notes: str = "target-only",
) -> BlackboxRecord:
    """Project runtime state toward IF-BLACKBOX-001 without claiming persistence."""
    event_data = event if isinstance(event, dict) else {}
    state_data = state if isinstance(state, dict) else {}
    power_snapshot = _mapping_snapshot(state_data.get("power"))
    thermal_snapshot = _mapping_snapshot(state_data.get("thermal"))
    sensor_snapshot = _mapping_snapshot(state_data.get("sensor_plane") or state_data.get("sensors"))
    body_state_snapshot = {
        key: state_data[key]
        for key in ("body_state", "safe_state", "qiki_state", "health_state")
        if key in state_data
    }
    motion_snapshot = {
        key: state_data[key]
        for key in ("position", "heading", "speed", "speed_m_s", "velocity_xyz_m_s", "attitude", "orbit")
        if key in state_data
    }

    trigger_event, severity = _blackbox_trigger_from_event(
        event_data,
        power=power_snapshot,
        thermal=thermal_snapshot,
    )
    if trigger_event == "missing":
        reason_codes = (
            BLACKBOX_TARGET_ONLY,
            BLACKBOX_NOT_RECORDED,
            BLACKBOX_TRIGGER_MISSING,
        )
    else:
        reason_codes = (
            BLACKBOX_TARGET_ONLY,
            BLACKBOX_NOT_RECORDED,
            BLACKBOX_TRIGGER_DETECTED,
        )

    event_id = str(event_data.get("event_id") or "target-only")
    return BlackboxRecord(
        record_id=f"bb:{event_id}",
        recorded_state="not_recorded",
        timestamp=_num_or_none(event_data.get("timestamp")),
        trigger_event=trigger_event,
        severity=severity,
        body_state_snapshot=body_state_snapshot,
        power_snapshot=power_snapshot,
        thermal_snapshot=thermal_snapshot,
        motion_snapshot=motion_snapshot,
        sensor_snapshot=sensor_snapshot,
        command_chain=tuple(command_chain) if command_chain is not None else _string_tuple(event_data.get("command_chain")),
        audit_refs=tuple(audit_refs) if audit_refs is not None else _string_tuple(event_data.get("audit_refs")),
        reason_codes=reason_codes,
        loss_context=str(loss_context or "target-only"),
        recovery_notes=str(recovery_notes or "target-only"),
    )


def _safe_get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _safe_power_state(power: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    if not power:
        return "unknown", ()
    reason_codes: list[str] = []
    soc = _num_or_none(power.get("soc_pct"))
    cap = _num_or_none(power.get("supercap_soc_pct"))
    if soc is not None and soc <= 10.0:
        reason_codes.append(SAFE_POWER_LOW)
    if cap is not None and cap <= 10.0:
        reason_codes.append(SAFE_CAP_LOW)
    if reason_codes:
        return "low", tuple(reason_codes)
    return "nominal", ()


def _safe_thermal_state(thermal: dict[str, Any]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    if not thermal:
        return "unknown", (), ()
    records = thermal_telemetry_from_thermal_state(thermal)
    states = {record.thermal_state for record in records}
    blocked: list[str] = []
    for record in records:
        blocked.extend(record.blocked_commands)
    if "critical" in states:
        return "critical", (SAFE_THERMAL_CRITICAL,), tuple(dict.fromkeys(blocked))
    if "hot" in states:
        return "degraded", (), tuple(dict.fromkeys(blocked))
    if states == {"unknown"}:
        return "unknown", (), tuple(dict.fromkeys(blocked))
    return "nominal", (), tuple(dict.fromkeys(blocked))


def _safe_sensor_state(sensor_records: Sequence[Any] | None) -> tuple[str, tuple[str, ...]]:
    if not sensor_records:
        return "unknown", ()
    saw_known = False
    for record in sensor_records:
        trust_status = str(_safe_get(record, "trust_status", "") or "").strip().lower()
        reasons = set(_string_tuple(_safe_get(record, "reason_codes", ())))
        if trust_status == "conflicting" or SENSOR_CONFLICTING in reasons:
            return "conflicting", (SAFE_SENSOR_CONFLICT,)
        if trust_status and trust_status not in {"missing", "unknown"}:
            saw_known = True
    return ("nominal" if saw_known else "unknown"), ()


def _safe_pdu_state(pdu_permissions: Sequence[Any] | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not pdu_permissions:
        return (), ()
    blocked: list[str] = []
    for record in pdu_permissions:
        reasons = set(_string_tuple(_safe_get(record, "reason_codes", ())))
        allowance = str(_safe_get(record, "allowance_state", "") or "")
        load_id = str(_safe_get(record, "load_id", "") or "")
        if reasons.intersection({PDU_OVERLOAD, PDU_DENIED, PDU_PEAK_DENIED, BUS_UNSTABLE}) or allowance in {
            "load_rejected",
            "load_shed",
            "PDU_safe_mode",
        }:
            if load_id and load_id != "missing":
                blocked.append(load_id)
    return ((SAFE_PDU_FAULT,) if blocked else ()), tuple(dict.fromkeys(blocked))


def _safe_exit_conditions(reason_codes: tuple[str, ...]) -> tuple[str, ...]:
    conditions: list[str] = []
    if SAFE_POWER_LOW in reason_codes or SAFE_CAP_LOW in reason_codes:
        conditions.append("exit_power_recovered")
    if SAFE_THERMAL_CRITICAL in reason_codes:
        conditions.append("exit_thermal_nominal")
    if SAFE_SENSOR_CONFLICT in reason_codes:
        conditions.append("exit_sensor_conflict_resolved")
    if SAFE_PDU_FAULT in reason_codes:
        conditions.append("exit_pdu_fault_cleared")
    if SAFE_DAMAGE_CRITICAL in reason_codes:
        conditions.append("exit_damage_assessed")
    if SAFE_BLACKBOX_CRITICAL in reason_codes:
        conditions.append("exit_blackbox_reviewed")
    return tuple(dict.fromkeys(conditions))


def _safe_state_from_reasons(reason_codes: tuple[str, ...]) -> str:
    if not reason_codes:
        return "safe_unknown"
    if any(reason in reason_codes for reason in (SAFE_THERMAL_CRITICAL, SAFE_DAMAGE_CRITICAL, SAFE_BLACKBOX_CRITICAL)):
        return "safe_lockdown"
    if SAFE_SENSOR_CONFLICT in reason_codes and len(reason_codes) == 1:
        return "safe_warning"
    return "safe_limited"


def safe_state_from_runtime_state(
    *,
    power: dict[str, Any] | None = None,
    thermal: dict[str, Any] | None = None,
    sensor_records: Sequence[Any] | None = None,
    pdu_permissions: Sequence[Any] | None = None,
    bayonet_state: str = "unknown",
    damage_state: str = "unknown",
    blackbox_record: Any | None = None,
    timestamp: float | None = None,
) -> SafeStateRecord:
    """Map observed runtime risk signals into IF-SAFE-001 without claiming a SAFE engine."""
    power_data = power if isinstance(power, dict) else {}
    thermal_data = thermal if isinstance(thermal, dict) else {}
    power_state, power_reasons = _safe_power_state(power_data)
    thermal_state, thermal_reasons, thermal_blocked = _safe_thermal_state(thermal_data)
    sensor_state, sensor_reasons = _safe_sensor_state(sensor_records)
    pdu_reasons, pdu_blocked = _safe_pdu_state(pdu_permissions)

    reason_codes: list[str] = []
    reason_codes.extend(power_reasons)
    reason_codes.extend(thermal_reasons)
    reason_codes.extend(sensor_reasons)
    reason_codes.extend(pdu_reasons)
    if str(bayonet_state).lower() in {"unsafe", "soft_capture", "fault"}:
        reason_codes.append(SAFE_BAYONET_UNSAFE)
    if str(damage_state).lower() in {"critical", "fatal"}:
        reason_codes.append(SAFE_DAMAGE_CRITICAL)
    if blackbox_record is not None and str(_safe_get(blackbox_record, "severity", "")).lower() == "critical":
        reason_codes.append(SAFE_BLACKBOX_CRITICAL)

    reason_tuple = tuple(dict.fromkeys(reason_codes))
    blocked_commands = tuple(dict.fromkeys((*thermal_blocked, *pdu_blocked)))
    safe_state = _safe_state_from_reasons(reason_tuple)
    return SafeStateRecord(
        SAFE_state=safe_state,
        SAFE_reason=reason_tuple[0] if reason_tuple else "missing",
        blocked_commands=blocked_commands,
        allowed_commands=("status", "recovery") if safe_state == "safe_lockdown" else ("status",),
        exit_conditions=_safe_exit_conditions(reason_tuple),
        power_state=power_state,
        thermal_state=thermal_state,
        sensor_state=sensor_state,
        bayonet_state=str(bayonet_state or "unknown"),
        damage_state=str(damage_state or "unknown"),
        timestamp=timestamp,
        reason_codes=reason_tuple,
        blackbox_relevance=any(
            reason in reason_tuple
            for reason in (SAFE_THERMAL_CRITICAL, SAFE_DAMAGE_CRITICAL, SAFE_BLACKBOX_CRITICAL)
        ),
    )


_BAYONET_ALLOWED_STATES = {
    "free",
    "approach",
    "alignment",
    "magnetic_pre_align",
    "soft_capture",
    "mechanical_hard_lock",
    "structural_check_passed",
    "structural_check_failed",
    "degraded_lock",
    "emergency_detach_pending",
    "detached",
    "unknown",
}


def _bayonet_connected_object(docking: dict[str, Any], state: str) -> str:
    explicit = str(docking.get("connected_object_id") or "").strip()
    if explicit:
        return explicit
    port = str(docking.get("port") or "").strip()
    if state in {"mechanical_hard_lock", "soft_capture", "degraded_lock", "structural_check_passed"}:
        return f"dock:{port}" if port else "unknown"
    if state == "detached":
        return "none"
    return "unknown"


def _bayonet_state_from_docking(docking: dict[str, Any]) -> str:
    raw_state = str(docking.get("state") or "").strip()
    if raw_state in _BAYONET_ALLOWED_STATES:
        return raw_state
    if raw_state == "docked" or docking.get("connected") is True:
        return "mechanical_hard_lock"
    if raw_state == "undocked" or docking.get("connected") is False:
        return "detached"
    return "unknown"


def _bayonet_reason_codes(state: str, connected_object_id: str) -> tuple[str, ...]:
    reason_codes: list[str] = []
    if state == "unknown":
        reason_codes.append(BAYONET_STATE_UNKNOWN)
    if state in {"soft_capture", "magnetic_pre_align"}:
        reason_codes.append(BAYONET_SOFT_CAPTURE_ONLY)
        reason_codes.append(BAYONET_HARD_LOCK_MISSING)
    if state == "structural_check_failed":
        reason_codes.append(BAYONET_STRUCTURAL_CHECK_FAILED)
    if state == "degraded_lock":
        reason_codes.append(BAYONET_DEGRADED_LOCK)
    if state == "emergency_detach_pending":
        reason_codes.append(BAYONET_EMERGENCY_DETACH_PENDING)
    if connected_object_id == "unknown" and state not in {"unknown", "detached", "free"}:
        reason_codes.append(BAYONET_CONNECTED_OBJECT_UNKNOWN)
    return tuple(dict.fromkeys(reason_codes))


def bayonet_mech_from_docking_state(
    docking: dict[str, Any] | None,
    *,
    timestamp: float | None = None,
    state_source: str = "q_sim_service.world_model.docking",
    bayonet_id: str = "bayonet:primary",
) -> BayonetMechRecord:
    """Map docking/mechanical runtime state into IF-BAYONET-MECH-001 without bridge claims."""
    if not isinstance(docking, dict) or not docking:
        return BayonetMechRecord(
            bayonet_id=bayonet_id,
            state="unknown",
            state_timestamp=timestamp,
            state_source="missing",
            lock_quality="unknown",
            structural_rating="unknown",
            degraded_reason="missing",
            connected_object_id="unknown",
            mechanical_load_class="unknown",
            emergency_detach_available=False,
            reason_codes=(BAYONET_STATE_UNKNOWN,),
        )

    if docking.get("enabled") is False:
        state = "unknown"
    else:
        state = _bayonet_state_from_docking(docking)
    connected_object_id = _bayonet_connected_object(docking, state)
    structural_rating = str(docking.get("structural_rating") or "unknown")
    lock_quality = str(docking.get("lock_quality") or "unknown")
    if state == "mechanical_hard_lock" and lock_quality == "unknown":
        lock_quality = "hard_lock_observed"
    elif state == "soft_capture" and lock_quality == "unknown":
        lock_quality = "soft_capture"
    elif state in {"detached", "free"} and lock_quality == "unknown":
        lock_quality = "none"

    degraded_reason = str(docking.get("degraded_reason") or "missing")
    mechanical_load_class = str(docking.get("mechanical_load_class") or "unknown")
    emergency_detach_available = bool(docking.get("connected")) or state in {
        "soft_capture",
        "mechanical_hard_lock",
        "structural_check_passed",
        "degraded_lock",
        "emergency_detach_pending",
    }
    return BayonetMechRecord(
        bayonet_id=str(docking.get("bayonet_id") or bayonet_id),
        state=state,
        state_timestamp=timestamp,
        state_source=state_source,
        lock_quality=lock_quality,
        structural_rating=structural_rating,
        degraded_reason=degraded_reason,
        connected_object_id=connected_object_id,
        mechanical_load_class=mechanical_load_class,
        emergency_detach_available=emergency_detach_available,
        reason_codes=_bayonet_reason_codes(state, connected_object_id),
    )


def _bridge_structural_check(mech: BayonetMechRecord | None) -> str:
    if mech is None:
        return "missing"
    if mech.state == "structural_check_passed":
        return "passed"
    if mech.state == "structural_check_failed" or mech.structural_rating == "failed":
        return "failed"
    if mech.structural_rating == "passed":
        return "passed"
    return "missing"


def _bridge_reason_codes(
    *,
    mech: BayonetMechRecord | None,
    structural_check: str,
    electrical_safety_state: str,
    umbilical_state: str,
    passport_state: str,
    pdu_allowance_state: str,
    thermal_clearance: str,
    safe_state: str,
    motion_restriction: str,
) -> tuple[str, ...]:
    reason_codes: list[str] = []
    mechanical_state = "unknown" if mech is None else mech.state
    if mechanical_state not in {"mechanical_hard_lock", "structural_check_passed"}:
        reason_codes.append(BRIDGE_HARD_LOCK_MISSING)
    if structural_check != "passed":
        reason_codes.append(BRIDGE_STRUCTURAL_CHECK_MISSING)
    if electrical_safety_state != "passed":
        reason_codes.append(BRIDGE_ELECTRICAL_UNSAFE)
    if umbilical_state != "mated":
        reason_codes.append(BRIDGE_UMBILICAL_MISSING)
    if passport_state == "invalid":
        reason_codes.append(BRIDGE_PASSPORT_INVALID)
    elif passport_state != "validated":
        reason_codes.append(BRIDGE_PASSPORT_MISSING)
    if pdu_allowance_state != "allowed":
        reason_codes.append(BRIDGE_PDU_DENIED)
    if thermal_clearance != "clear":
        reason_codes.append(BRIDGE_THERMAL_BLOCK)
    if safe_state in {"safe_warning", "safe_limited", "safe_lockdown"}:
        reason_codes.append(BRIDGE_SAFE_BLOCK)
    if motion_restriction == "restricted":
        reason_codes.append(BRIDGE_ACTIVE_RESTRICTED_MOTION)
    return tuple(dict.fromkeys(reason_codes))


def bayonet_bridge_from_runtime_state(
    mech: BayonetMechRecord | None,
    *,
    desired_bridge_state: str = "bridge_allowed",
    electrical_safety_state: str = "missing",
    umbilical_state: str = "missing",
    passport_state: str = "missing",
    pdu_allowance_state: str = "denied",
    thermal_clearance: str = "missing",
    safe_state: str = "safe_unknown",
    motion_restriction: str = "none",
    power_direction: str = "none",
    power_limit_W: float | None = None,
    data_link_state: str = "missing",
    thermal_node: str = "missing",
) -> BayonetBridgeRecord:
    """Map bayonet validation chain into IF-BAYONET-BRIDGE-001 without activating bridge."""
    structural_check = _bridge_structural_check(mech)
    reason_codes = _bridge_reason_codes(
        mech=mech,
        structural_check=structural_check,
        electrical_safety_state=electrical_safety_state,
        umbilical_state=umbilical_state,
        passport_state=passport_state,
        pdu_allowance_state=pdu_allowance_state,
        thermal_clearance=thermal_clearance,
        safe_state=safe_state,
        motion_restriction=motion_restriction,
    )
    if reason_codes == (BRIDGE_ACTIVE_RESTRICTED_MOTION,):
        bridge_state = "bridge_degraded"
    elif reason_codes:
        bridge_state = "bridge_disallowed"
    elif desired_bridge_state == "bridge_active":
        bridge_state = "bridge_active"
    else:
        bridge_state = "bridge_allowed"

    return BayonetBridgeRecord(
        bayonet_id="bayonet:primary" if mech is None else mech.bayonet_id,
        connected_object_id="unknown" if mech is None else mech.connected_object_id,
        bridge_state=bridge_state,
        mechanical_state="unknown" if mech is None else mech.state,
        structural_check=structural_check,
        electrical_safety_state=electrical_safety_state,
        umbilical_state=umbilical_state,
        passport_state=passport_state,
        power_direction=power_direction,
        power_limit_W=_num_or_none(power_limit_W),
        data_link_state=data_link_state,
        thermal_node=thermal_node,
        reason_codes=reason_codes,
    )


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
        # Battery electrical constraints (virtual hardware). 0.0 means "unlimited".
        self._battery_max_charge_w = 0.0
        self._battery_max_discharge_w = 0.0
        self._battery_channel_delta_v = 0.0
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
        # Battery charge/discharge telemetry (post-supercap; derived, no-mocks).
        self.battery_charge_w = 0.0
        self.battery_discharge_w = 0.0
        self.battery_spill_w = 0.0
        self.battery_unserved_w = 0.0

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
        self.docking_connected = False
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
        self._radiation_warn_usvh: float | None = None
        self._radiation_crit_usvh: float | None = None

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
        self._rcs_propellant_kg_initial = 0.0
        self._rcs_isp_s = 0.0
        self._rcs_power_w_at_100pct = 0.0
        self._rcs_heat_fraction_to_hull = 0.0
        self._rcs_pulse_window_s = 0.0
        self._rcs_ztt_torque_tol_nm = 0.0
        self._propellant_tank_pressure_nominal_pa = 2_000_000.0
        self._propellant_tank_pressure_min_pa = 200_000.0
        self._oxidizer_mass_ratio = 0.0

        self._rcs_cmd_axis: str | None = None
        self._rcs_cmd_pct: float = 0.0
        self._rcs_cmd_time_left_s: float = 0.0
        self._rcs_fuel_rate_gs: float = 0.0

        self.rcs_active = False
        self.rcs_power_w = 0.0
        self.rcs_propellant_kg = 0.0
        self.rcs_throttled = False
        self._rcs_thruster_state: dict[int, dict[str, float | bool | str]] = {}
        self._rcs_net_force_n: list[float] = [0.0, 0.0, 0.0]
        self._rcs_net_torque_nm: list[float] = [0.0, 0.0, 0.0]
        self._rcs_last_axis: str | None = None

        self._actuator_role_by_id: dict[str, str] = {}
        self._actuator_id_by_role: dict[str, str] = {}

        # Apply runtime profile from bot_config (single SoT).
        self._apply_bot_config(bot_config)

        # Power Plane breakdown (operator-facing diagnostics; no-mocks).
        # These are derived values, not additional sources of truth.
        self.power_loads_w: dict[str, float] = {
            "base": float(self._base_power_out_w),
            "motion": 0.0,
            "mcqpu": 0.0,
            "radar": 0.0,
            "transponder": 0.0,
            "nbl": 0.0,
            "rcs": 0.0,
            "supercap_charge": 0.0,
        }
        self.power_sources_w: dict[str, float] = {
            "base": float(self._base_power_in_w),
            "dock": 0.0,
            "supercap_discharge": 0.0,
        }

        self._sim_time_s = 0.0
        # Simulation-truth epoch base (used to derive deterministic event timestamps from sim time).
        # Captured once at boot to avoid per-tick wall-clock jitter.
        self._sim_epoch_start_ts = float(time.time())

        # Virtual MCQPU utilization (simulation-truth).
        self._mcqpu = MCQPUTelemetry()
        self.cpu_usage = float(self._mcqpu.state.cpu_usage_pct)
        self.memory_usage = float(self._mcqpu.state.memory_usage_pct)
        self._radar_enabled = False
        self._sensor_queue_depth = 0
        self._actuator_queue_depth = 0
        self._transponder_active = False
        logger.info("WorldModel initialized.")

    def sim_time_s(self) -> float:
        return float(self._sim_time_s)

    def sim_epoch_start_ts(self) -> float:
        return float(self._sim_epoch_start_ts)

    def sim_time_epoch_ts(self) -> float:
        return float(self._sim_epoch_start_ts + self._sim_time_s)

    def _apply_bot_config(self, bot_config: dict | None) -> None:
        if not isinstance(bot_config, dict):
            return

        hw = bot_config.get("hardware_profile")
        if not isinstance(hw, dict):
            return

        self._actuator_role_by_id.clear()
        self._actuator_id_by_role.clear()
        actuators = hw.get("actuators")
        if isinstance(actuators, list):
            for item in actuators:
                if not isinstance(item, dict):
                    continue
                raw_id = str(item.get("id") or "").strip()
                role = str(item.get("role") or "").strip()
                if not role:
                    role = raw_id
                if raw_id:
                    self._actuator_role_by_id[raw_id] = role
                    if role and role not in self._actuator_id_by_role:
                        self._actuator_id_by_role[role] = raw_id

        if "power_capacity_wh" in hw:
            try:
                self._battery_capacity_wh = float(hw["power_capacity_wh"])
            except Exception:
                self.power_faults.append("BATTERY_CAPACITY_INVALID")
        else:
            self.power_faults.append("BATTERY_CAPACITY_MISSING")

        if "battery_soc_init_pct" in hw:
            try:
                init_soc = float(hw["battery_soc_init_pct"])
                self.battery_level = max(0.0, min(100.0, init_soc))
            except Exception:
                self.power_faults.append("BATTERY_SOC_INIT_INVALID")

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
        battery_max_charge_w = f("battery_max_charge_w", self._battery_max_charge_w)
        if battery_max_charge_w < 0.0:
            self.power_faults.append("POWER_PLANE_PARAM_NEGATIVE:battery_max_charge_w")
            battery_max_charge_w = 0.0
        self._battery_max_charge_w = float(battery_max_charge_w)
        battery_max_discharge_w = f("battery_max_discharge_w", self._battery_max_discharge_w)
        if battery_max_discharge_w < 0.0:
            self.power_faults.append("POWER_PLANE_PARAM_NEGATIVE:battery_max_discharge_w")
            battery_max_discharge_w = 0.0
        self._battery_max_discharge_w = float(battery_max_discharge_w)
        battery_channel_delta_v = f("battery_channel_delta_v", self._battery_channel_delta_v)
        if battery_channel_delta_v < 0.0:
            self.power_faults.append("POWER_PLANE_PARAM_NEGATIVE:battery_channel_delta_v")
            battery_channel_delta_v = 0.0
        self._battery_channel_delta_v = float(battery_channel_delta_v)

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
            self.docking_connected = False
            self.docking_state = "disabled"
        else:
            self.docking_port = self._docking_default_port
            self.docking_connected = bool(self.dock_connected)
            self.docking_state = "docked" if self.docking_connected else "undocked"

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
                float(prox.get("min_range_m_init"))
                if self._proximity_enabled and prox.get("min_range_m_init") is not None
                else None
            )
        except Exception:
            self._proximity_min_range_m = None
        try:
            self._proximity_contacts = (
                int(prox.get("contacts_init"))
                if self._proximity_enabled and prox.get("contacts_init") is not None
                else None
            )
        except Exception:
            self._proximity_contacts = None

        solar = sp.get("solar") if isinstance(sp.get("solar"), dict) else {}
        try:
            self._solar_illumination_pct = (
                float(solar.get("illumination_pct_init"))
                if self._solar_enabled and solar.get("illumination_pct_init") is not None
                else None
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
        self.battery_charge_w = 0.0
        self.battery_discharge_w = 0.0
        self.battery_spill_w = 0.0
        self.battery_unserved_w = 0.0

        # Thermal Plane parameters (single source of truth: bot_config.json).
        tp = hw.get("thermal_plane")
        if not isinstance(tp, dict):
            tp = {}

        self._thermal_enabled = bool(tp.get("enabled", False))
        try:
            self._thermal_ambient_exchange_w_per_c = float(tp.get("ambient_exchange_w_per_c", 0.0))
        except Exception:
            self._thermal_ambient_exchange_w_per_c = 0.0

        # Warn threshold policy: derived warn = trip - warn_delta unless explicit t_warn_c is provided.
        try:
            self._thermal_warn_delta_c = float(tp.get("warn_delta_c", 10.0))
        except Exception:
            self._thermal_warn_delta_c = 10.0
        self._thermal_warn_delta_c = max(0.0, min(80.0, float(self._thermal_warn_delta_c)))

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

            try:
                t_warn = raw.get("t_warn_c")
                t_warn = float(t_warn) if t_warn is not None else None
            except Exception:
                t_warn = None

            cap = max(1.0, cap)
            cool = max(0.0, cool)
            t_init = max(-120.0, min(160.0, t_init))
            t_trip = float(t_trip)
            t_hys = max(0.0, t_hys)

            if t_trip > 0.0 and t_hys <= 0.0:
                # Keep this config warning persistent (survives step() fault reset).
                self.power_faults.append(f"THERMAL_PLANE_PARAM_INVALID:{node_id}:hys_zero")

            if t_warn is None and t_trip > 0.0:
                t_warn = float(t_trip) - float(self._thermal_warn_delta_c)
            if t_warn is None:
                t_warn = 0.0

            self._thermal_nodes_order.append(node_id)
            self._thermal_nodes[node_id] = {
                "temp_c": float(t_init),
                "cap_j_per_c": float(cap),
                "cool_w_per_c": float(cool),
                "trip_c": float(t_trip),
                "hys_c": float(t_hys),
                "warn_c": float(t_warn),
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
            self._rcs_propellant_kg_initial = float(self._rcs_propellant_kg)
            try:
                self._rcs_isp_s = max(0.0, float(pr.get("isp_s", 0.0)))
            except Exception:
                self._rcs_isp_s = 0.0
            try:
                self._rcs_power_w_at_100pct = max(0.0, float(pr.get("rcs_power_w_at_100pct", 0.0)))
            except Exception:
                self._rcs_power_w_at_100pct = 0.0
            try:
                self._rcs_heat_fraction_to_hull = max(0.0, min(1.0, float(pr.get("heat_fraction_to_hull", 0.0))))
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
            try:
                self._propellant_tank_pressure_nominal_pa = max(
                    0.0,
                    float(pr.get("propellant_tank_pressure_nominal_pa", self._propellant_tank_pressure_nominal_pa)),
                )
            except Exception:
                self._propellant_tank_pressure_nominal_pa = 2_000_000.0
            try:
                self._propellant_tank_pressure_min_pa = max(
                    0.0,
                    float(pr.get("propellant_tank_pressure_min_pa", self._propellant_tank_pressure_min_pa)),
                )
            except Exception:
                self._propellant_tank_pressure_min_pa = 200_000.0
            if self._propellant_tank_pressure_min_pa > self._propellant_tank_pressure_nominal_pa:
                self._propellant_tank_pressure_min_pa = float(self._propellant_tank_pressure_nominal_pa)
            try:
                self._oxidizer_mass_ratio = max(0.0, float(pr.get("oxidizer_mass_ratio", self._oxidizer_mass_ratio)))
            except Exception:
                self._oxidizer_mass_ratio = 0.0
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
            # Passive ambient cooling cannot drive a node below ambient; prevent Euler overshoot.
            if t >= amb and t2 < amb:
                t2 = max(-120.0, min(160.0, float(amb)))
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

    def set_docking_connected(self, connected: bool) -> bool:
        if not self._docking_enabled:
            return False
        connected = bool(connected)
        self.docking_connected = connected
        self.docking_state = "docked" if connected else "undocked"
        if connected and self.docking_port is None:
            self.docking_port = self._docking_default_port
        if not connected:
            self.set_dock_connected(False)
        return True

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
        logger.debug(f"Applying command to WorldModel: {command.command_type} for {command.actuator_id.value}")

        actuator_id = getattr(getattr(command, "actuator_id", None), "value", "")
        role = self._actuator_role_by_id.get(str(actuator_id), str(actuator_id))
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

        if role in ("motor_left", "motor_right"):
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
        axis = axis_map.get(str(role))
        if axis and cmd_type == ActuatorCommand.CommandType.SET_VELOCITY:
            pct = _as_pct()
            if pct is None:
                return
            pct = max(0.0, min(100.0, float(pct)))
            timeout_ms = int(getattr(command, "timeout_ms", 0) or 0)
            duration_s = max(0.0, float(timeout_ms) / 1000.0) if timeout_ms > 0 else 0.0
            if not self.set_rcs_command(axis, pct, duration_s):
                return
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
            logger.debug(f"WorldModel moved to ({self.position.x:.2f}, {self.position.y:.2f})")

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
        self.power_faults = [
            f
            for f in self.power_faults
            if f.endswith("_MISSING")
            or f.endswith("_INVALID")
            or f.startswith("POWER_PLANE_PARAM_INVALID")
            or f.startswith("THERMAL_PLANE_PARAM_INVALID")
        ]
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
        xpdr_out = self._transponder_power_w if (self._transponder_active and self.transponder_allowed) else 0.0
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
            self._base_power_out_w + motion_out + mcqpu_out + radar_out + xpdr_out + nbl_out + rcs_out
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
                self._base_power_out_w + motion_out + mcqpu_out + radar_out + xpdr_out + nbl_out + rcs_out
            )
            if power_out_wo_supercap > pdu_limit_w and motion_out > 0.0:
                excess = power_out_wo_supercap - pdu_limit_w
                reduced = min(excess, motion_out)
                motion_out -= reduced
                self.power_pdu_throttled = True
                self.power_throttled_loads.append("motion")
                power_out_wo_supercap = (
                    self._base_power_out_w + motion_out + mcqpu_out + radar_out + xpdr_out + nbl_out + rcs_out
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
                        self._base_power_out_w + motion_out + mcqpu_out + radar_out + xpdr_out + nbl_out + rcs_out
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
            self.supercap_soc_pct = (
                0.0
                if self._supercap_capacity_wh <= 0.0
                else (self._supercap_energy_wh / self._supercap_capacity_wh) * 100.0
            )
        else:
            self.supercap_soc_pct = 0.0

        # Finalize bus current and battery SoC update.
        self.power_bus_a = 0.0 if self.power_bus_v <= 0.0 else self.power_out_w / self.power_bus_v
        net_w = self.power_in_w - self.power_out_w
        if self._battery_capacity_wh > 0.0:
            raw_charge_w = max(0.0, float(net_w))
            raw_discharge_w = max(0.0, float(-net_w))

            max_charge_w = max(0.0, float(self._battery_max_charge_w))
            max_discharge_w = max(0.0, float(self._battery_max_discharge_w))

            charge_w = raw_charge_w
            if max_charge_w > 0.0 and charge_w > max_charge_w:
                self.power_faults.append("BATTERY_CHARGE_LIMIT")
                self.battery_spill_w = float(charge_w - max_charge_w)
                charge_w = max_charge_w

            discharge_w = raw_discharge_w
            if max_discharge_w > 0.0 and discharge_w > max_discharge_w:
                self.power_faults.append("BATTERY_DISCHARGE_LIMIT")
                self.battery_unserved_w = float(discharge_w - max_discharge_w)
                discharge_w = max_discharge_w

            self.battery_charge_w = float(max(0.0, charge_w))
            self.battery_discharge_w = float(max(0.0, discharge_w))

            effective_net_w = self.battery_charge_w - self.battery_discharge_w
            delta_wh = float(effective_net_w) * delta_time / 3600.0
            delta_pct = (delta_wh / self._battery_capacity_wh) * 100.0
            self.battery_level = max(0.0, min(100.0, self.battery_level + delta_pct))
        else:
            self.battery_level = max(0.0, min(100.0, self.battery_level))
            self.power_faults.append("BATTERY_CAPACITY_ZERO")

        if self.battery_level <= 0.0 and self.battery_discharge_w > 0.0:
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

        # Power breakdown (final, post-shedding / post-throttling / post-supercap).
        self.power_loads_w = {
            "base": float(self._base_power_out_w),
            "motion": float(motion_out),
            "mcqpu": float(mcqpu_out),
            "radar": float(radar_out),
            "transponder": float(xpdr_out),
            "nbl": float(nbl_out),
            "rcs": float(rcs_out),
            "supercap_charge": float(self.supercap_charge_w),
        }
        self.power_sources_w = {
            "base": float(self._base_power_in_w),
            "dock": float(self.dock_power_w),
            "supercap_discharge": float(self.supercap_discharge_w),
        }

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
            f = [
                float(d[0]) * float(t.f_max_newton),
                float(d[1]) * float(t.f_max_newton),
                float(d[2]) * float(t.f_max_newton),
            ]
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
                    net_f[0] += f[0]
                    net_f[1] += f[1]
                    net_f[2] += f[2]
                    net_tau[0] += tau[0]
                    net_tau[1] += tau[1]
                    net_tau[2] += tau[2]
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
            f = [
                float(d[0]) * float(t.f_max_newton) * duty,
                float(d[1]) * float(t.f_max_newton) * duty,
                float(d[2]) * float(t.f_max_newton) * duty,
            ]
            tau = self._cross(pos, f)
            net_f_avg[0] += f[0]
            net_f_avg[1] += f[1]
            net_f_avg[2] += f[2]
            net_tau_avg[0] += tau[0]
            net_tau_avg[1] += tau[1]
            net_tau_avg[2] += tau[2]
            f_total_mag += float(self._norm(f))

        # Propellant consumption (MVP): proportional to total thrust magnitude.
        g0 = 9.80665
        isp = max(1e-6, float(self._rcs_isp_s))
        mdot = float(f_total_mag) / (isp * g0)
        self._rcs_fuel_rate_gs = max(0.0, mdot * 1000.0)
        m_used = mdot * dt_eff
        if m_used > 0.0:
            if self._rcs_propellant_kg <= 0.0:
                self._rcs_propellant_kg = 0.0
                self._rcs_cmd_pct = 0.0
                self._rcs_fuel_rate_gs = 0.0
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
            self._rcs_cmd_time_left_s = max(0.0, float(self._rcs_cmd_time_left_s) - dt_eff)
            if self._rcs_cmd_time_left_s <= 0.0:
                self._rcs_cmd_pct = 0.0
                self._rcs_fuel_rate_gs = 0.0

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

        def _status_from_limits(
            value: float | None, *, enabled: bool, warn: float | None, crit: float | None
        ) -> tuple[str, str, dict | None]:
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

        thermal_nodes: list[dict[str, float | str | bool]] = []
        if self._thermal_enabled and self._thermal_nodes_order:
            for nid in self._thermal_nodes_order:
                node = self._thermal_nodes.get(nid)
                if not isinstance(node, dict):
                    continue
                temp_c = float(node.get("temp_c", self.temp_external_c))
                tripped = bool(self._thermal_trip_state.get(nid, False))
                warn_c = float(node.get("warn_c", 0.0))
                warned = bool((not tripped) and warn_c > 0.0 and temp_c >= warn_c)
                thermal_nodes.append(
                    {
                        "id": nid,
                        "temp_c": temp_c,
                        # Operator-facing (derived, no-mocks): explicit trip/warn state and thresholds.
                        "tripped": tripped,
                        "warned": warned,
                        "warn_c": warn_c,
                        "trip_c": float(node.get("trip_c", 0.0)),
                        "hys_c": float(node.get("hys_c", 0.0)),
                    }
                )
        heading_rad = math.radians(float(self.heading))
        vel_x = float(self.speed) * math.sin(heading_rad)
        vel_y = float(self.speed) * math.cos(heading_rad)
        vel_z = 0.0
        r_xy = math.hypot(float(self.position.x), float(self.position.y))
        r_m = math.sqrt(float(self.position.x) ** 2 + float(self.position.y) ** 2 + float(self.position.z) ** 2)
        inclination_deg = math.degrees(math.atan2(abs(float(self.position.z)), max(1e-9, r_xy)))
        if r_m > 1.0 and abs(float(self.speed)) > 0.01:
            orbit_state = "degraded"
            orbit_reason = "kinematic_estimate_non_orbital_model"
            orbit_confidence = 0.25
            orbit_apoapsis_km = r_m / 1000.0
            orbit_periapsis_km = r_m / 1000.0
            orbit_period_min = (2.0 * math.pi * r_m) / max(abs(float(self.speed)), 1e-6) / 60.0
            orbit_eccentricity = 0.0
        else:
            orbit_state = "off"
            orbit_reason = "insufficient_motion_or_radius"
            orbit_confidence = 0.0
            orbit_apoapsis_km = None
            orbit_periapsis_km = None
            orbit_period_min = None
            orbit_eccentricity = None

        bus_v = float(self.power_bus_v)
        half_delta_v = float(self._battery_channel_delta_v) / 2.0
        battery_1_voltage_v = max(0.0, bus_v + half_delta_v)
        battery_2_voltage_v = max(0.0, bus_v - half_delta_v)

        propellant_init = max(0.0, float(self._rcs_propellant_kg_initial))
        propellant_now = max(0.0, float(self._rcs_propellant_kg))
        propellant_total_g = propellant_init * 1000.0
        remaining_fuel_g = propellant_now * 1000.0
        fuel_pct = 0.0 if propellant_init <= 0.0 else max(0.0, min(100.0, (propellant_now / propellant_init) * 100.0))
        fill_ratio = 0.0 if propellant_init <= 0.0 else max(0.0, min(1.0, propellant_now / propellant_init))
        pressure_span = max(0.0, float(self._propellant_tank_pressure_nominal_pa - self._propellant_tank_pressure_min_pa))
        propellant_tank_pressure_pa = float(self._propellant_tank_pressure_min_pa + pressure_span * fill_ratio)
        oxidizer_mass_kg = max(0.0, propellant_now * float(self._oxidizer_mass_ratio))
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
            "speed_m_s": self.speed,
            "velocity_xyz_m_s": {"x": vel_x, "y": vel_y, "z": vel_z},
            "orbit": {
                "state": orbit_state,
                "reason": orbit_reason,
                "confidence": orbit_confidence,
                "apoapsis_km": orbit_apoapsis_km,
                "periapsis_km": orbit_periapsis_km,
                "inclination_deg": inclination_deg,
                "eccentricity": orbit_eccentricity,
                "period_min": orbit_period_min,
            },
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
                "sources_w": dict(self.power_sources_w),
                "loads_w": dict(self.power_loads_w),
                "power_in_w": self.power_in_w,
                "power_out_w": self.power_out_w,
                "battery_capacity_wh": float(self._battery_capacity_wh),
                "battery_charge_w": float(self.battery_charge_w),
                "battery_discharge_w": float(self.battery_discharge_w),
                "battery_spill_w": float(self.battery_spill_w),
                "battery_unserved_w": float(self.battery_unserved_w),
                "bus_v": self.power_bus_v,
                "battery_1_voltage_v": battery_1_voltage_v,
                "battery_2_voltage_v": battery_2_voltage_v,
                "bus_a": self.power_bus_a,
                "load_shedding": bool(self.power_load_shedding),
                "shed_loads": list(self.power_shed_loads),
                "shed_reasons": list(self.power_shed_reasons),
                "pdu_limit_w": max(0.0, float(self._max_bus_a) * float(self.power_bus_v)),
                "pdu_throttled": bool(self.power_pdu_throttled),
                "throttled_loads": list(self.power_throttled_loads),
                "faults": list(self.power_faults),
                "supercap_soc_pct": float(self.supercap_soc_pct),
                "supercap_capacity_wh": float(self._supercap_capacity_wh),
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
                "fuel_pct": fuel_pct,
                "fuel_total_g": propellant_total_g,
                "fuel_rate_gs": float(self._rcs_fuel_rate_gs),
                "remaining_fuel_g": remaining_fuel_g,
                "propellant_tank_pressure_pa": propellant_tank_pressure_pa,
                "oxidizer_mass_kg": oxidizer_mass_kg,
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
                    "thrusters": [dict(self._rcs_thruster_state[i]) for i in sorted(self._rcs_thruster_state.keys())],
                }
            },
            "docking": {
                "enabled": bool(self._docking_enabled),
                "state": self.docking_state,
                "connected": bool(self.docking_connected),
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
                    "status": _status_from_bool(
                        self._star_tracker_locked, enabled=bool(self._star_tracker_enabled), warn_on_false=True
                    )[0],
                    "reason": _status_from_bool(
                        self._star_tracker_locked, enabled=bool(self._star_tracker_enabled), warn_on_false=True
                    )[1],
                    "locked": self._star_tracker_locked,
                    "attitude_err_deg": self._star_tracker_attitude_err_deg,
                },
                "magnetometer": {
                    "enabled": bool(self._magnetometer_enabled),
                    "field_ut": self._mag_field_ut,
                },
            },
        }
