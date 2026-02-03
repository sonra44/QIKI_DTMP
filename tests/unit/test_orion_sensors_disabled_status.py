import time

import pytest


def _sample_telemetry_payload_with_disabled_sensors() -> dict:
    # Minimal TelemetrySnapshotModel-compatible payload + sensor_plane extension.
    # Keep values within validators; no mocks beyond strict N/A semantics.
    return {
        "schema_version": 1,
        "source": "q_sim_service",
        "timestamp": "2026-02-03T00:00:00.000Z",
        "ts_unix_ms": 1770076800000,
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "velocity": 0.0,
        "heading": 0.0,
        "attitude": {"roll_rad": 0.0, "pitch_rad": 0.0, "yaw_rad": 0.0},
        "battery": 50.0,
        "hull": {"integrity": 100.0},
        "power": {
            "soc_pct": 50.0,
            "power_in_w": 0.0,
            "power_out_w": 0.0,
            "bus_v": 28.0,
            "bus_a": 0.0,
        },
        "thermal": {"nodes": [{"id": "core", "temp_c": 20.0}]},
        "radiation_usvh": 0.0,
        "temp_external_c": -60.0,
        "temp_core_c": 20.0,
        "sensor_plane": {
            "enabled": True,
            "star_tracker": {
                "enabled": False,
                "locked": None,
                "status": "na",
                "reason": "disabled",
                "attitude_err_deg": None,
            },
            "magnetometer": {
                "enabled": False,
                "field_ut": None,
            },
            "imu": {
                "enabled": True,
                "ok": True,
                "status": "ok",
                "reason": "ok",
                "roll_rate_rps": 0.0,
                "pitch_rate_rps": 0.0,
                "yaw_rate_rps": 0.0,
            },
            "proximity": {"enabled": False, "min_range_m": None, "contacts": None},
            "solar": {"enabled": False, "illumination_pct": None},
            "radiation": {
                "enabled": True,
                "status": "ok",
                "reason": "within limits",
                "background_usvh": 0.0,
                "dose_total_usv": 0.0,
                "limits": {"warn_usvh": 1.0, "crit_usvh": 2.0},
            },
        },
    }


@pytest.mark.asyncio
async def test_orion_sensors_show_disabled_in_compact_mode() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp
    from qiki.services.operator_console.ui import i18n as I18N

    app = OrionApp()

    class _FakeDataTable:
        id = "sensors-table"

        def clear(self) -> None:
            return

        def add_row(self, *_cells, key: str | None = None) -> None:  # noqa: ANN001
            return

    def _fake_query_one(selector, _cls=None):  # noqa: ANN001
        if selector == "#sensors-table":
            return _FakeDataTable()
        raise LookupError(selector)

    app.query_one = _fake_query_one  # type: ignore[method-assign]
    app._sensors_compact_enabled = lambda: True  # type: ignore[method-assign]
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-1",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="info",
            payload=_sample_telemetry_payload_with_disabled_sensors(),
        )
    )

    app._render_sensors_table()

    assert app._sensors_by_key["star_tracker"]["status"] == I18N.bidi("Disabled", "Отключено")
    assert app._sensors_by_key["magnetometer"]["status"] == I18N.bidi("Disabled", "Отключено")

