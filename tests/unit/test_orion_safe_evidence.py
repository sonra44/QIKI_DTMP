"""Stage 10 / IF-SAFE-001 — ORION operator surface of SAFE state.

Canon §22.7: ORION must show SAFE state, the primary reason_code, blocked commands, allowed
commands, exit conditions, missing data, and degraded nodes. REQ-SAFE-001 (P0): SAFE is a
physical survival mode, not a decorative alert. Defensive: safe_unknown (no real evaluation)
is never shown as inactive/nominal.
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import safe_state_from_runtime_state
from qiki.services.operator_console.orion_v.safe_evidence import safe_to_evidence


def _unknown():
    return safe_state_from_runtime_state()


def _state(**kw):
    return dataclasses.replace(_unknown(), **kw)


def test_unknown_not_shown_as_nominal() -> None:
    ev = safe_to_evidence(_unknown())
    assert ev.is_unknown is True
    assert ev.is_active is False
    assert "nominal" not in ev.operator_text.lower()
    assert "inactive" not in ev.operator_text.lower()


def test_active_safe_surfaced() -> None:
    rec = _state(
        SAFE_state="safe_limited",
        SAFE_reason="SAFE_POWER_LOW",
        reason_codes=("SAFE_POWER_LOW",),
        blocked_commands=("boost",),
    )
    ev = safe_to_evidence(rec)
    assert ev.is_active is True
    assert ev.primary_reason == "SAFE_POWER_LOW"
    assert "boost" in ev.blocked_commands


def test_lockdown_is_active() -> None:
    ev = safe_to_evidence(_state(SAFE_state="safe_lockdown", reason_codes=("SAFE_THERMAL_CRITICAL",)))
    assert ev.is_active is True


def test_inactive_is_not_unknown_not_active() -> None:
    ev = safe_to_evidence(_state(SAFE_state="safe_inactive", reason_codes=()))
    assert ev.is_unknown is False
    assert ev.is_active is False


def test_exit_conditions_kept_structured() -> None:
    # CODEX_BLOCKER: exit conditions must stay a structured tuple, not a repr string.
    rec = _state(exit_conditions=("exit_power_recovered", "exit_thermal_ok"))
    ev = safe_to_evidence(rec)
    assert isinstance(ev.exit_conditions, tuple)
    assert ev.exit_conditions == ("exit_power_recovered", "exit_thermal_ok")


def test_readonly() -> None:
    assert safe_to_evidence(_unknown()).read_only is True
