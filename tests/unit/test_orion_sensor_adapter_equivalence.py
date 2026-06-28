"""Equivalence + backcompat guard for the shared §15 sensor mapper (Slice A extract).

SensorTelemetryRecord + sensor_telemetry_from_sensor_plane moved to
qiki.shared.models.sensors; world_model re-exports them for q_sim consumers/tests.
This asserts the shared mapper and the world_model re-export resolve to the SAME
mapper field-by-field, and that the backcompat import path still works.
"""

# ruff: noqa: E501  (parametrized sensor_plane snapshots are intentionally one-line per case)

from __future__ import annotations

import dataclasses
from dataclasses import fields

import pytest

from qiki.services.q_sim_service.core.world_model import (
    SensorTelemetryRecord as WMSensorTelemetryRecord,
)
from qiki.services.q_sim_service.core.world_model import (
    sensor_telemetry_from_sensor_plane as wm_mapper,
)
from qiki.shared.models.sensors import SensorTelemetryRecord, sensor_telemetry_from_sensor_plane

# Each case: (sensor_plane, thermal).
CASES = [
    (None, None),  # not a dict -> single missing record
    ("bad", None),  # not a dict -> single missing record
    ({}, None),  # empty plane -> all sensors missing/no-source
    ({"imu": {"enabled": True, "roll_rate_rps": 0.1, "pitch_rate_rps": 0.0, "yaw_rate_rps": -0.1, "status": "ok"}}, None),  # imu trusted
    ({"imu": {"enabled": True, "roll_rate_rps": 0.1, "pitch_rate_rps": 0.0, "yaw_rate_rps": -0.1, "status": "warn"}}, None),  # imu degraded
    ({"radiation": {"enabled": True, "background_usvh": 12.0, "status": "crit"}}, None),  # radiation degraded
    ({"star_tracker": {"enabled": True, "locked": False, "attitude_err_deg": 3.0, "status": "ok"}}, None),  # blind
    ({"magnetometer": {"enabled": True, "field_ut": {"x": 1, "y": 2, "z": 3}}}, None),  # field dict value
    ({"proximity": {"enabled": True, "min_range_m": 5.0, "contacts": 2}}, None),  # proximity
    ({"solar": {"enabled": True, "illumination_pct": 80}}, None),  # solar
    ({"imu": {"enabled": True, "roll_rate_rps": 0.1, "pitch_rate_rps": 0.0, "yaw_rate_rps": -0.1, "status": "ok"}}, {"nodes": [{"id": "sensor_head", "tripped": True}]}),  # thermal-blocked sensor node
]


@pytest.mark.parametrize("sensor_plane,thermal", CASES)
def test_shared_sensor_mapper_is_1to1_with_world_model(sensor_plane, thermal) -> None:
    ts = 123.0
    shared = sensor_telemetry_from_sensor_plane(sensor_plane, thermal=thermal, timestamp=ts, freshness="fresh")
    wm = wm_mapper(sensor_plane, thermal=thermal, timestamp=ts, freshness="fresh")
    assert len(shared) == len(wm)
    for s, w in zip(shared, wm):
        assert dataclasses.asdict(s) == dataclasses.asdict(w)


def test_backcompat_record_reexport_is_shared_class() -> None:
    # world_model.SensorTelemetryRecord must be the shared class (re-export, not a copy).
    assert WMSensorTelemetryRecord is SensorTelemetryRecord
    # §15.4 contract: the record still carries all 19 required fields.
    assert len(fields(SensorTelemetryRecord)) == 19
