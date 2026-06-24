from __future__ import annotations

from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector
from qiki.services.operator_console.orion_v.hardware_view_model.types import ViewStatus
from qiki.services.operator_console.orion_v.hardware_view_model.utils import merge_status


def test_empty_snapshot_returns_no_data_for_all_subsystems() -> None:
    model = HardwareCollector().update({})

    assert model.system_status == ViewStatus.NO_DATA
    expected = {
        "power",
        "thermal",
        "comms",
        "docking",
        "navigation",
        "compute",
        "sensors",
        "hull",
        "shields",
        "propulsion",
    }
    assert set(model.subsystems.keys()) == expected
    assert all(subsystem.status == ViewStatus.NO_DATA for subsystem in model.subsystems.values())


def test_power_soc_critical_escalates_system_status() -> None:
    model = HardwareCollector().update({"power.soc": 10})

    assert model.subsystems["power"].status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_power_runtime_from_soc_and_draw_sets_warn() -> None:
    model = HardwareCollector().update(
        {
            "power.soc": 18,
            "power.draw_w": 150,
            "power.battery_wh": 500,
        }
    )
    power = model.subsystems["power"]
    runtime = next(field for field in power.fields if field.key == "power.runtime_min")

    assert runtime.value == 36.0
    assert runtime.status == ViewStatus.OK
    assert power.status == ViewStatus.WARN


def test_power_runtime_below_10_minutes_sets_crit() -> None:
    model = HardwareCollector().update(
        {
            "power.soc": 18,
            "power.draw_w": 600,
            "power.battery_wh": 500,
        }
    )
    power = model.subsystems["power"]
    runtime = next(field for field in power.fields if field.key == "power.runtime_min")

    assert runtime.value == 9.0
    assert runtime.status == ViewStatus.CRIT
    assert power.status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_power_bus_voltage_critical_sets_crit() -> None:
    model = HardwareCollector().update({"power.bus_v": 19})

    assert model.subsystems["power"].status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_power_draw_derived_from_bus_voltage_and_current() -> None:
    model = HardwareCollector().update(
        {
            "power.soc": 50,
            "power.bus_v": 24,
            "power.bus_a": 10,
            "power.battery_wh": 500,
        }
    )
    power = model.subsystems["power"]
    draw = next(field for field in power.fields if field.key == "power.draw_w")

    assert draw.value == 240.0
    assert draw.hint == "расчет по U*I"


def test_power_fields_keep_no_data_values_when_snapshot_empty() -> None:
    model = HardwareCollector().update({})
    power = model.subsystems["power"]
    required_keys = {
        "power.soc",
        "power.bus_v",
        "power.bus_a",
        "power.draw_w",
        "power.runtime_min",
        "power.limit_mode",
        "power.load_shedding",
        "power.shed_reasons",
        "power.dock_bridge_state",
        "power_budgeter.state",
        "pdu.state",
    }
    index = {field.key: field for field in power.fields}

    assert required_keys.issubset(index.keys())
    for key in required_keys:
        assert index[key].status == ViewStatus.NO_DATA
        assert index[key].value == "Нет данных"


def test_power_shed_reasons_field_uses_runtime_values() -> None:
    model = HardwareCollector().update(
        {
            "power.load_shedding": True,
            "power.shed_reasons": ["low_soc", "pdu_overcurrent"],
        }
    )
    power = model.subsystems["power"]
    reasons = next(field for field in power.fields if field.key == "power.shed_reasons")

    assert reasons.value == "low_soc, pdu_overcurrent"
    assert reasons.status in {ViewStatus.WARN, ViewStatus.CRIT}


def test_power_shed_reasons_field_marks_degraded_when_missing_while_shedding() -> None:
    model = HardwareCollector().update({"power.load_shedding": True})
    power = model.subsystems["power"]
    reasons = next(field for field in power.fields if field.key == "power.shed_reasons")

    assert reasons.value == "degraded: нет данных"
    assert reasons.status == ViewStatus.WARN


