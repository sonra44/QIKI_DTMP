from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .artifact_freshness import ArtifactFreshness, evaluate_artifact_freshness


@dataclass(frozen=True, slots=True)
class ArtifactCandidate:
    source: str
    path: Path | None = None
    doc_key: str | None = None
    updated_at: str | None = None
    exists: bool = False
    payload: Any | None = None
    variant: str = "unknown"


@dataclass(frozen=True, slots=True)
class ArtifactCandidates:
    explicit_override: ArtifactCandidate | None = None
    run_result_ref: ArtifactCandidate | None = None
    local_module_finding: ArtifactCandidate | None = None
    analyzer_derived_doc: ArtifactCandidate | None = None
    live_replay_refs: list[ArtifactCandidate] = field(default_factory=list)
    empty_placeholder: ArtifactCandidate | None = None
    scan_timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedArtifact:
    source: str
    path: Path | None = None
    doc_key: str | None = None
    found: bool = False
    freshness: ArtifactFreshness | None = None
    reason: str = "not_found"
    warnings: list[str] = field(default_factory=list)
    payload: Any | None = None
    variant: str = "unknown"


def _candidate_found(candidate: ArtifactCandidate | None) -> bool:
    if candidate is None:
        return False
    return candidate.payload is not None or candidate.exists


def _resolve(candidate: ArtifactCandidate, reason: str, scan_timestamp: str | None) -> ResolvedArtifact:
    freshness = evaluate_artifact_freshness(
        candidate.updated_at,
        scan_timestamp,
        artifact_exists=_candidate_found(candidate),
    )
    warnings: list[str] = []
    if freshness.status in {"stale", "future_timestamp", "invalid_timestamp", "missing"}:
        warnings.append(f"artifact_{freshness.status}")
    return ResolvedArtifact(
        source=candidate.source,
        path=candidate.path,
        doc_key=candidate.doc_key,
        found=_candidate_found(candidate),
        freshness=freshness,
        reason=reason,
        warnings=warnings,
        payload=candidate.payload,
        variant=candidate.variant,
    )


def resolve_module_artifact(module_name: str, candidates: ArtifactCandidates) -> ResolvedArtifact:
    ordered: list[tuple[str, ArtifactCandidate | None]] = [
        ("explicit_override", candidates.explicit_override),
        ("run_result_ref", candidates.run_result_ref),
        ("local_module_finding", candidates.local_module_finding),
        ("analyzer_derived_doc", candidates.analyzer_derived_doc),
    ]
    for index, live_ref in enumerate(candidates.live_replay_refs):
        ordered.append((f"live_replay_ref_{index}", live_ref))

    for reason, candidate in ordered:
        if _candidate_found(candidate):
            return _resolve(candidate, reason, candidates.scan_timestamp)

    placeholder = candidates.empty_placeholder or ArtifactCandidate(
        source="empty_placeholder",
        path=None,
        exists=False,
        variant="empty",
    )
    result = _resolve(placeholder, "empty_placeholder", candidates.scan_timestamp)
    return ResolvedArtifact(
        source=result.source,
        path=result.path,
        doc_key=result.doc_key,
        found=False,
        freshness=result.freshness,
        reason=f"no_artifact_for_{module_name}",
        warnings=[*result.warnings, "artifact_not_found"],
        payload=result.payload,
        variant=result.variant,
    )
