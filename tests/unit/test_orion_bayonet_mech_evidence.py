"""Stage 11 / IF-BAYONET-MECH-001 — ORION surface of bayonet mechanical state.

Canon §8.10: ORION must show bayonet_id, state, lock quality, structural status, connected
object, bridge availability, motion restrictions, reason_codes. ADR-0009: bridge requires
mechanical hard lock AND structural check passed — soft_capture / magnetic_pre_align / unknown
are not bridge-allowed; degraded_lock requires restricted motion. Defensive: unknown is never
shown as locked/safe.
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import bayonet_mech_from_docking_state
from qiki.services.operator_console.orion_v.bayonet_mech_evidence import bayonet_mech_to_evidence


def _unknown():
    return bayonet_mech_from_docking_state(None)


def _state(**kw):
    return dataclasses.replace(_unknown(), **kw)


def test_unknown_not_locked() -> None:
    ev = bayonet_mech_to_evidence(_unknown())
    assert ev.is_unknown is True
    assert ev.bridge_available is False
    assert ev.motion_restriction == "unknown"
    assert "locked" not in ev.operator_text.lower()


def test_structural_passed_bridge_available() -> None:
    ev = bayonet_mech_to_evidence(_state(state="structural_check_passed", reason_codes=()))
    assert ev.bridge_available is True


def test_hard_lock_without_structural_has_no_bridge() -> None:
    # ADR-0009: a hard lock alone is not enough; structural check is required.
    ev = bayonet_mech_to_evidence(
        _state(state="mechanical_hard_lock", structural_rating="unknown", reason_codes=())
    )
    assert ev.bridge_available is False


def test_soft_capture_restricted_and_no_bridge() -> None:
    ev = bayonet_mech_to_evidence(
        _state(state="soft_capture", reason_codes=("BAYONET_SOFT_CAPTURE_ONLY",))
    )
    assert ev.bridge_available is False
    assert ev.motion_restriction == "restricted"


def test_readonly() -> None:
    assert bayonet_mech_to_evidence(_unknown()).read_only is True
