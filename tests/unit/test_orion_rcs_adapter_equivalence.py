"""Equivalence + backcompat guard for the shared §14 RCS mapper (RCS Slice step 1).

RcsCommandRecord + rcs_command_from_runtime_state moved to qiki.shared.models.rcs;
world_model re-exports them for q_sim consumers/tests. This asserts the shared mapper and
the world_model re-export resolve to the SAME mapper field-by-field across the §14 gate
scenarios (CURRENT behavior — the mapper does not emit COM_INVALID/INERTIA_UNMODELED, so
those are not asserted), and that the backcompat import path still works.
"""

# ruff: noqa: E501  (parametrized rcs/power/thermal snapshots are intentionally one-line per case)

from __future__ import annotations

import dataclasses
from dataclasses import fields

import pytest

from qiki.services.q_sim_service.core.world_model import (
    RcsCommandRecord as WMRcsCommandRecord,
)
from qiki.services.q_sim_service.core.world_model import (
    rcs_command_from_runtime_state as wm_mapper,
)
from qiki.shared.models.rcs import (
    BAYONET_SOFT_CAPTURE_ONLY,
    BRIDGE_ACTIVE_RESTRICTED_MOTION,
    CAP_LOW,
    RCS_CLUSTER_HOT,
    RCS_UNAVAILABLE,
    SAFE_LOCKED,
    THRUST_MAP_MISSING,
    TORQUE_MAP_MISSING,
    WORKING_MASS_LOW,
    RcsCommandRecord,
    rcs_command_from_runtime_state,
)

_ENABLED = {"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}]}

_HOT = {"nodes": [{"id": "rcs_left", "tripped": True}]}
_RCS = {"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}], "axis": "yaw"}

# Each case: (rcs, kwargs)
CASES = [
    (None, {}),  # not a dict -> defaults
    ({}, {}),  # empty -> disabled / maps missing
    (_RCS, {}),  # nominal allowed
    ({"enabled": False}, {}),  # disabled -> RCS_UNAVAILABLE + maps missing
    ({"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}]}, {"thermal": _HOT}),  # cluster hot
    ({"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}]}, {"power": {"supercap_soc_pct": 0.0}}),  # cap low
    ({"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}]}, {"docking": {"state": "soft_capture"}}),  # bayonet soft capture
    ({"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}]}, {"power": {"dock_connected": True}}),  # bridge active restricted
    ({"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}]}, {"safe_state": "locked"}),  # safe locked
    ({"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}], "propellant_kg": 0.0}, {}),  # working mass low (empty)
    ({"enabled": True, "thrusters": [{"index": 1, "cluster_id": "L"}], "propellant_kg": 1.0}, {"working_mass_required": 5.0}),  # working mass below required
    (_RCS, {"command_id": "cmd1", "requested_delta_v": 2.0, "duration_s": 3.0, "CoM_class": "A", "inertia_class": "B"}),  # full passthrough fields
]


@pytest.mark.parametrize("rcs,kwargs", CASES)
def test_shared_rcs_mapper_is_1to1_with_world_model(rcs, kwargs) -> None:
    shared = rcs_command_from_runtime_state(rcs, **kwargs)
    wm = wm_mapper(rcs, **kwargs)
    assert dataclasses.asdict(shared) == dataclasses.asdict(wm)


def test_backcompat_record_reexport_is_shared_class() -> None:
    assert WMRcsCommandRecord is RcsCommandRecord
    # §14.4 contract: the record still carries all 18 required fields.
    assert len(fields(RcsCommandRecord)) == 18


def test_rcs_mapper_golden_behavior() -> None:
    # Non-tautological golden assertions of CURRENT mapper behavior (the equivalence test above
    # is a backcompat/shape guard only — shared and wm_mapper are the same function after re-export).
    nominal = rcs_command_from_runtime_state(_RCS)
    assert nominal.validation_status == "allowed"
    assert nominal.reason_codes == ()

    for rejected in (rcs_command_from_runtime_state(None), rcs_command_from_runtime_state({"enabled": False})):
        assert rejected.validation_status == "rejected"
        assert RCS_UNAVAILABLE in rejected.reason_codes
        assert THRUST_MAP_MISSING in rejected.reason_codes
        assert TORQUE_MAP_MISSING in rejected.reason_codes
        assert rejected.Thrust_Map_status == "missing"
        assert rejected.Torque_Map_status == "missing"

    hot = rcs_command_from_runtime_state(_ENABLED, thermal=_HOT)
    assert RCS_CLUSTER_HOT in hot.reason_codes
    assert hot.thermal_nodes == ("rcs_left",)

    cap_low = rcs_command_from_runtime_state(_ENABLED, power={"supercap_soc_pct": 0.0})
    assert CAP_LOW in cap_low.reason_codes

    bridge = rcs_command_from_runtime_state(_ENABLED, power={"dock_connected": True})
    assert BRIDGE_ACTIVE_RESTRICTED_MOTION in bridge.reason_codes
    assert bridge.bridge_state == "active_unrated"

    soft = rcs_command_from_runtime_state(_ENABLED, docking={"state": "soft_capture"})
    assert BAYONET_SOFT_CAPTURE_ONLY in soft.reason_codes
    assert soft.bayonet_state == "soft_capture"

    locked = rcs_command_from_runtime_state(_ENABLED, safe_state="locked")
    assert SAFE_LOCKED in locked.reason_codes

    empty_prop = rcs_command_from_runtime_state({**_ENABLED, "propellant_kg": 0.0})
    assert WORKING_MASS_LOW in empty_prop.reason_codes
    below_required = rcs_command_from_runtime_state({**_ENABLED, "propellant_kg": 1.0}, working_mass_required=5.0)
    assert WORKING_MASS_LOW in below_required.reason_codes

    passthrough = rcs_command_from_runtime_state(
        _RCS, command_id="cmd1", requested_delta_v=2.0, duration_s=3.0, CoM_class="A", inertia_class="B"
    )
    assert passthrough.command_id == "cmd1"
    assert passthrough.requested_delta_v == 2.0
    assert passthrough.duration_s == 3.0
    assert passthrough.CoM_class == "A"
    assert passthrough.inertia_class == "B"

    # CURRENT behavior: missing CoM/inertia classes do NOT emit COM_INVALID / INERTIA_UNMODELED
    # (the mapper carries the class fields but does not validate them — that is a later task).
    missing_classes = rcs_command_from_runtime_state(_RCS, CoM_class="missing", inertia_class="missing")
    assert "COM_INVALID" not in missing_classes.reason_codes
    assert "INERTIA_UNMODELED" not in missing_classes.reason_codes
