"""IF-THERMAL-TELEM-001 (§13.7) read-only ORION thermal surface.

Per §13.7 ORION must show, per thermal node: which node is heating, which commands are
blocked, what cooldown is needed, and which reason_code is active. Values are surfaced
from ThermalTelemetryRecord(s) where present; absent state stays "unknown" and absent
provenance stays "missing" (Canon != Implemented). This module does not compute thermal
state, gate commands, or invoke the PDU.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# §13.5 states that mean a node is heating in a way ORION must flag.
_HOT_STATES = ("hot", "critical")


@dataclass(frozen=True, slots=True)
class ThermalNodeEvidence:
    node_id: str
    state_label: str  # §13.5: nominal/warm/hot/critical/cooldown/unknown
    is_hot: bool
    temp_label: str
    cooldown_label: str
    blocked_commands: tuple[str, ...]
    reason_codes: tuple[str, ...]
    trust_status: str


@dataclass(frozen=True, slots=True)
class ThermalEvidence:
    claim_type: str  # "thermal_telemetry"
    source_type: str  # "telemetry"
    read_only: bool
    nodes: tuple[ThermalNodeEvidence, ...]
    hot_nodes: tuple[str, ...]
    operator_text: str


def _temp(value: Any) -> str:
    return "missing" if value is None else f"{float(value):.0f}°C"


def _state_text(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "unknown"


def _commands(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return () if value in ("", "missing") else (value,)
    return tuple(value)


def _node_evidence(record: Any) -> ThermalNodeEvidence:
    state = _state_text(record.thermal_state)
    return ThermalNodeEvidence(
        node_id=str(record.thermal_node_id or "missing"),
        state_label=state,
        is_hot=state in _HOT_STATES,
        temp_label=_temp(record.temp_current),
        cooldown_label=str(record.cooldown_state or "missing"),
        blocked_commands=_commands(record.blocked_commands),
        reason_codes=tuple(record.reason_codes or ()),
        trust_status=str(record.trust_status or "missing"),
    )


def thermal_to_evidence(records: Any) -> ThermalEvidence:
    """Read-only ORION projection of per-node ThermalTelemetryRecord(s)."""
    nodes = tuple(_node_evidence(record) for record in records)
    hot_nodes = tuple(node.node_id for node in nodes if node.is_hot)
    if not nodes:
        operator_text = "thermal: no node telemetry"
    elif hot_nodes:
        operator_text = "thermal: heating nodes — " + ", ".join(hot_nodes)
    elif all(node.state_label == "nominal" for node in nodes):
        # "all nominal" only when EVERY node is nominal — never mask warm/cooldown/unknown.
        operator_text = "thermal: all nodes nominal"
    elif all(node.state_label == "unknown" for node in nodes):
        operator_text = "thermal: no node telemetry (unknown/missing)"
    else:
        flagged = [
            f"{node.node_id}={node.state_label}"
            for node in nodes
            if node.state_label != "nominal"
        ]
        operator_text = "thermal: attention — " + ", ".join(flagged)
    return ThermalEvidence(
        claim_type="thermal_telemetry",
        source_type="telemetry",
        read_only=True,
        nodes=nodes,
        hot_nodes=hot_nodes,
        operator_text=operator_text,
    )
