"""RCS Slice step 3: ORION consumes the EMITTED §14 record (body_if_records.rcs_commands);
it must NOT re-derive §14 evidence from raw propulsion/rcs; absent block => None (honest "no
telemetry", never an allowed claim).
"""

from __future__ import annotations

import dataclasses

from qiki.services.operator_console.orion_v.rcs_evidence import rcs_evidence_from_snapshot
from qiki.shared.models.rcs import rcs_command_from_runtime_state, rcs_record_from_mapping

_ENABLED = {"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}], "axis": "yaw"}
_HOT = {"nodes": [{"id": "rcs_left", "tripped": True}]}


def _emitted_snapshot(rcs, **kwargs):
    record = rcs_command_from_runtime_state(rcs, **kwargs)
    return {"body_if_records": {"rcs_commands": [dataclasses.asdict(record)]}}


def test_record_from_mapping_roundtrips_and_ignores_extra_keys() -> None:
    # thermal-hot record so thermal_nodes is non-empty — locks the JSON round-trip for ALL 4
    # tuple fields (active_clusters / required_thrusters / thermal_nodes / reason_codes).
    record = rcs_command_from_runtime_state(_ENABLED, thermal=_HOT)
    assert record.thermal_nodes  # precondition: thermal blockers present
    data = dataclasses.asdict(record)
    for name in ("required_thrusters", "active_clusters", "thermal_nodes", "reason_codes"):
        data[name] = list(data[name])  # JSON serializes the tuple fields to lists
    data["future_unknown_field"] = "ignored"  # forward-compat: must not break reconstruction
    assert rcs_record_from_mapping(data) == record


def test_consume_projects_from_emitted_record() -> None:
    evidence = rcs_evidence_from_snapshot(_emitted_snapshot(_ENABLED))
    assert evidence is not None
    assert evidence.rcs_mode == "yaw"
    assert evidence.validation_label == "allowed"
    assert evidence.is_allowed is True


def test_absent_block_is_none_not_rederived_from_raw() -> None:
    # Raw propulsion.rcs present, but NO emitted §14 record: must return None (honest "no
    # telemetry") — never re-derive an allowed validation from the raw RCS state.
    evidence = rcs_evidence_from_snapshot({"propulsion": {"rcs": _ENABLED}})
    assert evidence is None


def test_empty_block_is_none() -> None:
    assert rcs_evidence_from_snapshot({"body_if_records": {"rcs_commands": []}}) is None
