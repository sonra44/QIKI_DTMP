"""Slice A step 4: §15 sensor evidence is CONSUMED into the F2 sensors view + visible line.

The collector builds one synthetic field `sensors.if_sensor_telem.evidence` from the emitted
IF records (never re-derived from raw); the systems card surfaces it as a visible line and
keeps it (honest "no telemetry") even when the producer does not emit the block.
"""

# ruff: noqa: E501  (sensor_plane fixtures are intentionally one-line per sensor)

from __future__ import annotations

import dataclasses

from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector, ViewStatus
from qiki.services.operator_console.orion_v.screens.systems import _sensors_evidence_line
from qiki.shared.models.sensors import sensor_telemetry_from_sensor_plane

_FULL_PLANE = {
    "imu": {"enabled": True, "roll_rate_rps": 0.1, "pitch_rate_rps": 0.0, "yaw_rate_rps": -0.1, "status": "ok"},
    "radiation": {"enabled": True, "background_usvh": 5.0, "status": "ok"},
    "proximity": {"enabled": True, "min_range_m": 10.0, "contacts": 1},
    "solar": {"enabled": True, "illumination_pct": 80},
    "star_tracker": {"enabled": True, "locked": True, "attitude_err_deg": 0.5, "status": "ok"},
    "magnetometer": {"enabled": True, "field_ut": {"x": 1, "y": 2, "z": 3}},
}


def _emitted_snapshot(sensor_plane):
    records = sensor_telemetry_from_sensor_plane(sensor_plane, timestamp=1.0)
    return {"body_if_records": {"sensor_telemetry": [dataclasses.asdict(r) for r in records]}}


def _if_field(view):
    return next((f for f in view.fields if f.key == "sensors.if_sensor_telem.evidence"), None)


def test_if_evidence_field_trusted_from_emitted_records() -> None:
    view = HardwareCollector().build_sensors(_emitted_snapshot(_FULL_PLANE))
    field = _if_field(view)
    assert field is not None
    assert field.trust_status == "trusted"
    assert field.freshness == "fresh"
    # visible F2 line surfaces the consumed evidence
    assert "доказательство" in _sensors_evidence_line(view)


def test_if_evidence_field_missing_when_no_block_and_not_dropped() -> None:
    # Raw sensor_plane present but NO emitted IF block: the §15 field must stay present and
    # honest "no telemetry" (never silently dropped, never re-derived green from raw).
    view = HardwareCollector().build_sensors({"sensor_plane": _FULL_PLANE})
    field = _if_field(view)
    # Decision B: field stays present + visible + inspector metadata missing, but NEUTRAL
    # status (NO_DATA) so it does not change operational subsystem severity.
    assert field is not None
    assert field.trust_status == "missing"
    assert field.freshness == "unknown"
    assert field.reason_codes == ("SENSOR_MISSING",)
    assert field.status == ViewStatus.NO_DATA
    assert "нет данных" in str(field.value)
    assert "нет данных" in _sensors_evidence_line(view)  # no-telemetry line still visible on F2


def test_present_but_degraded_records_carry_trust_but_stay_neutral() -> None:
    # Decision B: emitted records that are not all trusted carry the worst trust + an attention
    # value/line for the §19 inspector, but the §15 field status stays NEUTRAL (NO_DATA) — it
    # must NOT escalate the operational chip severity in this patch.
    plane = {"imu": {"enabled": True, "roll_rate_rps": 0.1, "pitch_rate_rps": 0.0, "yaw_rate_rps": -0.1, "status": "ok"}}
    view = HardwareCollector().build_sensors(_emitted_snapshot(plane))  # imu present, others missing
    field = _if_field(view)
    assert field is not None
    assert field.status == ViewStatus.NO_DATA  # neutral — no chip escalation
    assert field.trust_status == "missing"  # worst trust among present records
    assert "внимание" in str(field.value)
    assert "внимание" in _sensors_evidence_line(view)
