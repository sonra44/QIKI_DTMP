"""Stage 9 / IF-BLACKBOX-001 — ORION recovery surface of blackbox records.

Canon §21: blackbox is the last memory of the body. §21.6 target-only — the canon states that
"describing blackbox relevance does not mean blackbox already writes". REQ (P0): ORION must mark
target-only/not-implemented, never present as runtime-ready. So a detected trigger is never shown
as recorded unless a real store record exists.
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import blackbox_record_from_runtime_event
from qiki.services.operator_console.orion_v.blackbox_evidence import blackbox_to_evidence


def _none():
    return blackbox_record_from_runtime_event(None)


def test_no_trigger_not_recorded() -> None:
    ev = blackbox_to_evidence(_none())
    assert ev.is_recorded is False
    assert ev.trigger_detected is False


def test_trigger_detected_but_not_recorded() -> None:
    rec = dataclasses.replace(
        _none(),
        trigger_event="critical_power_loss",
        reason_codes=("BLACKBOX_TARGET_ONLY", "BLACKBOX_NOT_RECORDED"),
    )
    ev = blackbox_to_evidence(rec)
    assert ev.trigger_detected is True
    assert ev.is_recorded is False
    assert "not recorded" in ev.operator_text.lower() or "target-only" in ev.operator_text.lower()


def test_recorded_demoted_when_not_recorded_reason() -> None:
    # Defensive: recorded_state=recorded but reason says not recorded -> demote.
    rec = dataclasses.replace(_none(), recorded_state="recorded", reason_codes=("BLACKBOX_NOT_RECORDED",))
    ev = blackbox_to_evidence(rec)
    assert ev.is_recorded is False


def test_recorded_positive_only_with_real_store() -> None:
    rec = dataclasses.replace(_none(), recorded_state="recorded", trigger_event="collision", reason_codes=())
    ev = blackbox_to_evidence(rec)
    assert ev.is_recorded is True


def test_empty_snapshots_not_reported_available() -> None:
    # CODEX_BLOCKER: empty {} snapshots must not be reported as available.
    ev = blackbox_to_evidence(_none())
    assert ev.available_snapshots == ()


def test_partial_snapshot_includes_only_present() -> None:
    rec = dataclasses.replace(_none(), power_snapshot={"battery_soc_pct": 50.0})
    ev = blackbox_to_evidence(rec)
    assert ev.available_snapshots == ("power_snapshot",)


def test_readonly() -> None:
    assert blackbox_to_evidence(_none()).read_only is True
