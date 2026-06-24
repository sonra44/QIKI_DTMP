from dataclasses import fields

from qiki.services.q_sim_service.core.world_model import (
    SensorTelemetryRecord,
    sensor_telemetry_from_sensor_plane,
)
from qiki.services.q_sim_service.service import QSimService
from qiki.shared.config_models import QSimServiceConfig


def test_sensor_plane_included_in_telemetry_payload() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    payload = qsim._build_telemetry_payload(qsim.world_model.get_state())
    assert "sensor_plane" in payload
    sp = payload.get("sensor_plane")
    assert isinstance(sp, dict)
    assert "imu" in sp
    assert "radiation" in sp


def test_radiation_dose_integrates_when_enabled() -> None:
    cfg = QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO")
    qsim = QSimService(cfg)

    payload0 = qsim._build_telemetry_payload(qsim.world_model.get_state())
    dose0 = ((payload0.get("sensor_plane") or {}).get("radiation") or {}).get("dose_total_usv")

    # Advance simulation by 10 seconds: dose must not decrease.
    qsim.world_model.step(10.0)
    payload1 = qsim._build_telemetry_payload(qsim.world_model.get_state())
    dose1 = ((payload1.get("sensor_plane") or {}).get("radiation") or {}).get("dose_total_usv")

    assert dose0 is None or dose1 is None or float(dose1) >= float(dose0) - 1e-12


def test_if_sensor_telem_record_exposes_canon_fields() -> None:
    record_fields = {field.name for field in fields(SensorTelemetryRecord)}

    assert record_fields == {
        "sensor_id",
        "sensor_class",
        "measured_quantity",
        "value",
        "unit",
        "timestamp",
        "freshness",
        "latency",
        "accuracy",
        "source",
        "trust_status",
        "field_of_view",
        "mount_point",
        "blocked_by_module",
        "affected_by_motion",
        "affected_by_field",
        "affected_by_emcon",
        "thermal_state",
        "reason_codes",
    }


def test_if_sensor_telem_mapper_projects_real_sensor_values_per_sensor() -> None:
    qsim = QSimService(QSimServiceConfig(sim_tick_interval=1, sim_sensor_type=1, log_level="INFO"))
    qsim.world_model.step(1.0)
    state = qsim.world_model.get_state()

    records = sensor_telemetry_from_sensor_plane(
        state.get("sensor_plane"),
        timestamp=qsim.world_model.sim_time_epoch_ts(),
    )

    by_id = {record.sensor_id: record for record in records}
    assert {"imu", "radiation", "proximity", "solar", "star_tracker", "magnetometer"} <= set(by_id)

    imu = by_id["imu"]
    assert imu.sensor_class == "motion"
    assert imu.measured_quantity == "angular_rate"
    assert imu.unit == "rad/s"
    assert imu.source == "q_sim_service.world_model.sensor_plane"
    assert imu.trust_status == "trusted"
    assert imu.freshness == "fresh"
    assert isinstance(imu.value, dict)
    assert set(imu.value) == {"roll_rate_rps", "pitch_rate_rps", "yaw_rate_rps"}

    radiation = by_id["radiation"]
    assert radiation.measured_quantity == "radiation_background"
    assert radiation.unit == "uSv/h"
    assert radiation.source == "q_sim_service.world_model.sensor_plane"
    assert radiation.trust_status in {"trusted", "degraded"}


def test_if_sensor_telem_mapper_marks_missing_when_no_sensor_source() -> None:
    records = sensor_telemetry_from_sensor_plane(None)

    assert len(records) == 1
    record = records[0]
    assert record.sensor_id == "missing"
    assert record.value is None
    assert record.source == "missing"
    assert record.trust_status == "missing"
    assert record.freshness == "unknown"
    assert record.reason_codes == ("SENSOR_MISSING",)


def test_if_sensor_telem_mapper_does_not_trust_value_without_source() -> None:
    records = sensor_telemetry_from_sensor_plane(
        {"enabled": True, "solar": {"enabled": True, "illumination_pct": 72.0}},
        source="",
    )

    solar = next(record for record in records if record.sensor_id == "solar")
    assert solar.value is None
    assert solar.source == "missing"
    assert solar.trust_status == "missing"
    assert "SENSOR_MISSING" in solar.reason_codes
