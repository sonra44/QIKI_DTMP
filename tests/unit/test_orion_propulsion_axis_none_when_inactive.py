import time

import pytest


def _sample_telemetry_payload_rcs_inactive_no_axis() -> dict:
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
        "power": {"soc_pct": 50.0, "power_in_w": 0.0, "power_out_w": 0.0, "bus_v": 28.0, "bus_a": 0.0},
        "thermal": {"nodes": [{"id": "core", "temp_c": 20.0}]},
        "radiation_usvh": 0.0,
        "temp_external_c": -60.0,
        "temp_core_c": 20.0,
        "propulsion": {
            "rcs": {
                "enabled": True,
                "active": False,
                "throttled": False,
                "axis": None,
                "command_pct": 0.0,
                "time_left_s": 0.0,
                "propellant_kg": 12.0,
                "power_w": 0.0,
                "net_force_n": [0.0, 0.0, 0.0],
                "net_torque_nm": [0.0, 0.0, 0.0],
                "thrusters": [],
            }
        },
    }


@pytest.mark.asyncio
async def test_orion_propulsion_axis_is_none_when_inactive() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp
    from qiki.services.operator_console.ui import i18n as I18N

    app = OrionApp()

    class _FakeDataTable:
        id = "propulsion-table"

        def clear(self) -> None:
            return

        def add_row(self, *_cells, key: str | None = None) -> None:  # noqa: ANN001
            return

    def _fake_query_one(selector, _cls=None):  # noqa: ANN001
        if selector == "#propulsion-table":
            return _FakeDataTable()
        raise LookupError(selector)

    app.query_one = _fake_query_one  # type: ignore[method-assign]
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-1",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="info",
            payload=_sample_telemetry_payload_rcs_inactive_no_axis(),
        )
    )

    app._render_propulsion_table()

    assert app._propulsion_by_key["rcs_axis"]["value"] == I18N.bidi("none", "нет")
    assert app._propulsion_by_key["rcs_axis"]["status"] == I18N.bidi("Normal", "Норма")

