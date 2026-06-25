"""IF-NBL-001 step 1a: snapshot -> NBL record adapter (route a, honesty-bound).

The live q-sim snapshot publishes NBL only as power-budget facts and never an NBL packet.
The adapter must therefore project an honest record: packet layer not-implemented /
target-only, real power cost surfaced, everything unpublished left missing — never faked.
These tests drive the adapter through the real ORION projection (nbl_to_evidence).
"""
from __future__ import annotations

from qiki.services.operator_console.orion_v.evidence_adapters import snapshot_to_nbl_record
from qiki.services.operator_console.orion_v.nbl_evidence import nbl_to_evidence


def _evidence(snapshot):
    return nbl_to_evidence(snapshot_to_nbl_record(snapshot))


def test_packet_layer_is_never_shown_as_sent() -> None:
    # Even a fully "allowed/active" power state must not produce a delivered packet:
    # the feed carries no packet, so ORION must never claim one was sent.
    ev = _evidence({"power": {"nbl_active": True, "nbl_allowed": True, "nbl_budget_w": 20.0}})
    assert ev.status == "not_implemented"
    assert ev.is_sent is False
    assert "NBL_NOT_IMPLEMENTED" in ev.reason_codes
    assert "NBL_RULES_ONLY" in ev.reason_codes      # §17.10 target-only, always present
    assert ev.read_only is True
    assert "(target-only)" in ev.operator_text


def test_real_power_cost_surfaced_others_missing() -> None:
    ev = _evidence({"power": {"nbl_allowed": True, "nbl_budget_w": 20.0, "nbl_power_w": 12.0}})
    # budget preferred over draw (canon mapping order)
    assert "power=20.0" in ev.cost_label
    assert "SoC_cap=missing" in ev.cost_label
    assert ev.criticality == "missing"        # not published -> missing, not faked
    assert ev.payload_class == "missing"
    assert ev.delivery_confidence == "unknown"


def test_power_denied_adds_canon_reason() -> None:
    ev = _evidence({"power": {"nbl_active": True, "nbl_allowed": False, "nbl_budget_w": 0.0}})
    assert "NBL_PDU_DENIED" in ev.reason_codes      # canon: power gate denies NBL
    assert "NBL_NOT_IMPLEMENTED" in ev.reason_codes
    assert ev.is_sent is False
    assert "power=0.0" in ev.cost_label             # real value, not faked-missing


def test_empty_snapshot_all_missing_no_fake() -> None:
    ev = _evidence({})
    assert ev.status == "not_implemented"
    assert ev.is_sent is False
    assert ev.cost_label == "missing"               # no power -> cost missing
    assert ev.packet_id == "missing"
    assert "NBL_RULES_ONLY" in ev.reason_codes      # target-only baseline even with no power
    assert "NBL_PDU_DENIED" not in ev.reason_codes  # nbl_allowed absent != denied


def test_allowed_true_has_no_pdu_denied() -> None:
    ev = _evidence({"power": {"nbl_allowed": True, "nbl_budget_w": 5.0}})
    assert "NBL_PDU_DENIED" not in ev.reason_codes
