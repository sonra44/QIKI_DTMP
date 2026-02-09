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
        "power": {"soc_pct": 50.0, "power_in_w": 20.0, "power_out_w": 40.0, "bus_v": 28.0, "bus_a": 1.0},
        "thermal": {"nodes": [{"id": "core", "temp_c": 21.0}]},
        "radiation_usvh": 0.0,
        "temp_external_c": -60.0,
        "temp_core_c": 20.0,
        "sim_state": {"running": True, "paused": False, "speed": 1.0, "fsm_state": "RUNNING"},
        "propulsion": {"rcs": {"active": True, "throttled": False}},
    }


def test_summary_health_motion_compact_short_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp

    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "1")
    app = OrionApp()
    app.nats_connected = True
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-health-motion-compact",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="info",
            payload=_sample_payload(),
        )
    )
    blocks = app._build_summary_blocks()
    health = next(b for b in blocks if b.block_id == "health")
    motion = next(b for b in blocks if b.block_id == "motion_safety")
    assert "state=" in str(health.value)
    assert "link=" in str(health.value)
    assert "v=" in str(motion.value)
    assert "hdg=" in str(motion.value)
    assert "rcs=" in str(motion.value)


def test_summary_health_motion_verbose_keeps_original_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp

    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "0")
    app = OrionApp()
    app.nats_connected = True
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-health-motion-verbose",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="info",
            payload=_sample_payload(),
        )
    )
    blocks = app._build_summary_blocks()
    motion = next(b for b in blocks if b.block_id == "motion_safety")
    assert "V=" in str(motion.value)
    assert "Hdg=" in str(motion.value)
    assert "RCS=" in str(motion.value)
