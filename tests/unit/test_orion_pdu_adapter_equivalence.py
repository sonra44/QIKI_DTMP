"""Equivalence + backcompat guard for the shared §11 PDU mapper (PDU Slice step 1).

PduPermissionRecord + pdu_permissions_from_power_state moved to qiki.shared.models.pdu;
world_model re-exports them for q_sim consumers/tests. This asserts the shared mapper and
the world_model re-export resolve to the SAME mapper field-by-field across the §11 gate
scenarios, and that the backcompat import path still works.
"""

# ruff: noqa: E501  (parametrized power/thermal snapshots are intentionally one-line per case)

from __future__ import annotations

import dataclasses
from dataclasses import fields

import pytest

from qiki.services.q_sim_service.core.world_model import (
    PduPermissionRecord as WMPduPermissionRecord,
)
from qiki.services.q_sim_service.core.world_model import (
    pdu_permissions_from_power_state as wm_mapper,
)
from qiki.shared.models.pdu import PduPermissionRecord, pdu_permissions_from_power_state

_THERMAL_BLOCK = {"nodes": [{"id": "pdu", "tripped": True}]}

# Each case: (power, thermal, safe_state, duration_s)
CASES = [
    (None, None, "unknown", None),  # not a dict -> missing record
    ({"loads_w": {}}, None, "unknown", None),  # no loads -> missing record
    ({"loads_w": {"base": 5.0, "radar": 10.0}, "soc_pct": 80, "supercap_soc_pct": 50, "bus_v": 28, "bus_a": 2}, None, "unknown", None),  # nominal multi-load
    ({"loads_w": {"radar": 10}, "shed_loads": ["radar"], "shed_reasons": ["low_soc"]}, None, "unknown", None),  # shed + low soc
    ({"loads_w": {"radar": 10}, "throttled_loads": ["radar"]}, None, "unknown", None),  # throttled -> allowed_limited
    ({"loads_w": {"radar": 10}}, _THERMAL_BLOCK, "unknown", None),  # thermal block via node
    ({"loads_w": {"base": 5}}, None, "locked", None),  # SAFE locked
    ({"loads_w": {"nbl": 20}, "supercap_soc_pct": 0.0}, None, "unknown", 5.0),  # peak cap low (0%)
    ({"loads_w": {"base": 5}, "faults": ["BUS_V_ZERO"], "bus_v": 0.0}, None, "unknown", None),  # bus unstable
    ({"loads_w": {"rcs": 30}, "supercap_soc_pct": 10, "supercap_capacity_wh": 1.0}, None, "unknown", 100.0),  # peak energy over cap
    ({"loads_w": {"radar": 10}, "shed_loads": "radar", "shed_reasons": ""}, None, "unknown", None),  # _string_tuple bare string / empty
    ({"loads_w": {"nbl": 5}, "nbl_allowed": False}, None, "unknown", None),  # nbl rejected
    ({"loads_w": {"radar": 10}, "pdu_throttled": True}, None, "unknown", None),  # pdu throttling state
    ({"loads_w": {"radar": 10}, "faults": ["PDU_OVERCURRENT"]}, None, "unknown", None),  # overcurrent
]


@pytest.mark.parametrize("power,thermal,safe_state,duration_s", CASES)
def test_shared_pdu_mapper_is_1to1_with_world_model(power, thermal, safe_state, duration_s) -> None:
    shared = pdu_permissions_from_power_state(power, thermal=thermal, safe_state=safe_state, duration_s=duration_s)
    wm = wm_mapper(power, thermal=thermal, safe_state=safe_state, duration_s=duration_s)
    assert len(shared) == len(wm)
    for s, w in zip(shared, wm):
        assert dataclasses.asdict(s) == dataclasses.asdict(w)


def test_backcompat_record_reexport_is_shared_class() -> None:
    assert WMPduPermissionRecord is PduPermissionRecord
    # §11.5 contract: the record still carries all 14 required fields.
    assert len(fields(PduPermissionRecord)) == 14
