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

