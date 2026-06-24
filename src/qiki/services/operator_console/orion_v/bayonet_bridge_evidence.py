"""IF-BAYONET-BRIDGE-001 (§9.11) read-only ORION surface of the bayonet power/data bridge.

Per §9.11 ORION must show bridge_state, mechanical_state, electrical_safety, passport_state,
power_direction, power_limit_W, data link status, thermal blockers, motion restrictions,
reason_codes. REQ-BAYONET-004 (P0): the bridge SHALL NOT be active before the full validation
chain. Defensive: bridge_active only when bridge_state==bridge_active AND no blocking reasons;
bridge_allowed is not active. Read-only; never opens, closes, or powers a bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BayonetBridgeEvidence:
    bayonet_id: str
    connected_object: str
    bridge_state: str
    mechanical_state: str
    electrical_safety: str
    passport_state: str
    power_direction: str
    power_limit_label: str
    data_link_state: str
    bridge_active: bool
    bridge_allowed: bool
    thermal_blockers: tuple[str, ...]
    motion_restriction: str
    reason_codes: tuple[str, ...]
    read_only: bool
    operator_text: str


def _text(value: Any, default: str = "missing") -> str:
    text = str(value or "").strip()
    return text if text else default


def bayonet_bridge_to_evidence(record: Any) -> BayonetBridgeEvidence:
    """Read-only ORION projection of one BayonetBridgeRecord (§9.11)."""
    bridge_state = _text(record.bridge_state, "bridge_disallowed")
    reason_codes = tuple(record.reason_codes or ())
    # Defensive (REQ-BAYONET-004): active only with the active state AND no blocking reason.
    bridge_active = bridge_state == "bridge_active" and not reason_codes
    bridge_allowed = bridge_state == "bridge_allowed" and not reason_codes
    thermal_blockers = tuple(r for r in reason_codes if "THERMAL" in r)
    motion_restriction = (
        "restricted"
        if bridge_state == "bridge_degraded" or "BRIDGE_ACTIVE_RESTRICTED_MOTION" in reason_codes
        else "none"
    )
    power_limit = record.power_limit_W
    power_limit_label = "missing" if power_limit is None else f"{float(power_limit):.0f}W"
    if bridge_active:
        operator_text = f"bridge: ACTIVE (power {_text(record.power_direction, 'none')})"
    elif bridge_allowed:
        operator_text = "bridge: allowed (not active)"
    else:
        operator_text = f"bridge: {bridge_state}" + (" — " + ", ".join(reason_codes) if reason_codes else "")
    return BayonetBridgeEvidence(
        bayonet_id=str(record.bayonet_id or "missing"),
        connected_object=_text(record.connected_object_id),
        bridge_state=bridge_state,
        mechanical_state=_text(record.mechanical_state),
        electrical_safety=_text(record.electrical_safety_state),
        passport_state=_text(record.passport_state),
        power_direction=_text(record.power_direction, "none"),
        power_limit_label=power_limit_label,
        data_link_state=_text(record.data_link_state),
        bridge_active=bridge_active,
        bridge_allowed=bridge_allowed,
        thermal_blockers=thermal_blockers,
        motion_restriction=motion_restriction,
        reason_codes=reason_codes,
        read_only=True,
        operator_text=operator_text,
    )
