from __future__ import annotations

from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector, ViewStatus


def _field_value(model, key: str):
    return next(field for field in model.subsystems["thermal"].fields if field.key == key).value


def _field_status(model, key: str) -> ViewStatus:
    return next(field for field in model.subsystems["thermal"].fields if field.key == key).status


def test_thermal_core_warn_status() -> None:
    model = HardwareCollector().update({"thermal.core_c": 90})
    core = next(field for field in model.subsystems["thermal"].fields if field.key == "thermal.core_c")

    assert core.status == ViewStatus.WARN


def test_thermal_core_crit_status() -> None:
    model = HardwareCollector().update({"thermal.core_c": 96})
    core = next(field for field in model.subsystems["thermal"].fields if field.key == "thermal.core_c")

    assert core.status == ViewStatus.CRIT
    assert model.subsystems["thermal"].status == ViewStatus.CRIT


def test_thermal_trend_rising_current_prev() -> None:
    collector = HardwareCollector()
    collector.update({"thermal.core_c": 70})
    model = collector.update({"thermal.core_c": 72})

    assert _field_value(model, "thermal.trend") == "растёт"


def test_thermal_trend_falling_current_prev() -> None:
    collector = HardwareCollector()
    collector.update({"thermal.core_c": 72})
    model = collector.update({"thermal.core_c": 71})

    assert _field_value(model, "thermal.trend") == "падает"


def test_thermal_trend_missing_without_previous_value() -> None:
    model = HardwareCollector().update({"thermal.core_c": 70})

    assert _field_value(model, "thermal.trend") == "Нет данных"


def test_thermal_empty_snapshot_returns_no_data_fields() -> None:
    model = HardwareCollector().update({})
    thermal = model.subsystems["thermal"]
    index = {field.key: field for field in thermal.fields}

    assert thermal.status == ViewStatus.NO_DATA
    assert index["thermal.core_c"].status == ViewStatus.NO_DATA
    assert index["thermal.core_c"].value == "Нет данных"
    assert index["thermal.trend"].value == "Нет данных"


def test_thermal_fields_use_thermal_nodes_for_warn_trip_thresholds() -> None:
    model = HardwareCollector().update(
        {
            "thermal": {
                "nodes": [
                    {
                        "id": "core",
                        "temp_c": 86.0,
                        "warned": True,
                        "tripped": False,
                        "warn_c": 80.0,
                        "trip_c": 90.0,
                        "hys_c": 5.0,
                    },
                    {
                        "id": "pdu",
                        "temp_c": 98.0,
                        "warned": False,
                        "tripped": True,
                        "warn_c": 85.0,
                        "trip_c": 95.0,
                        "hys_c": 5.0,
                    },
                ]
            }
        }
    )

    assert _field_value(model, "thermal.core_state") == "WARN"
    assert _field_value(model, "thermal.warn_nodes") == "core"
    assert _field_value(model, "thermal.trip_nodes") == "pdu"
    assert _field_value(model, "thermal.core_warn_c") == 80.0
    assert _field_value(model, "thermal.core_trip_c") == 90.0
    assert _field_value(model, "thermal.core_hys_c") == 5.0
    assert _field_status(model, "thermal.trip_nodes") == ViewStatus.CRIT


def test_thermal_nodes_empty_lists_render_as_dashes_with_ok_status() -> None:
    model = HardwareCollector().update(
        {
            "thermal": {
                "nodes": [
                    {
                        "id": "core",
                        "temp_c": 70.0,
                        "warned": False,
                        "tripped": False,
                        "warn_c": 80.0,
                        "trip_c": 90.0,
                        "hys_c": 5.0,
                    }
                ]
            }
        }
    )

    assert _field_value(model, "thermal.warn_nodes") == "—"
    assert _field_value(model, "thermal.trip_nodes") == "—"
    assert _field_status(model, "thermal.warn_nodes") == ViewStatus.OK
    assert _field_status(model, "thermal.trip_nodes") == ViewStatus.OK


def test_thermal_delta_requires_actual_radiator_temperature() -> None:
    model = HardwareCollector().update(
        {
            "temp_core_c": -18.0,
            "temp_external_c": -60.0,
            "thermal": {
                "nodes": [
                    {
                        "id": "core",
                        "temp_c": -18.0,
                        "warned": False,
                        "tripped": False,
                        "warn_c": 80.0,
                        "trip_c": 90.0,
                        "hys_c": 5.0,
                    }
                ]
            },
        }
    )

    assert _field_value(model, "thermal.radiator_c") == -60.0
    assert _field_value(model, "thermal.delta_c") == "Нет данных"
    assert _field_status(model, "thermal.delta_c") == ViewStatus.NO_DATA
    assert model.subsystems["thermal"].status == ViewStatus.OK
