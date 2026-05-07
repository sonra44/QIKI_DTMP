from __future__ import annotations

from pathlib import Path

from project_introspector.artifact_resolver import ArtifactCandidate, ArtifactCandidates, resolve_module_artifact


def test_resolver_prefers_explicit_override_over_other_candidates(tmp_path: Path) -> None:
    override = ArtifactCandidate(source="override", path=tmp_path / "override.json", exists=True, payload={"module_path": "pkg.mod"})
    local = ArtifactCandidate(source="local_module_finding", path=tmp_path / "local.json", exists=True, payload={"module_path": "pkg.mod"})

    result = resolve_module_artifact(
        "pkg.mod",
        ArtifactCandidates(
            explicit_override=override,
            local_module_finding=local,
            scan_timestamp="2026-05-03T09:00:00Z",
        ),
    )

    assert result.found is True
    assert result.source == "override"
    assert result.reason == "explicit_override"


def test_resolver_uses_analyzer_doc_before_live_replay() -> None:
    analyzer = ArtifactCandidate(source="analyzer_derived_doc", doc_key="llm_module_pkg__mod", payload={"module_path": "pkg.mod"})
    live = ArtifactCandidate(source="live_replay", path=Path("live.json"), exists=True, payload={"module_path": "pkg.mod"})

    result = resolve_module_artifact("pkg.mod", ArtifactCandidates(analyzer_derived_doc=analyzer, live_replay_refs=[live]))

    assert result.found is True
    assert result.source == "analyzer_derived_doc"
    assert result.doc_key == "llm_module_pkg__mod"


def test_resolver_returns_empty_placeholder_when_nothing_found() -> None:
    result = resolve_module_artifact("pkg.missing", ArtifactCandidates())

    assert result.found is False
    assert result.reason == "no_artifact_for_pkg.missing"
    assert "artifact_not_found" in result.warnings
