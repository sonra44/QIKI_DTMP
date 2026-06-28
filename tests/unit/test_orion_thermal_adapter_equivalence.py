"""Equivalence guard for the shared §13.7 thermal mapper (post DEFERRED-A).

The former console BOUNDED-TEMP mirror is gone: both the console alias
(orion_v.thermal_telemetry_adapter.thermal_records_from_snapshot) and the q_sim
re-export (world_model.thermal_telemetry_from_thermal_state) now resolve to the one
qiki.shared.models.thermal mapper. This asserts they stay field-by-field equal —
a drift here means a re-export was rewired wrong or the shared contract changed.
"""

from __future__ import annotations

import dataclasses

import pytest

from qiki.services.operator_console.orion_v.thermal_telemetry_adapter import (
    thermal_records_from_snapshot,
)
from qiki.services.q_sim_service.core.world_model import (
    thermal_telemetry_from_thermal_state,
)

THERMALS = [
    {"nodes": [{"id": "core", "temp_c": 25.0, "tripped": False, "warned": False, "warn_c": 80.0, "trip_c": 90.0, "hys_c": 5.0}]},  # noqa: E501
    {"nodes": [{"id": "core", "temp_c": 85.0, "warned": True, "warn_c": 80.0, "trip_c": 90.0}]},
    {"nodes": [{"id": "pdu", "temp_c": 95.0, "tripped": True, "warn_c": 80.0, "trip_c": 90.0}]},
    {"nodes": [{"id": "rcs_left", "temp_c": 82.0, "warn_c": 80.0}]},
    {"nodes": [{"id": "sensor_head", "temp_c": 100.0, "tripped": True}]},
    {"nodes": [{"id": "comms", "temp_c": 100.0, "tripped": True}]},
    {"nodes": [{"id": "transponder", "temp_c": 100.0, "tripped": True}]},
    {"nodes": [{"id": "bayonet1", "tripped": True}]},
    {"nodes": [{"id": "module_a", "tripped": True}]},
    {"nodes": [{"id": "core"}]},  # temp missing -> unknown
    {"nodes": [{"id": "core", "temp_c": 50.0}]},  # temp present, warn_c missing -> nominal
    {"nodes": [{"id": "core", "temp_c": 50.0, "warn_c": 0.0}]},  # warn_c == 0 -> nominal (warn > 0.0 branch)
    {"nodes": [{"id": "core", "temp_c": 50.0, "warn_c": -5.0}]},  # negative warn_c -> nominal
    {"nodes": [{"id": "core", "tripped": True}]},  # core critical -> blocked ("nbl",)
    {"nodes": [{"id": "rcs_left", "tripped": True}]},  # rcs critical -> blocked ("rcs",)
    {"nodes": [{"id": "core", "temp_c": 70.0, "warn_c": 80.0, "heat_active_w": 12.5, "cooldown_state": "active"}]},  # noqa: E501
    {"nodes": [{"id": "", "temp_c": 50}]},  # empty id -> skipped
    {"nodes": [42, "bad", None]},  # non-dict nodes -> skipped
    {"nodes": "bad"},  # non-list nodes -> treated as empty
    {"nodes": []},  # empty -> single missing record
    {},  # no thermal at all
    None,  # None thermal
]


@pytest.mark.parametrize("thermal", THERMALS)
def test_console_adapter_is_1to1_with_qsim_mapper(thermal) -> None:
    src = "equivalence-test"
    ts = 123.0
    console = thermal_records_from_snapshot(thermal, timestamp=ts, freshness="fresh", source=src)
    qsim = thermal_telemetry_from_thermal_state(thermal, timestamp=ts, freshness="fresh", source=src)
    assert len(console) == len(qsim)
    for c, q in zip(console, qsim):
        assert dataclasses.asdict(c) == dataclasses.asdict(q)
