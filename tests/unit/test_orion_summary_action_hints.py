import time

import pytest


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "source": "q_sim_service",
        "timestamp": "2026-02-10T00:00:00.000Z",
        "ts_unix_ms": 1770681600000,
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "velocity": 2.0,
        "heading": 90.0,
        "attitude": {"roll_rad": 0.0, "pitch_rad": 0.0, "yaw_rad": 0.1},
        "battery": 50.0,
        "hull": {"integrity": 100.0},
        "power": {
            "soc_pct": 45.0,
            "faults": ["PDU_OVERCURRENT"],
            "pdu_throttled": True,
            "load_shedding": True,
            "shed_loads": ["radar"],
            "power_in_w": 210.0,
            "power_out_w": 185.0,
            "bus_v": 28.1,
            "bus_a": 7.8,
        },
        "thermal": {"nodes": [{"id": "core", "temp_c": 95.0, "tripped": True}]},
        "radiation_usvh": 0.0,
        "temp_external_c": -60.0,
        "temp_core_c": 20.0,
        "sensor_plane": {
            "radiation": {
                "enabled": True,
                "status": "crit",
                "background_usvh": 2.5,
                "limits": {"warn_usvh": 1.0, "crit_usvh": 2.0},
            }
        },
    }


def test_summary_action_hints_compact_are_short(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp

    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "1")
    app = OrionApp()
    app.nats_connected = True
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-hints-compact",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="warn",
            payload=_sample_payload(),
        )
    )

    blocks = app._build_summary_blocks()
    energy = next(b for b in blocks if b.block_id == "energy")
    threats = next(b for b in blocks if b.block_id == "threats")
    actions = next(b for b in blocks if b.block_id == "actions_incidents")

    assert "next=pause+power" in str(energy.value)
    assert "next=pause+radiation" in str(threats.value)
    assert "Next/Действие=pause+threat" in str(actions.value)


def test_summary_action_hints_verbose_keep_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp

    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "0")
    app = OrionApp()
    app.nats_connected = True
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-hints-verbose",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="warn",
            payload=_sample_payload(),
        )
    )

    blocks = app._build_summary_blocks()
    energy = next(b for b in blocks if b.block_id == "energy")
    threats = next(b for b in blocks if b.block_id == "threats")

    assert "next=pause + inspect power faults" in str(energy.value)
    assert "next=pause + execute radiation protocol" in str(threats.value)
