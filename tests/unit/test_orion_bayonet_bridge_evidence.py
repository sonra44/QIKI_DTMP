"""Stage 12 / IF-BAYONET-BRIDGE-001 — ORION surface of bayonet power/data bridge.

Canon §9.11: ORION must show bridge_state, mechanical_state, electrical_safety, passport_state,
power_direction, power_limit_W, data link status, thermal blockers, motion restrictions,
reason_codes. REQ-BAYONET-004 (P0): bridge SHALL NOT be active before the full validation chain.
Defensive: bridge_active only when bridge_state==bridge_active AND no blocking reasons;
bridge_allowed is not active; hard_lock/soft_capture/proximity are not active.
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import bayonet_bridge_from_runtime_state
from qiki.services.operator_console.orion_v.bayonet_bridge_evidence import bayonet_bridge_to_evidence


def _disallowed():
    return bayonet_bridge_from_runtime_state(None)


def _state(**kw):
    return dataclasses.replace(_disallowed(), **kw)


def test_no_chain_not_active() -> None:
    ev = bayonet_bridge_to_evidence(_disallowed())
    assert ev.bridge_active is False
    assert ev.bridge_allowed is False
    assert ev.bridge_state == "bridge_disallowed"


def test_allowed_is_not_active() -> None:
    ev = bayonet_bridge_to_evidence(_state(bridge_state="bridge_allowed", reason_codes=()))
    assert ev.bridge_allowed is True
    assert ev.bridge_active is False


def test_active_positive_only_with_full_chain() -> None:
    ev = bayonet_bridge_to_evidence(_state(bridge_state="bridge_active", reason_codes=()))
    assert ev.bridge_active is True


def test_active_with_blocker_is_demoted() -> None:
    # REQ-BAYONET-004: a bridge_active claim with a blocking reason is not honored.
    ev = bayonet_bridge_to_evidence(_state(bridge_state="bridge_active", reason_codes=("BRIDGE_PDU_DENIED",)))
    assert ev.bridge_active is False


def test_allowed_with_blocker_is_demoted() -> None:
    # CODEX_BLOCKER / REQ-BAYONET-004: a bridge_allowed claim with a blocker is not honored.
    ev = bayonet_bridge_to_evidence(_state(bridge_state="bridge_allowed", reason_codes=("BRIDGE_PDU_DENIED",)))
    assert ev.bridge_allowed is False
    assert "allowed (not active)" not in ev.operator_text


def test_thermal_blocker_surfaced() -> None:
    ev = bayonet_bridge_to_evidence(_state(bridge_state="bridge_disallowed", reason_codes=("BRIDGE_THERMAL_BLOCK",)))
    assert "BRIDGE_THERMAL_BLOCK" in ev.thermal_blockers


def test_readonly() -> None:
    assert bayonet_bridge_to_evidence(_disallowed()).read_only is True