def test_propulsion_fuel_critical_sets_critical_status() -> None:
    model = HardwareCollector().update({"propulsion.fuel_pct": 8})
    propulsion = model.subsystems["propulsion"]

    assert propulsion.status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_propulsion_thruster_stuck_sets_critical_status() -> None:
    model = HardwareCollector().update({"rcs.forward.stuck": True})

    assert model.subsystems["propulsion"].status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_propulsion_motor_temp_critical_sets_critical_status() -> None:
    model = HardwareCollector().update({"motor_left.temp_c": 96})
    left_temp_field = next(field for field in model.subsystems["propulsion"].fields if field.key == "motor_left.temp_c")

    assert left_temp_field.status == ViewStatus.CRIT
    assert model.subsystems["propulsion"].status == ViewStatus.CRIT


def test_propulsion_burn_time_computed_when_fuel_and_rate_present() -> None:
    model = HardwareCollector().update(
        {
            "propulsion.fuel_pct": 50,
            "propulsion.fuel_total_g": 1200,
            "propulsion.fuel_rate_gs": 2,
        }
    )
    burn = next(field for field in model.subsystems["propulsion"].fields if field.key == "propulsion.burn_time_min")
    remaining = next(
        field for field in model.subsystems["propulsion"].fields if field.key == "propulsion.remaining_fuel_g"
    )

    assert remaining.value == 600.0
    assert burn.value == 5.0
    assert burn.status == ViewStatus.CRIT


def test_propulsion_fields_keep_no_data_values_when_snapshot_empty() -> None:
    model = HardwareCollector().update({})
    propulsion = model.subsystems["propulsion"]
    required_keys = {
        "propulsion.fuel_pct",
        "propulsion.fuel_rate_gs",
        "propulsion.remaining_fuel_g",
        "propulsion.burn_time_min",
        "propulsion.total_thrust_n",
        "propulsion.thruster.forward",
        "propulsion.thruster.aft",
        "propulsion.thruster.port",
        "propulsion.thruster.starboard",
        "propulsion.thruster.up",
        "propulsion.thruster.down",
        "motor_left.rpm",
        "motor_right.rpm",
    }
    index = {field.key: field for field in propulsion.fields}

    assert required_keys.issubset(index.keys())
    for key in required_keys:
        assert index[key].status == ViewStatus.NO_DATA
        assert index[key].value == "Нет данных"


def test_navigation_speed_is_derived_from_velocity_vector() -> None:
    model = HardwareCollector().update({"nav.vx": 3, "nav.vy": 4, "nav.vz": 12})
    navigation = model.subsystems["navigation"]
    speed_field = next(field for field in navigation.fields if field.key == "navigation.speed_mps")

    assert speed_field.value == 13.0
    assert speed_field.hint == "расчет по Vx/Vy/Vz"


def test_navigation_confidence_critical_sets_critical_status() -> None:
    model = HardwareCollector().update({"navigation.confidence": 0.1})

    assert model.subsystems["navigation"].status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_navigation_confidence_medium_sets_warn_status() -> None:
    model = HardwareCollector().update({"navigation.confidence": 0.6})
    confidence_field = next(
        field for field in model.subsystems["navigation"].fields if field.key == "navigation.confidence"
    )

    assert confidence_field.status == ViewStatus.WARN
    assert model.subsystems["navigation"].status == ViewStatus.WARN


def test_navigation_fields_keep_no_data_values_when_snapshot_empty() -> None:
    model = HardwareCollector().update({})
    navigation = model.subsystems["navigation"]
    required_keys = {
        "navigation.pos_x",
        "navigation.pos_y",
        "navigation.pos_z",
        "navigation.speed_mps",
        "navigation.vel_x",
        "navigation.vel_y",
        "navigation.vel_z",
        "navigation.heading_deg",
        "navigation.mode",
        "navigation.confidence",
        "navigation.quality",
    }
    index = {field.key: field for field in navigation.fields}

    assert required_keys.issubset(index.keys())
    for key in required_keys:
        assert index[key].status == ViewStatus.NO_DATA
        assert index[key].value == "Нет данных"


