"""Slice A step 3: ORION consumes the EMITTED §15 records (body_if_records), it must NOT
re-derive §15 evidence from raw sensor_plane; absent block => honest "no telemetry".
"""

from __future__ import annotations

import dataclasses

from qiki.services.operator_console.orion_v.sensor_evidence import sensor_evidence_from_snapshot
from qiki.shared.models.sensors import (
    sensor_record_from_mapping,
    sensor_telemetry_from_sensor_plane,
)

_IMU_PLANE = {"imu": {"enabled": True, "roll_rate_rps": 0.1, "pitch_rate_rps": 0.0, "yaw_rate_rps": -0.1, "status": "ok"}}  # noqa: E501


def _emitted_snapshot(sensor_plane, thermal=None):
    records = sensor_telemetry_from_sensor_plane(sensor_plane, thermal=thermal, timestamp=1.0)
    return {"body_if_records": {"sensor_telemetry": [dataclasses.asdict(r) for r in records]}}


def test_record_from_mapping_roundtrips_and_ignores_extra_keys() -> None:
    rec = sensor_telemetry_from_sensor_plane(_IMU_PLANE, timestamp=1.0)[0]
    data = dataclasses.asdict(rec)
    data["reason_codes"] = list(data["reason_codes"])  # JSON serializes tuple -> list
    data["future_unknown_field"] = "ignored"  # forward-compat: must not break reconstruction
    assert sensor_record_from_mapping(data) == rec


def test_consume_projects_from_emitted_records() -> None:
    evidence = sensor_evidence_from_snapshot(_emitted_snapshot(_IMU_PLANE))
    by_id = {sensor.sensor_id: sensor for sensor in evidence.sensors}
    assert "imu" in by_id
    assert by_id["imu"].trust_status == "trusted"


def test_absent_if_block_is_honest_missing_not_rederived_from_raw() -> None:
    # Raw sensor_plane present, but NO emitted §15 block: evidence must be honest "no
    # telemetry" — it must NOT re-derive trusted sensors from the raw operational plane.
    evidence = sensor_evidence_from_snapshot({"sensor_plane": _IMU_PLANE})
    assert evidence.sensors == ()
    assert "no telemetry" in evidence.operator_text


def test_empty_if_block_is_honest_missing() -> None:
    evidence = sensor_evidence_from_snapshot({"body_if_records": {"sensor_telemetry": []}})
    assert evidence.sensors == ()
    assert "no telemetry" in evidence.operator_text
