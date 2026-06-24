"""Stage 8 / IF-NBL-001 — ORION operator surface of NBL emergency packets.

Canon §17.8: ORION must show criticality, payload class, cost, status, delivery uncertainty,
and reason_codes. §17.10: NBL is rules-only / target-only — a packet is never shown as sent
or delivered without a real source; delivery confidence stays as reported (unknown).
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import nbl_packet_from_runtime_state
from qiki.services.operator_console.orion_v.nbl_evidence import nbl_to_evidence


def _rules_only():
    return nbl_packet_from_runtime_state(None)


def test_rules_only_not_sent() -> None:
    ev = nbl_to_evidence(_rules_only())
    assert ev.is_sent is False
    assert ev.status == "not_implemented"
    assert any(r in ev.reason_codes for r in ("NBL_RULES_ONLY", "NBL_NOT_IMPLEMENTED"))


def test_allowed_is_not_sent() -> None:
    # packet_allowed must never be surfaced as sent (allowed != delivered).
    rec = dataclasses.replace(_rules_only(), status="packet_allowed", reason_codes=())
    ev = nbl_to_evidence(rec)
    assert ev.is_sent is False
    assert ev.status == "packet_allowed"


def test_delivery_uncertainty_surfaced() -> None:
    ev = nbl_to_evidence(_rules_only())
    assert ev.delivery_confidence == "unknown"


def test_sent_is_positive_only_when_status_sent() -> None:
    rec = dataclasses.replace(_rules_only(), status="packet_sent", reason_codes=())
    ev = nbl_to_evidence(rec)
    assert ev.is_sent is True


def test_sent_with_rules_only_reason_is_demoted() -> None:
    # CODEX_BLOCKER: a packet_sent status is not real delivery when rules-only/not-implemented.
    rec = dataclasses.replace(_rules_only(), status="packet_sent")  # keeps NBL_RULES_ONLY/NOT_IMPLEMENTED
    ev = nbl_to_evidence(rec)
    assert ev.is_sent is False
    assert "target-only" in ev.operator_text


def test_readonly() -> None:
    assert nbl_to_evidence(_rules_only()).read_only is True