def test_docking_eta_is_calculated_from_distance_and_speed() -> None:
    model = HardwareCollector().update(
        {
            "docking.distance_m": 10,
            "docking.approach_mps": 0.2,
        }
    )
    docking = model.subsystems["docking"]
    eta = next(field for field in docking.fields if field.key == "docking.eta_contact")

    assert eta.value == "0:50"
    assert eta.status == ViewStatus.OK


def test_docking_alignment_critical_sets_critical_status() -> None:
    model = HardwareCollector().update({"docking.alignment_error_deg": 12})

    assert model.subsystems["docking"].status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_docking_speed_critical_sets_critical_status() -> None:
    model = HardwareCollector().update({"docking.approach_mps": 0.5})

    assert model.subsystems["docking"].status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_docking_sensor_offline_during_approach_sets_warn() -> None:
    model = HardwareCollector().update(
        {
            "docking.state": "approach",
            "sensor_docking.status": "offline",
        }
    )

    assert model.subsystems["docking"].status == ViewStatus.WARN


def test_docking_empty_snapshot_returns_no_data() -> None:
    model = HardwareCollector().update({})
    docking = model.subsystems["docking"]
    keys = {
        "docking.state",
        "docking.target",
        "docking.distance_m",
        "docking.approach_mps",
        "docking.alignment_error_deg",
        "docking.eta_contact",
        "docking.capture",
        "docking.lock",
        "sensor_docking.status",
    }
    index = {field.key: field for field in docking.fields}

    assert docking.status == ViewStatus.NO_DATA
    assert keys.issubset(index.keys())
    for key in keys:
        assert index[key].value == "Нет данных"
        assert index[key].status == ViewStatus.NO_DATA


def test_sensors_star_tracker_offline_sets_warn() -> None:
    model = HardwareCollector().update({"sensor_star_tracker.status": "offline"})

    assert model.subsystems["sensors"].status == ViewStatus.WARN


def test_sensors_two_critical_offline_sets_crit() -> None:
    model = HardwareCollector().update(
        {
            "imu_main.status": "offline",
            "sensor_star_tracker.status": "offline",
        }
    )

    assert model.subsystems["sensors"].status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_sensors_confidence_critical_sets_crit() -> None:
    model = HardwareCollector().update({"imu_main.confidence": 0.1})

    assert model.subsystems["sensors"].status == ViewStatus.CRIT


def test_sensors_summary_counts_online_degraded_offline() -> None:
    model = HardwareCollector().update(
        {
            "radar_360.status": "online",
            "lidar_front.status": "degraded",
            "imu_main.status": "offline",
        }
    )

    assert model.subsystems["sensors"].summary == "Сенсоры: 1 в работе, 1 деградации, 1 отключены"


def test_sensors_empty_snapshot_returns_no_data_for_all_required_sensors() -> None:
    model = HardwareCollector().update({})
    sensors = model.subsystems["sensors"]
    required = {
        "radar_360",
        "lidar_front",
        "lidar",
        "imu_main",
        "sensor_thermal",
        "sensor_radiation",
        "sensor_proximity",
        "sensor_solar",
        "sensor_star_tracker",
        "spectrometer",
        "magnetometer",
    }
    status_fields = [
        field for field in sensors.fields if field.key.startswith("sensors.") and field.key.endswith(".status")
    ]
    ids = {field.key.split(".")[1] for field in status_fields}

    assert required.issubset(ids)
    assert sensors.status == ViewStatus.NO_DATA
    assert sensors.summary == "Нет данных"
    assert all(field.value == "Нет данных" for field in status_fields)
    assert all(field.status == ViewStatus.NO_DATA for field in status_fields)


