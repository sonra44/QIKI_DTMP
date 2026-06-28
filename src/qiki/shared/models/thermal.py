"""IF-THERMAL-TELEM-001 (§13.7) shared thermal telemetry contract + mapper.

Single source of truth for the thermal-telemetry record and its pure derivation,
imported by BOTH q_sim (producer) and ORION operator_console (read-only projection).
This replaces the former duplication: q_sim_service.world_model defined the record +
mapper, and operator_console kept a BOUNDED-TEMP verbatim mirror guarded by an
equivalence test. The mapper has NO q_sim / protobuf deps so the console may import it
directly (canon: hard q_sim<->ORION layer separation — the contract is shared, the
runtime is not).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Reason codes — thermal evidence vocabulary.
THERMAL_TELEM_MISSING = "THERMAL_TELEM_MISSING"
THERMAL_NODE_HOT = "THERMAL_NODE_HOT"
THERMAL_NODE_CRITICAL = "THERMAL_NODE_CRITICAL"
PDU_THERMAL_BLOCK = "PDU_THERMAL_BLOCK"
RCS_CLUSTER_HOT = "RCS_CLUSTER_HOT"
SENSOR_HEAD_HOT = "SENSOR_HEAD_HOT"
COMMS_HOT = "COMMS_HOT"
BAYONET_THERMAL_BLOCK = "BAYONET_THERMAL_BLOCK"
MODULE_THERMAL_BLOCK = "MODULE_THERMAL_BLOCK"


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


def _num_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    """Map a thermal-state dict into per-node IF-THERMAL-TELEM-001 records."""
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
