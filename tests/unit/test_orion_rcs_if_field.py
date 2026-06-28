"""RCS Slice step 4: §14 RCS command evidence consumed into the F2 propulsion view + line.

The collector builds one synthetic field `propulsion.if_rcs_cmd.evidence` from the emitted IF
record (never re-derived from raw propulsion); the systems propulsion card surfaces it as a
visible line and keeps it (honest "no telemetry") even when the producer does not emit it.
Decision B: the §14 field status is NEUTRAL — it does not escalate the operational chip.
"""

# ruff: noqa: E501  (rcs snapshot fixtures are intentionally one-line)

from __future__ import annotations

import dataclasses

from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector, ViewStatus
from qiki.services.operator_console.orion_v.screens.systems import _rcs_evidence_line
from qiki.shared.models.rcs import rcs_command_from_runtime_state

_ENABLED = {"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}], "axis": "yaw"}


def _emitted_snapshot(rcs, **kwargs):
    record = rcs_command_from_runtime_state(rcs, **kwargs)
    return {"body_if_records": {"rcs_commands": [dataclasses.asdict(record)]}}


def _if_field(view):
    return next((f for f in view.fields if f.key == "propulsion.if_rcs_cmd.evidence"), None)


def test_if_evidence_field_allowed_from_emitted_record() -> None:
    view = HardwareCollector().build_propulsion(_emitted_snapshot(_ENABLED))
    field = _if_field(view)
    assert field is not None
    assert field.trust_status == "trusted"  # validation allowed
    assert field.freshness == "fresh"
    assert field.status == ViewStatus.NO_DATA  # neutral, decision B (no chip escalation)
    assert "доказательство" in _rcs_evidence_line(view)


def test_if_evidence_field_missing_when_no_record_and_not_dropped() -> None:
    # Raw propulsion.rcs present but NO emitted §14 record: the field must stay present + honest
    # "no telemetry" (never dropped, never re-derived as allowed from raw).
    view = HardwareCollector().build_propulsion({"propulsion": {"rcs": _ENABLED}})
    field = _if_field(view)
    assert field is not None
    assert field.trust_status == "missing"
    assert field.freshness == "unknown"
    assert field.status == ViewStatus.NO_DATA
    assert field.reason_codes == ()  # absent is "no telemetry", not a §14 blocker
    assert "нет данных" in str(field.value)
    assert "нет данных" in _rcs_evidence_line(view)


def test_if_evidence_field_degraded_for_disabled_rcs_stays_neutral() -> None:
    view = HardwareCollector().build_propulsion(_emitted_snapshot({"enabled": False}))
    field = _if_field(view)
    assert field is not None
    assert field.status == ViewStatus.NO_DATA  # neutral chip even when RCS is rejected
    assert field.trust_status == "degraded"
    assert "внимание" in str(field.value)
    assert "RCS_UNAVAILABLE" in field.reason_codes
