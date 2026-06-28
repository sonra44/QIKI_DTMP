"""IF-RCS-CMD-001 (§14.7) read-only ORION surface of an RCS command.

Per §14.7 ORION must show requested burn, allowed/rejected, active blockers, map status,
thermal blockers, CoM/inertia class, expected effect, and effect confirmation state.
ADR-0015: validation/allowed is NOT effect confirmation. With no real effect loop, effect
confirmation stays "missing" and expected effect stays "target-only" — never claimed.
Read-only; never validates, gates, or executes the burn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qiki.shared.models.rcs import rcs_record_from_mapping

# Reason codes that denote a thermal blocker for the burn (§14.6).
_THERMAL_REASONS = ("RCS_CLUSTER_HOT",)


@dataclass(frozen=True, slots=True)
class RcsCommandEvidence:
    command_id: str
    rcs_mode: str
    requested_burn: str
    validation_label: str
    is_allowed: bool
    active_blockers: tuple[str, ...]
    thrust_map_status: str
    torque_map_status: str
    thermal_blockers: tuple[str, ...]
    com_class: str
    inertia_class: str
    expected_effect: str
    effect_confirmation: str
    reason_codes: tuple[str, ...]
    read_only: bool
    operator_text: str


def _text(value: Any, default: str = "missing") -> str:
    text = str(value or "").strip()
    return text if text else default


def _requested_burn(record: Any) -> str:
    dv = record.requested_delta_v
    tq = record.requested_torque
    if dv is None and tq is None:
        return "none"
    return f"delta_v={dv if dv is not None else 'none'} torque={tq if tq is not None else 'none'}"


def rcs_to_evidence(record: Any) -> RcsCommandEvidence:
    """Read-only ORION projection of one RcsCommandRecord (§14.7)."""
    validation = _text(record.validation_status, "missing")
    reason_codes = tuple(record.reason_codes or ())
    thrust_map = _text(record.Thrust_Map_status)
    torque_map = _text(record.Torque_Map_status)
    maps_present = thrust_map not in ("missing", "") and torque_map not in ("missing", "")
    # Defensive enforcement: ORION honors an allowed claim only when it is internally
    # consistent — no active blocker reason_codes and both thrust/torque maps present.
    is_allowed = validation == "allowed" and not reason_codes and maps_present
    thermal_blockers = tuple(r for r in reason_codes if r in _THERMAL_REASONS or "HOT" in r or "THERMAL" in r)
    # ADR-0015: no real effect loop exists yet — never claim a confirmed effect.
    effect_confirmation = "missing"
    expected_effect = "target-only"
    if is_allowed:
        operator_text = (
            f"RCS: allowed (validation); expected effect: {expected_effect}; "
            f"effect confirmation: {effect_confirmation}"
        )
    elif validation == "allowed":
        flagged = list(reason_codes)
        if not maps_present:
            flagged.append("map_missing")
        operator_text = "RCS: attention — allowed claim not honored: " + ", ".join(flagged)
    else:
        operator_text = "RCS: rejected — " + (", ".join(reason_codes) if reason_codes else "no reason")
    return RcsCommandEvidence(
        command_id=str(record.command_id or "missing"),
        rcs_mode=_text(record.RCS_mode),
        requested_burn=_requested_burn(record),
        validation_label=validation,
        is_allowed=is_allowed,
        active_blockers=reason_codes,
        thrust_map_status=_text(record.Thrust_Map_status),
        torque_map_status=_text(record.Torque_Map_status),
        thermal_blockers=thermal_blockers,
        com_class=_text(record.CoM_class),
        inertia_class=_text(record.inertia_class),
        expected_effect=expected_effect,
        effect_confirmation=effect_confirmation,
        reason_codes=reason_codes,
        read_only=True,
        operator_text=operator_text,
    )


def rcs_evidence_from_snapshot(snapshot: Any) -> RcsCommandEvidence | None:
    """Project §14 RCS command evidence from the EMITTED IF record (RCS Slice consume path).

    Reads ONLY body_if_records.rcs_commands (the one-item list the producer emitted) and never
    re-derives §14 evidence from raw propulsion/rcs state. Returns None when no record is
    emitted — honest "no telemetry" (the caller renders that explicitly, never an allowed claim).
    """
    body = snapshot.get("body_if_records") if isinstance(snapshot, dict) else None
    records_raw = body.get("rcs_commands") if isinstance(body, dict) else None
    if not isinstance(records_raw, list) or not records_raw:
        return None
    first = records_raw[0]
    if not isinstance(first, dict):
        return None
    return rcs_to_evidence(rcs_record_from_mapping(first))
