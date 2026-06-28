"""IF-PDU-POWER-001 (§11) shared PDU load-permission contract + mapper.

Single source of truth for the per-load PDU permission record and its pure derivation,
imported by BOTH q_sim (producer) and ORION operator_console (read-only projection). Part
of the producer->transport->ORION evidence path: q_sim emits these records, ORION consumes
them (it must NOT re-derive §11 evidence from raw power state). No q_sim / protobuf deps.
Reuses the shared thermal mapper for the per-load thermal-block gate.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from qiki.shared.models.thermal import thermal_telemetry_from_thermal_state

# §11.7 PDU reason codes.
PDU_DENIED = "PDU_DENIED"
PDU_OVERLOAD = "PDU_OVERLOAD"
PDU_PEAK_DENIED = "PDU_PEAK_DENIED"
CAP_LOW = "CAP_LOW"
BAT_LOW = "BAT_LOW"
BUS_UNSTABLE = "BUS_UNSTABLE"
LOAD_SHED_ACTIVE = "LOAD_SHED_ACTIVE"
THERMAL_BLOCK = "THERMAL_BLOCK"
SAFE_LOCKED = "SAFE_LOCKED"

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


def _num_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    return (str(value),)


def _numeric_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, raw in value.items():
        num = _num_or_none(raw)
        if num is not None:
            out[str(key)] = num
    return out


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
    requested_power_W: float | None,
    duration_s: float | None,
    power: dict[str, Any],
    thermal_blocked: tuple[str, ...],
    thermal_clearance: str,
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
    if peak_required and thermal_clearance != "clear":
        reason_codes.append(THERMAL_BLOCK)
    if "BUS_V_ZERO" in faults or _num_or_none(power.get("bus_v")) == 0.0:
        reason_codes.append(BUS_UNSTABLE)

    soc_cap = _num_or_none(power.get("supercap_soc_pct"))
    cap_capacity_wh = _num_or_none(power.get("supercap_capacity_wh"))
    if peak_required and soc_cap is not None and soc_cap <= 0.0:
        reason_codes.append(CAP_LOW)
        reason_codes.append(PDU_PEAK_DENIED)
    elif (
        peak_required
        and requested_power_W is not None
        and duration_s is not None
        and duration_s > 0.0
        and soc_cap is not None
        and cap_capacity_wh is not None
    ):
        required_wh = requested_power_W * duration_s / 3600.0
        available_wh = cap_capacity_wh * soc_cap / 100.0
        if required_wh > available_wh:
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
            requested_power_W=requested_w,
            duration_s=duration_s,
            power=power,
            thermal_blocked=thermal_blocked,
            thermal_clearance=thermal_clearance,
            allowance_state=allowance_state,
            safe_state=safe_state,
        )
        if (
            peak_required
            and (CAP_LOW in reason_codes or (THERMAL_BLOCK in reason_codes and thermal_clearance != "clear"))
            and allowance_state in {"load_allowed", "load_allowed_limited"}
        ):
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
