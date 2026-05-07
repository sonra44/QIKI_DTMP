from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .artifact_freshness import evaluate_artifact_freshness, parse_iso_datetime


@dataclass(frozen=True)
class ArtifactEvidenceReason:
    code: str
    freshness_state: str


def artifact_evidence_reason(
    *,
    artifact_exists: bool,
    artifact_updated_at: str | None,
    scan_scanned_at: str | None,
) -> ArtifactEvidenceReason:
    freshness = evaluate_artifact_freshness(
        artifact_updated_at,
        scan_scanned_at,
        artifact_exists=artifact_exists,
    )
    return ArtifactEvidenceReason(code=freshness.reason_code, freshness_state=freshness.freshness_state)
