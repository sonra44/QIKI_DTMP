"""IF-PDU-POWER-001 (§11.8) read-only ORION PDU load-permission surface.

Per §11.8 ORION must show, per load: PDU state, requested load, allowed/rejected, blocked
peak commands, SoC_bat, SoC_cap (separately — ADR-0003), thermal blockers, reason_codes.
Conservative: a rejected/shed load is never shown as allowed; a missing thermal clearance is
never shown as cleared; "all allowed" is claimed only when every load is actually allowed
(unknown/degraded/missing are never masked as allowed). Read-only; never re-decides the PDU.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# §11.6 allowance states grouped by what ORION may assert.
_ALLOWED_STATES = ("load_allowed", "load_allowed_limited")
_REJECTED_STATES = ("load_rejected", "load_shed", "PDU_safe_mode")


@dataclass(frozen=True, slots=True)
class PduLoadEvidence:
    load_id: str
    load_class: str
    requested_power_label: str
    allowance_label: str
    is_rejected: bool
    is_blocked_peak: bool
    pdu_state: str
    soc_bat_label: str
    soc_cap_label: str
    thermal_clearance: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PduEvidence:
    claim_type: str  # "pdu_permission"
    source_type: str  # "telemetry"
    read_only: bool
    loads: tuple[PduLoadEvidence, ...]
    rejected_loads: tuple[str, ...]
    blocked_peak_loads: tuple[str, ...]
    operator_text: str


def _pct(value: Any) -> str:
    return "missing" if value is None else f"{float(value):.0f}%"


def _power(value: Any) -> str:
    return "missing" if value is None else f"{float(value):.0f}W"


def _text(value: Any, default: str = "missing") -> str:
    text = str(value or "").strip()
    return text if text else default


def _load_evidence(record: Any) -> PduLoadEvidence:
    allowance = _text(record.allowance_state, "missing")
    is_rejected = allowance in _REJECTED_STATES
    peak_required = bool(record.peak_required)
    return PduLoadEvidence(
        load_id=str(record.load_id or "missing"),
        load_class=_text(record.load_class),
        requested_power_label=_power(record.requested_power_W),
        allowance_label=allowance,
        is_rejected=is_rejected,
        is_blocked_peak=peak_required and is_rejected,
        pdu_state=_text(record.PDU_state),
        soc_bat_label=_pct(record.SoC_bat),
        soc_cap_label=_pct(record.SoC_cap),
        thermal_clearance=_text(record.thermal_clearance, "missing"),
        reason_codes=tuple(record.reason_codes or ()),
    )


def _is_fully_cleared(load: PduLoadEvidence) -> bool:
    # Full authorization = allowed (not limited) AND thermal affirmatively cleared.
    return load.allowance_label == "load_allowed" and load.thermal_clearance == "clear"


def _attention_label(load: PduLoadEvidence) -> str:
    if load.allowance_label not in _ALLOWED_STATES:
        return f"{load.load_id}={load.allowance_label}"
    if load.thermal_clearance != "clear":
        return f"{load.load_id} thermal_clearance={load.thermal_clearance}"
    return f"{load.load_id}={load.allowance_label}"  # load_allowed_limited (not full)


def pdu_to_evidence(records: Any) -> PduEvidence:
    """Read-only ORION projection of per-load PduPermissionRecord(s)."""
    loads = tuple(_load_evidence(record) for record in records)
    rejected_loads = tuple(load.load_id for load in loads if load.is_rejected)
    blocked_peak_loads = tuple(load.load_id for load in loads if load.is_blocked_peak)
    if blocked_peak_loads:
        operator_text = "PDU: blocked peak — " + ", ".join(blocked_peak_loads)
    elif rejected_loads:
        operator_text = "PDU: rejected loads — " + ", ".join(rejected_loads)
    elif not loads:
        operator_text = "PDU: no load permission telemetry"
    elif all(_is_fully_cleared(load) for load in loads):
        # "all allowed" only when EVERY load is fully allowed AND thermally cleared
        # (ADR-0003: allowance without thermal clearance is not a full authorization).
        operator_text = "PDU: all requested loads allowed"
    else:
        operator_text = "PDU: attention — " + ", ".join(_attention_label(load) for load in loads if not _is_fully_cleared(load))
    return PduEvidence(
        claim_type="pdu_permission",
        source_type="telemetry",
        read_only=True,
        loads=loads,
        rejected_loads=rejected_loads,
        blocked_peak_loads=blocked_peak_loads,
        operator_text=operator_text,
    )