def test_sensors_disabled_sensor_plane_does_not_raise_subsystem_warning() -> None:
    model = HardwareCollector().update(
        {
            "sensor_plane.magnetometer.enabled": False,
            "sensor_plane.star_tracker.enabled": False,
            "sensor_plane.proximity.enabled": False,
            "sensor_plane.solar.enabled": False,
            "sensor_plane.imu.enabled": True,
            "sensor_plane.imu.status": "ok",
            "sensor_plane.imu.roll_rate_rps": 0.01,
            "sensor_plane.radiation.enabled": True,
            "sensor_plane.radiation.status": "ok",
            "sensor_plane.radiation.background_usvh": 0.0,
        }
    )

    sensors = model.subsystems["sensors"]
    assert sensors.status == ViewStatus.OK
    magnetometer = next(field for field in sensors.fields if field.key == "sensors.magnetometer.status")
    star_tracker = next(field for field in sensors.fields if field.key == "sensors.sensor_star_tracker.status")
    imu_value = next(field for field in sensors.fields if field.key == "sensors.imu_main.value")
    radiation_value = next(field for field in sensors.fields if field.key == "sensors.sensor_radiation.value")

    assert magnetometer.value == "Отключен"
    assert magnetometer.status == ViewStatus.OK
    assert star_tracker.value == "Отключен"
    assert star_tracker.status == ViewStatus.OK
    assert imu_value.status == ViewStatus.OK
    assert radiation_value.status == ViewStatus.OK


def test_sensors_real_plane_degraded_status_not_masked_as_ok() -> None:
    # HIGH-honesty: the live collector must read sensor_plane.<alias>.status, not silently fall
    # back to .enabled. A degraded sensor (enabled=True, status="warn") must show WARN, never OK
    # — an enabled-but-degraded sensor reported as OK is a dishonest perception surface.
    model = HardwareCollector().update(
        {
            "sensor_plane.imu.enabled": True,
            "sensor_plane.imu.status": "warn",
            "sensor_plane.imu.roll_rate_rps": 0.01,
        }
    )

    sensors = model.subsystems["sensors"]
    imu_status = next(field for field in sensors.fields if field.key == "sensors.imu_main.status")
    assert imu_status.status == ViewStatus.WARN


def test_sensors_real_plane_status_ok_stays_ok() -> None:
    # Negative: a genuinely healthy real-plane sensor must remain OK (no over-flagging).
    model = HardwareCollector().update(
        {
            "sensor_plane.imu.enabled": True,
            "sensor_plane.imu.status": "ok",
            "sensor_plane.imu.roll_rate_rps": 0.01,
        }
    )

    sensors = model.subsystems["sensors"]
    imu_status = next(field for field in sensors.fields if field.key == "sensors.imu_main.status")
    assert imu_status.status == ViewStatus.OK


def test_sensors_disabled_with_uninformative_status_stays_disabled_not_no_data() -> None:
    # A deliberately-disabled sensor that emits an uninformative status (e.g. star tracker
    # status="na", enabled=False) must still read as "Отключен" (intentionally off, OK), not be
    # misread as "Нет данных" via the status path.
    model = HardwareCollector().update(
        {
            "sensor_plane.star_tracker.enabled": False,
            "sensor_plane.star_tracker.status": "na",
        }
    )

    sensors = model.subsystems["sensors"]
    star_tracker = next(field for field in sensors.fields if field.key == "sensors.sensor_star_tracker.status")
    assert star_tracker.value == "Отключен"
    assert star_tracker.status == ViewStatus.OK


