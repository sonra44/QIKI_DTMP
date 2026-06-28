"""PDU Slice step 3: ORION consumes the EMITTED §11 records (body_if_records.pdu_permissions);
it must NOT re-derive §11 evidence from raw power; absent block => honest "no load permission
telemetry".
"""

from __future__ import annotations

import dataclasses

from qiki.services.operator_console.orion_v.pdu_evidence import pdu_evidence_from_snapshot
from qiki.shared.models.pdu import pdu_permissions_from_power_state, pdu_record_from_mapping

_POWER = {"loads_w": {"base": 5.0, "radar": 10.0}, "soc_pct": 80, "supercap_soc_pct": 50, "bus_v": 28, "bus_a": 2}


def _emitted_snapshot(power, thermal=None):
    records = pdu_permissions_from_power_state(power, thermal=thermal, safe_state="unknown")
    return {"body_if_records": {"pdu_permissions": [dataclasses.asdict(r) for r in records]}}


def test_record_from_mapping_roundtrips_and_ignores_extra_keys() -> None:
    record = pdu_permissions_from_power_state(_POWER, safe_state="unknown")[0]
    data = dataclasses.asdict(record)
    data["reason_codes"] = list(data["reason_codes"])  # JSON serializes tuple -> list
    data["future_unknown_field"] = "ignored"  # forward-compat: must not break reconstruction
    assert pdu_record_from_mapping(data) == record


def test_consume_projects_from_emitted_records() -> None:
    evidence = pdu_evidence_from_snapshot(_emitted_snapshot(_POWER))
    assert len(evidence.loads) == 2  # base + radar consumed from emitted records
    assert "PDU:" in evidence.operator_text


def test_absent_if_block_is_honest_no_telemetry_not_rederived_from_raw() -> None:
    # Raw power present, but NO emitted §11 block: evidence must be honest "no load permission
    # telemetry" — it must NOT re-derive allowed/cleared loads from the raw power picture.
    evidence = pdu_evidence_from_snapshot({"power": _POWER})
    assert evidence.loads == ()
    assert "no load permission telemetry" in evidence.operator_text


def test_empty_if_block_is_honest_no_telemetry() -> None:
    evidence = pdu_evidence_from_snapshot({"body_if_records": {"pdu_permissions": []}})
    assert evidence.loads == ()
    assert "no load permission telemetry" in evidence.operator_text
