"""IF-BAYONET-MECH-001 (§8.10) read-only ORION surface of bayonet mechanical state.

Per §8.10 ORION must show bayonet_id, state, lock quality, structural status, connected object,
bridge availability, motion restrictions, reason_codes. ADR-0009: bridge requires mechanical hard
lock AND structural check passed — soft_capture / magnetic_pre_align / unknown are not
bridge-allowed; degraded_lock requires restricted motion. Defensive: unknown is never shown as
locked/safe. Read-only; never locks, unlocks, or enables a bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Only this state means the mechanical validation chain (hard lock + structural) passed.
_BRIDGE_READY_STATE = "structural_check_passed"
# §8.5 states that constrain motion (ADR-0009: soft capture / pre-align / degraded).
_RESTRICTED_STATES = ("soft_capture", "magnetic_pre_align", "degraded_lock", "emergency_detach_pending")


@dataclass(frozen=True, slots=True)
class BayonetMechEvidence:
    bayonet_id: str
    state: str
    lock_quality: str
    structural_status: str
    connected_object: str
    bridge_available: bool
    motion_restriction: str
    is_unknown: bool
    reason_codes: tuple[str, ...]
    read_only: bool
    operator_text: str


def _text(value: Any, default: str = "missing") -> str:
    text = str(value or "").strip()
    return text if text else default


def bayonet_mech_to_evidence(record: Any) -> BayonetMechEvidence:
    """Read-only ORION projection of one BayonetMechRecord (§8.10)."""
    state = _text(record.state, "unknown")
    reason_codes = tuple(record.reason_codes or ())
    is_unknown = state == "unknown"
    # Defensive: bridge only when the mechanical chain explicitly passed structural check.
    bridge_available = state == _BRIDGE_READY_STATE and not reason_codes
    if is_unknown:
        motion_restriction = "unknown"
    elif state in _RESTRICTED_STATES:
        motion_restriction = "restricted"
    else:
        motion_restriction = "none"
    if is_unknown:
        operator_text = "bayonet: state unknown (target-only) — no bridge, motion restrictions unknown"
    elif bridge_available:
        operator_text = f"bayonet: {state} — bridge available (mechanical)"
    else:
        operator_text = (
            f"bayonet: {state} — no bridge; motion {motion_restriction}"
            + (" — " + ", ".join(reason_codes) if reason_codes else "")
        )
    return BayonetMechEvidence(
        bayonet_id=str(record.bayonet_id or "missing"),
        state=state,
        lock_quality=_text(record.lock_quality),
        structural_status=_text(record.structural_rating),
        connected_object=_text(record.connected_object_id),
        bridge_available=bridge_available,
        motion_restriction=motion_restriction,
        is_unknown=is_unknown,
        reason_codes=reason_codes,
        read_only=True,
        operator_text=operator_text,
    )
