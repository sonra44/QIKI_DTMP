from __future__ import annotations

import logging

from qiki.services.operator_console.orion_v.hardware_view_model import HardwareCollector
from qiki.services.operator_console.orion_v.hardware_view_model.diagnostics import (
    compute_field_coverage,
    compute_missing_keys,
)
from qiki.services.operator_console.orion_v.hardware_view_model.key_aliases import (
    SUBSYSTEM_KEYSETS,
    canonicalize_snapshot,
)


def test_compute_field_coverage_counts_filled_by_status() -> None:
    collector = HardwareCollector()
    model = collector.update({"comms.latency_ms": 45.0}, now_ts=1000.0)

    coverage = compute_field_coverage(model)
    assert coverage["comms"][1] >= 7
    assert coverage["comms"][0] >= 1


def test_compute_missing_keys_reports_expected_for_empty_snapshot() -> None:
    missing = compute_missing_keys(snapshot_canon={}, subsystem_keysets=SUBSYSTEM_KEYSETS)

    assert "comms.latency_ms" in missing["comms"]
    assert "power.soc" in missing["power"]


def test_canonicalize_snapshot_adds_canonical_keys_from_aliases() -> None:
    canonical = canonicalize_snapshot({"link.loss_pct": 3.5, "link.latency_ms": 180.0})

    assert canonical["comms.packet_loss_pct"] == 3.5
    assert canonical["comms.latency_ms"] == 180.0


def test_diagnostics_rate_limit_blocks_second_log_before_period(
    monkeypatch, caplog
) -> None:
    collector = HardwareCollector()
    caplog.set_level(
        logging.INFO,
        logger="qiki.services.operator_console.orion_v.hardware_view_model.collector",
    )
    model = collector.update({"comms.latency_ms": 45.0}, now_ts=1000.0)
    snapshot_canon = canonicalize_snapshot({"comms.latency_ms": 45.0})
    monkeypatch.setenv("ORIONV_HWM_DIAG", "1")
    monkeypatch.setenv("ORIONV_HWM_DIAG_PERIOD_S", "10")

    caplog.clear()
    collector._log_diagnostics_if_enabled(
        model=model,
        snapshot_canon=snapshot_canon,
        monotonic_now=100.0,
    )
    first_count = len(caplog.records)
    assert first_count >= 1

    collector._log_diagnostics_if_enabled(
        model=model,
        snapshot_canon=snapshot_canon,
        monotonic_now=105.0,
    )
    assert len(caplog.records) == first_count
