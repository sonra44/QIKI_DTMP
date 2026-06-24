"""Stage 7 / IF-RCS-CMD-001 — ORION operator surface of RCS commands.

Canon §14.7: ORION must show requested burn, allowed/rejected, active blockers, map status,
thermal blockers, CoM/inertia class, expected effect, and effect confirmation state.
ADR-0015: ACK/validation is NOT effect confirmation — with no real effect loop, effect
confirmation stays missing/target-only and is never shown as confirmed.
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import rcs_command_from_runtime_state
from qiki.services.operator_console.orion_v.rcs_evidence import rcs_to_evidence


def _rejected():
    return rcs_command_from_runtime_state(None)


def _allowed():
    return dataclasses.replace(
        _rejected(),
        validation_status="allowed",
        reason_codes=(),
        Thrust_Map_status="available",
        Torque_Map_status="available",
    )


def test_rejected_command_surfaced() -> None:
    ev = rcs_to_evidence(_rejected())
    assert ev.is_allowed is False
    assert ev.validation_label == "rejected"
    assert ev.active_blockers  # reason codes present


def test_effect_confirmation_never_confirmed() -> None:
    # ADR-0015: no real effect loop -> effect confirmation must stay missing/target-only.
    ev = rcs_to_evidence(_allowed())
    assert ev.is_allowed is True
    assert ev.effect_confirmation in ("missing", "target-only")
    assert ev.effect_confirmation != "confirmed"


def test_allowed_operator_text_states_effect_not_confirmed() -> None:
    ev = rcs_to_evidence(_allowed())
    assert "missing" in ev.operator_text or "target-only" in ev.operator_text


def test_thermal_blocker_flagged() -> None:
    rec = dataclasses.replace(_rejected(), validation_status="rejected", reason_codes=("RCS_CLUSTER_HOT",))
    ev = rcs_to_evidence(rec)
    assert "RCS_CLUSTER_HOT" in ev.thermal_blockers


def test_allowed_but_maps_missing_is_demoted() -> None:
    # CODEX_BLOCKER: ORION must not honor an allowed claim when thrust/torque maps are missing.
    rec = dataclasses.replace(_rejected(), validation_status="allowed", reason_codes=())
    ev = rcs_to_evidence(rec)
    assert ev.is_allowed is False
    assert "allowed (validation)" not in ev.operator_text


def test_allowed_with_blocker_reason_is_demoted() -> None:
    # An allowed claim with an active blocker reason is contradictory -> demote.
    rec = dataclasses.replace(
        _rejected(),
        validation_status="allowed",
        reason_codes=("CAP_LOW",),
        Thrust_Map_status="available",
        Torque_Map_status="available",
    )
    ev = rcs_to_evidence(rec)
    assert ev.is_allowed is False
    assert "CAP_LOW" in ev.active_blockers


def test_readonly() -> None:
    assert rcs_to_evidence(_rejected()).read_only is True