def test_sensors_star_tracker_attitude_error_surfaced() -> None:
    # D: star tracker attitude error is surfaced as its own additive field when present, so the
    # operator sees orientation error (not only star count). Real-plane key attitude_err_deg.
    model = HardwareCollector().update(
        {
            "sensor_plane.star_tracker.enabled": True,
            "sensor_plane.star_tracker.status": "ok",
            "sensor_plane.star_tracker.locked": True,
            "sensor_plane.star_tracker.attitude_err_deg": 1.5,
        }
    )

    sensors = model.subsystems["sensors"]
    att_err = next(field for field in sensors.fields if field.key == "sensors.sensor_star_tracker.attitude_err")
    assert att_err.value == 1.5
    assert att_err.status == ViewStatus.OK


def test_sensors_star_tracker_attitude_error_absent_is_no_data() -> None:
    # Additive field must degrade honestly to NO_DATA when the source is absent, never fabricate.
    model = HardwareCollector().update({"sensor_plane.star_tracker.enabled": True})

    sensors = model.subsystems["sensors"]
    att_err = next(field for field in sensors.fields if field.key == "sensors.sensor_star_tracker.attitude_err")
    assert att_err.status == ViewStatus.NO_DATA


def test_sensors_real_plane_crit_status_not_shown_as_no_data() -> None:
    # F-min: a sensor reporting status="crit" must surface as a concern (WARN), aligned with the
    # runtime mapper which already classes warn/crit as SENSOR_DEGRADED — never silently NO_DATA.
    model = HardwareCollector().update(
        {
            "sensor_plane.imu.enabled": True,
            "sensor_plane.imu.status": "crit",
            "sensor_plane.imu.roll_rate_rps": 0.01,
        }
    )

    sensors = model.subsystems["sensors"]
    imu_status = next(field for field in sensors.fields if field.key == "sensors.imu_main.status")
    assert imu_status.status == ViewStatus.WARN


def test_hull_integrity_pct_critical_sets_critical_status() -> None:
    model = HardwareCollector().update({"hull.integrity_pct": 35})

    assert model.subsystems["hull"].status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_hull_integrity_is_computed_from_hp_values() -> None:
    model = HardwareCollector().update({"hull.hp": 60, "hull.hp_max": 120})
    hull = model.subsystems["hull"]
    integrity = next(field for field in hull.fields if field.key == "hull.integrity_pct")

    assert integrity.value == 50.0
    assert integrity.status == ViewStatus.WARN


def test_hull_sector_damage_sets_worst_sector_and_critical_status() -> None:
    model = HardwareCollector().update({"hull.sector_damage": {"nose": 85}})
    hull = model.subsystems["hull"]
    worst = next(field for field in hull.fields if field.key == "hull.worst_sector")

    assert worst.value == "nose (85%)"
    assert hull.status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_shields_level_critical_sets_critical_status() -> None:
    model = HardwareCollector().update({"shields.level_pct": 8})

    assert model.subsystems["shields"].status == ViewStatus.CRIT
    assert model.system_status == ViewStatus.CRIT


def test_hull_and_shields_keep_no_data_values_when_snapshot_empty() -> None:
    model = HardwareCollector().update({})
    hull = model.subsystems["hull"]
    shields = model.subsystems["shields"]

    hull_index = {field.key: field for field in hull.fields}
    shields_index = {field.key: field for field in shields.fields}

    for key in {"hull.integrity_pct", "hull.worst_sector", "hull.sector_damage", "hull.stress"}:
        assert hull_index[key].status == ViewStatus.NO_DATA
        assert hull_index[key].value == "Нет данных"

    for key in {"shields.level_pct", "shields.state", "shields.draw_w", "shields.recharge", "shields.energy"}:
        assert shields_index[key].status == ViewStatus.NO_DATA
        assert shields_index[key].value == "Нет данных"


def test_merge_status_picks_highest_severity() -> None:
    assert merge_status(ViewStatus.OK, ViewStatus.WARN) == ViewStatus.WARN
    assert merge_status(ViewStatus.WARN, ViewStatus.CRIT) == ViewStatus.CRIT
    assert merge_status(ViewStatus.NO_DATA, ViewStatus.OK) == ViewStatus.OK
