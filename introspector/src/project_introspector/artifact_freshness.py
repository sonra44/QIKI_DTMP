from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArtifactFreshness:
    status: str
    reason_code: str
    artifact_timestamp: str | None = None
    scan_timestamp: str | None = None

    @property
    def freshness_state(self) -> str:
        if self.status in {"current", "stale"}:
            return self.status
        return "unknown"


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def evaluate_artifact_freshness(
    artifact_timestamp: str | None,
    scan_timestamp: str | None,
    *,
    artifact_exists: bool = True,
    now: datetime | None = None,
) -> ArtifactFreshness:
    if not artifact_exists:
        return ArtifactFreshness(
            status="missing",
            reason_code="artifact_missing",
            artifact_timestamp=artifact_timestamp,
            scan_timestamp=scan_timestamp,
        )
    if not artifact_timestamp:
        return ArtifactFreshness(
            status="unknown",
            reason_code="artifact_timestamp_missing",
            artifact_timestamp=artifact_timestamp,
            scan_timestamp=scan_timestamp,
        )
    if not scan_timestamp:
        return ArtifactFreshness(
            status="unknown",
            reason_code="scan_timestamp_missing",
            artifact_timestamp=artifact_timestamp,
            scan_timestamp=scan_timestamp,
        )
    artifact_dt = parse_iso_datetime(artifact_timestamp)
    scan_dt = parse_iso_datetime(scan_timestamp)
    if artifact_dt is None or scan_dt is None:
        return ArtifactFreshness(
            status="invalid_timestamp",
            reason_code="timestamp_unparseable",
            artifact_timestamp=artifact_timestamp,
            scan_timestamp=scan_timestamp,
        )
    reference_now = (now or datetime.now(UTC)).astimezone(UTC)
    if artifact_dt > reference_now + timedelta(minutes=5):
        return ArtifactFreshness(
            status="future_timestamp",
            reason_code="artifact_timestamp_in_future",
            artifact_timestamp=artifact_timestamp,
            scan_timestamp=scan_timestamp,
        )
    if artifact_dt < scan_dt:
        return ArtifactFreshness(
            status="stale",
            reason_code="artifact_older_than_scan",
            artifact_timestamp=artifact_timestamp,
            scan_timestamp=scan_timestamp,
        )
    return ArtifactFreshness(
        status="current",
        reason_code="artifact_at_or_after_scan",
        artifact_timestamp=artifact_timestamp,
        scan_timestamp=scan_timestamp,
    )


def evaluate_path_freshness(
    path: Path,
    scan_timestamp: str | None,
    *,
    now: datetime | None = None,
) -> ArtifactFreshness:
    if not path.exists():
        return evaluate_artifact_freshness(None, scan_timestamp, artifact_exists=False, now=now)
    updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    return evaluate_artifact_freshness(updated_at, scan_timestamp, artifact_exists=True, now=now)
