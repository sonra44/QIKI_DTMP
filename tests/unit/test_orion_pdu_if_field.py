"""PDU Slice step 4: §11 PDU evidence consumed into the F2 power view + visible line.

The collector builds one synthetic field `power.if_pdu_power.evidence` from the emitted IF
records (never re-derived from raw power); the systems power card surfaces it as a visible
line and keeps it (honest "no telemetry") even when the producer does not emit the block.
Decision B: the §11 field status is NEUTRAL — it does not escalate the operational chip.
"""

# ruff: noqa: E501  (power snapshot fixtures are intentionally one-line)

from __future__ import annotations

import dataclasses

from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector, ViewStatus
from qiki.services.operator_console.orion_v.screens.systems import _pdu_evidence_line
from qiki.shared.models.pdu import pdu_permissions_from_power_state

_POWER = {"loads_w": {"base": 5.0, "radar": 10.0}, "soc_pct": 80, "supercap_soc_pct": 50, "bus_v": 28, "bus_a": 2}


def _emitted_snapshot(power, thermal=None):
    records = pdu_permissions_from_power_state(power, thermal=thermal, safe_state="unknown")
    return {"body_if_records": {"pdu_permissions": [dataclasses.asdict(r) for r in records]}}


def _if_field(view):
    return next((f for f in view.fields if f.key == "power.if_pdu_power.evidence"), None)


def test_if_evidence_field_allowed_from_emitted_records() -> None:
    view = HardwareCollector().build_power(_emitted_snapshot(_POWER))
    field = _if_field(view)
    assert field is not None
    assert field.trust_status == "trusted"  # all loads allowed
    assert field.freshness == "fresh"
    assert field.status == ViewStatus.NO_DATA  # neutral, decision B (no chip escalation)
    assert "доказательство" in _pdu_evidence_line(view)


def test_if_evidence_field_missing_when_no_block_and_not_dropped() -> None:
    # Raw power present but NO emitted §11 block: the field must stay present + honest "no
    # telemetry" (never dropped, never re-derived allowed from raw power).
    view = HardwareCollector().build_power({"power": _POWER})
    field = _if_field(view)
    assert field is not None
    assert field.trust_status == "missing"
    assert field.freshness == "unknown"
    assert field.status == ViewStatus.NO_DATA
    # absent block is "no telemetry", not a §11 denial — must NOT invent a §11.7 reason
    assert field.reason_codes == ()
    assert "нет данных" in str(field.value)
    assert "нет данных" in _pdu_evidence_line(view)


def test_if_evidence_field_degraded_for_rejected_load_stays_neutral() -> None:
    power = {"loads_w": {"nbl": 5}, "nbl_allowed": False, "soc_pct": 80}
    view = HardwareCollector().build_power(_emitted_snapshot(power))
    field = _if_field(view)
    assert field is not None
    assert field.status == ViewStatus.NO_DATA  # neutral chip even when a load is rejected
    assert field.trust_status == "degraded"
    assert "внимание" in str(field.value)
