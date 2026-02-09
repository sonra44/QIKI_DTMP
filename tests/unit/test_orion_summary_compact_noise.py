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
            "soc_pct": 50.0,
            "power_in_w": 20.0,
            "power_out_w": 40.0,
            "bus_v": 28.0,
            "bus_a": 1.0,
        },
        "thermal": {"nodes": [{"id": "core", "temp_c": 21.0}]},
        "radiation_usvh": 0.0,
        "temp_external_c": -60.0,
        "temp_core_c": 20.0,
        "sim_state": {"running": True, "paused": False, "speed": 1.0, "fsm_state": "RUNNING"},
        "sensor_plane": {
            "radiation": {
                "enabled": True,
                "status": "ok",
                "background_usvh": 0.3,
                "limits": {"warn_usvh": 1.0, "crit_usvh": 2.0},
            }
        },
        "comms": {"xpdr": {"mode": "MODE_C", "allowed": True}},
    }


def test_orion_summary_compact_hides_default_trust_token(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp

    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "1")
    app = OrionApp()
    app.nats_connected = True
    app._events_filter_text = None
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-compact-trust",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="info",
            payload=_sample_payload(),
        )
    )

    blocks = app._build_summary_blocks()
    actions = next(b for b in blocks if b.block_id == "actions_incidents")
    assert "trust=" not in str(actions.value)


def test_orion_summary_compact_keeps_non_default_trust_token(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp

    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "1")
    app = OrionApp()
    app.nats_connected = True
    app._events_filter_text = "verified"
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-compact-trust-nondefault",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="info",
            payload=_sample_payload(),
        )
    )

    blocks = app._build_summary_blocks()
    actions = next(b for b in blocks if b.block_id == "actions_incidents")
    assert "trust=verified" in str(actions.value)


def test_orion_summary_compact_uses_short_threats_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("textual")
    from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp

    monkeypatch.setenv("ORION_SUMMARY_COMPACT_DEFAULT", "1")
    app = OrionApp()
    app.nats_connected = True
    payload = _sample_payload()
    payload["sensor_plane"]["radiation"]["status"] = "warn"
    app._snapshots.put(
        EventEnvelope(
            event_id="telemetry-compact-threats",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="warn",
            payload=payload,
        )
    )

    blocks = app._build_summary_blocks()
    threats = next(b for b in blocks if b.block_id == "threats")
    value = str(threats.value)
    assert "rad=" in value
    assert "cause=" in value
    assert "bg=" not in value
