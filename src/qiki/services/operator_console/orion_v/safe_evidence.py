"""IF-SAFE-001 (§22.7) read-only ORION surface of SAFE state.

Per §22.7 ORION must show SAFE state, the primary reason_code, blocked commands, allowed
commands, exit conditions, missing data, and degraded nodes. REQ-SAFE-001 (P0): SAFE is a
physical survival mode. Defensive: safe_unknown (no real evaluation) is never shown as
inactive/nominal. Read-only; never enters, exits, or decides SAFE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# §22.5 states where SAFE is actively engaged / constraining the body.
_ACTIVE_STATES = ("safe_warning", "safe_limited", "safe_lockdown")
_NODE_STATE_FIELDS = ("power_state", "thermal_state", "sensor_state", "bayonet_state", "damage_state")
_ABSENT = ("", "missing", "unknown", "none")


@dataclass(frozen=True, slots=True)
class SafeEvidence:
    safe_state: str
    primary_reason: str
    is_active: bool
    is_unknown: bool
    blocked_commands: tuple[str, ...]
    allowed_commands: tuple[str, ...]
    exit_conditions: tuple[str, ...]
    missing_data: tuple[str, ...]
    degraded_nodes: tuple[str, ...]
    reason_codes: tuple[str, ...]
    read_only: bool
    operator_text: str


def _text(value: Any, default: str = "missing") -> str:
    text = str(value or "").strip()
    return text if text else default


def _commands(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return () if value in ("", "missing") else (value,)
    return tuple(value)


def safe_to_evidence(record: Any) -> SafeEvidence:
    """Read-only ORION projection of one SafeStateRecord (§22.7)."""
    safe_state = _text(record.SAFE_state, "safe_unknown")
    reason_codes = tuple(record.reason_codes or ())
    safe_reason = _text(record.SAFE_reason, "")
    primary_reason = safe_reason if safe_reason and safe_reason != "missing" else (reason_codes[0] if reason_codes else "none")
    is_unknown = safe_state == "safe_unknown"
    is_active = safe_state in _ACTIVE_STATES
    missing_data = tuple(
        name for name in _NODE_STATE_FIELDS if _text(getattr(record, name, None)).lower() in _ABSENT
    )
    degraded_nodes = tuple(
        name for name in _NODE_STATE_FIELDS if "degrad" in _text(getattr(record, name, None)).lower()
    )
    if is_unknown:
        operator_text = "SAFE: unknown (no evaluation — target-only)"
    elif is_active:
        operator_text = f"SAFE: {safe_state} — {primary_reason}"
    elif safe_state == "safe_inactive":
        operator_text = "SAFE: inactive"
    else:
        operator_text = f"SAFE: {safe_state}"
    return SafeEvidence(
        safe_state=safe_state,
        primary_reason=primary_reason,
        is_active=is_active,
        is_unknown=is_unknown,
        blocked_commands=_commands(record.blocked_commands),
        allowed_commands=_commands(record.allowed_commands),
        exit_conditions=_commands(record.exit_conditions),
        missing_data=missing_data,
        degraded_nodes=degraded_nodes,
        reason_codes=reason_codes,
        read_only=True,
        operator_text=operator_text,
    )
