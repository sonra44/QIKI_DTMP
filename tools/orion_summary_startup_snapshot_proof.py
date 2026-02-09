#!/usr/bin/env python3
"""Deterministic startup snapshot proof for ORION Summary Tier A."""

from __future__ import annotations

import os
import time

import pytest

pytest.importorskip("textual")

from qiki.services.operator_console.main_orion import EventEnvelope, OrionApp


LEGACY_BASELINE_BLOCKS = (
    "Telemetry link",
    "Telemetry age",
    "Power systems",
    "CPU usage",
    "Memory usage",
    "BIOS",
    "Mission control",
    "Last event age",
    "Events filters",
    "Events trust filter",
)


def _sample_payload() -> dict:
    return {
        "schema_version": 1,
        "source": "q_sim_service",
        "timestamp": "2026-02-10T00:00:00.000Z",
        "ts_unix_ms": 1770681600000,
        "position": {"x": 0.0, "y": 0.0, "z": 12.0},
        "velocity": 2.0,
        "heading": 90.0,
        "attitude": {"roll_rad": 0.0, "pitch_rad": 0.0, "yaw_rad": 0.1},
        "battery": 50.0,
        "hull": {"integrity": 100.0},
        "power": {
            "soc_pct": 18.5,
            "power_in_w": 20.0,
            "power_out_w": 48.0,
            "bus_v": 28.0,
            "bus_a": 1.2,
            "load_shedding": True,
            "shed_loads": ["camera", "thermal_aux"],
            "pdu_throttled": True,
            "faults": [],
        },
        "thermal": {"nodes": [{"id": "core", "temp_c": 21.0}]},
        "radiation_usvh": 1.2,
        "temp_external_c": -60.0,
        "temp_core_c": 20.0,
        "sim_state": {"running": True, "paused": False, "speed": 1.0, "fsm_state": "RUNNING"},
        "propulsion": {"rcs": {"active": True, "throttled": False}},
        "sensor_plane": {
            "radiation": {
                "enabled": True,
                "status": "warn",
                "background_usvh": 1.2,
                "limits": {"warn_usvh": 1.0, "crit_usvh": 2.0},
            }
        },
        "comms": {"xpdr": {"mode": "MODE_C", "allowed": True}},
    }


def main() -> None:
    os.environ.setdefault("ORION_SUMMARY_COMPACT_DEFAULT", "1")
    app = OrionApp()
    app.nats_connected = True
    app._events_filter_text = None
    app._snapshots.put(
        EventEnvelope(
            event_id="startup-snapshot-proof",
            type="telemetry",
            source="telemetry",
            ts_epoch=time.time(),
            level="warn",
            payload=_sample_payload(),
        )
    )
    blocks = app._build_summary_blocks()
    print("SNAPSHOT_PROOF_MODE=deterministic")
    print("BEFORE_REFERENCE_SUMMARY_ROWS=10")
    print("BEFORE_REFERENCE_BLOCKS=" + ",".join(LEGACY_BASELINE_BLOCKS))
    print(f"AFTER_SUMMARY_ROWS={len(blocks)}")
    print("AFTER_SUMMARY_IDS=" + ",".join(block.block_id for block in blocks))
    print("AFTER_SUMMARY_LINES_BEGIN")
    for block in blocks:
        print(f"{block.block_id}|{block.status}|{block.value}")
    print("AFTER_SUMMARY_LINES_END")


if __name__ == "__main__":
    main()
