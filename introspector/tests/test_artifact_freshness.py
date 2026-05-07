from __future__ import annotations

from datetime import UTC, datetime

from project_introspector.artifact_freshness import evaluate_artifact_freshness, parse_iso_datetime


def test_freshness_current_and_stale() -> None:
    assert evaluate_artifact_freshness("2026-05-03T10:00:00Z", "2026-05-03T09:00:00Z", now=datetime(2026, 5, 3, 11, tzinfo=UTC)).status == "current"
    assert evaluate_artifact_freshness("2026-05-03T08:00:00Z", "2026-05-03T09:00:00Z", now=datetime(2026, 5, 3, 11, tzinfo=UTC)).status == "stale"


def test_freshness_missing_unknown_invalid_and_future() -> None:
    assert evaluate_artifact_freshness(None, "2026-05-03T09:00:00Z", artifact_exists=False).status == "missing"
    assert evaluate_artifact_freshness(None, "2026-05-03T09:00:00Z").reason_code == "artifact_timestamp_missing"
    assert evaluate_artifact_freshness("2026-05-03T09:00:00Z", None).reason_code == "scan_timestamp_missing"
    assert evaluate_artifact_freshness("bad", "2026-05-03T09:00:00Z").status == "invalid_timestamp"
    assert evaluate_artifact_freshness("2026-05-04T09:00:00Z", "2026-05-03T09:00:00Z", now=datetime(2026, 5, 3, 9, tzinfo=UTC)).status == "future_timestamp"


def test_parse_iso_datetime_normalizes_naive_and_zulu() -> None:
    assert parse_iso_datetime("2026-05-03T09:00:00Z") is not None
    parsed = parse_iso_datetime("2026-05-03T09:00:00")
    assert parsed is not None
    assert parsed.tzinfo is not None
