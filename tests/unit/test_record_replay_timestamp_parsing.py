from __future__ import annotations

from datetime import UTC, datetime

from qiki.shared.record_replay import _extract_ts_epoch, _infer_type


def test_infer_type_known_subjects() -> None:
    assert _infer_type("qiki.telemetry") == "telemetry"
    assert _infer_type("qiki.events.v1.power.pdu") == "event"
    assert _infer_type("qiki.radar.v1.tracks") == "radar_track"
    assert _infer_type("qiki.responses.control") == "control_ack"


def test_extract_ts_epoch_prefers_ts_epoch_field() -> None:
    ts = _extract_ts_epoch("qiki.events.v1.power.pdu", {"ts_epoch": 123.0, "timestamp": "2026-02-02T00:00:00Z"})
    assert ts == 123.0


def test_extract_ts_epoch_parses_rfc3339_z_timestamp() -> None:
    dt = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    ts = _extract_ts_epoch("qiki.radar.v1.tracks", {"timestamp": "2026-02-02T12:00:00Z"})
    assert ts == dt.timestamp()


def test_extract_ts_epoch_parses_ts_event_iso() -> None:
    dt = datetime(2026, 2, 2, 12, 0, 0, tzinfo=UTC)
    ts = _extract_ts_epoch("qiki.radar.v1.tracks", {"ts_event": "2026-02-02T12:00:00+00:00"})
    assert ts == dt.timestamp()


def test_extract_ts_epoch_reads_telemetry_unix_ms() -> None:
    ts = _extract_ts_epoch("qiki.telemetry", {"ts_unix_ms": 1000})
    assert ts == 1.0

