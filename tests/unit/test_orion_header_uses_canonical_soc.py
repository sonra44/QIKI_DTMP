import pytest


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "source": "q_sim_service",
        "timestamp": "2026-02-10T00:00:00.000Z",
        "ts_unix_ms": 1770681600000,
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "velocity": 0.0,
        "heading": 0.0,
        "attitude": {"roll_rad": 0.0, "pitch_rad": 0.0, "yaw_rad": 0.0},
        # Legacy alias intentionally differs from canonical value.
        "battery": 88.0,
        "hull": {"integrity": 100.0},
        "power": {
            "soc_pct": 42.0,
            "power_in_w": 0.0,
            "power_out_w": 0.0,
            "bus_v": 28.0,
            "bus_a": 0.0,
        },
        "thermal": {"nodes": [{"id": "core", "temp_c": 20.0}]},
        "radiation_usvh": 0.0,
        "temp_external_c": -50.0,
        "temp_core_c": 20.0,
    }


def test_orion_header_uses_power_soc_pct_not_legacy_battery() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionHeader

    hdr = OrionHeader()
    hdr.update_from_telemetry(
        _sample_payload(),
        nats_connected=True,
        telemetry_age_s=1.0,
        telemetry_freshness_label="Fresh",
        telemetry_freshness_kind="fresh",
    )

    assert "42" in str(hdr.battery)
