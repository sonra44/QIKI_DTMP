"""Stage 5 / IF-SENSOR-TELEM-001 — ORION operator surface of sensor telemetry.

Canon §15.7: ORION must show source, freshness, trust, conflict, missing status, and
hypothesis/reconstruction marking — per sensor. REQ-SENSOR-001 (P0): a value without a
source is not physical truth and must be marked missing/hypothesis. Conservative: a
non-trusted sensor is never summarized as trusted; absent values stay "no value".
"""

from __future__ import annotations

import dataclasses

from qiki.services.q_sim_service.core.world_model import sensor_telemetry_from_sensor_plane
from qiki.services.operator_console.orion_v.sensor_evidence import sensor_to_evidence


def _missing():
    return sensor_telemetry_from_sensor_plane(None)[0]


def _sensor(**kw):
    return dataclasses.replace(_missing(), **kw)


def test_trusted_and_missing_not_summarized_as_all_trusted() -> None:
    # operator_text must not claim "all trusted" when a sensor is missing.
    trusted = _sensor(sensor_id="imu", trust_status="trusted", value=1.0, source="imu")
    missing = _sensor(sensor_id="radiation", trust_status="missing")
    ev = sensor_to_evidence((trusted, missing))
    assert "all trusted" not in ev.operator_text
    assert "radiation" in ev.missing_sensors


def test_conflicting_sensor_flagged() -> None:
    # "conflicting" implies real sources disagree, so it carries a source.
    ev = sensor_to_evidence(
        (_sensor(sensor_id="star_tracker", trust_status="conflicting", source="star_tracker", value=1.0),)
    )
    assert "star_tracker" in ev.conflicting_sensors
    assert ev.sensors[0].is_conflicting is True


def test_sourceless_trusted_is_demoted() -> None:
    # REQ-SENSOR-001 (P0): a value with no source is not physical truth, even if the
    # input record claims trusted. ORION must demote it at the surface.
    rec = _sensor(sensor_id="solar", value=72.0, source="", trust_status="trusted", unit="percent")
    ev = sensor_to_evidence((rec,))
    sensor = ev.sensors[0]
    assert sensor.is_trusted is False
    assert sensor.is_missing is True
    assert sensor.value_label == "no value"
    assert "all trusted" not in ev.operator_text


def test_hypothesis_sensor_marked() -> None:
    ev = sensor_to_evidence((_sensor(sensor_id="proximity", trust_status="hypothesis"),))
    assert "proximity" in ev.hypothesis_sensors
    assert ev.sensors[0].is_hypothesis is True


def test_missing_value_not_presented_as_truth() -> None:
    ev = sensor_to_evidence((_missing(),))  # value None, trust missing, source missing
    sensor = ev.sensors[0]
    assert sensor.is_missing is True
    assert sensor.value_label == "no value"


def test_all_trusted_positive() -> None:
    trusted = _sensor(sensor_id="imu", trust_status="trusted", value=1.0, source="imu", reason_codes=())
    ev = sensor_to_evidence((trusted,))
    assert ev.operator_text == "sensors: all trusted"


def test_trusted_with_blocking_reason_is_demoted() -> None:
    # Audit #1: a trusted sensor carrying a blocking reason_code must not stay "trusted".
    rec = _sensor(sensor_id="imu", trust_status="trusted", value=1.0, source="imu", reason_codes=("SENSOR_DEGRADED",))
    ev = sensor_to_evidence((rec,))
    assert ev.sensors[0].is_trusted is False
    assert "all trusted" not in ev.operator_text


def test_readonly() -> None:
    ev = sensor_to_evidence((_missing(),))
    assert ev.read_only is True
