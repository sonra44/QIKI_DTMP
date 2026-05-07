from __future__ import annotations

from pathlib import Path

from project_introspector.models import LLMProjectAnalysis
from project_introspector.project_analysis_policy import sanitize_project_analysis
from project_introspector.scanner import scan_project
from project_introspector.schema_builder import build_schema


def test_project_analysis_policy_removes_ungrounded_structured_items(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("import httpx\ndef main():\n    return 1\n", encoding="utf-8")
    schema = build_schema(scan_project(tmp_path, project_name="demo"))
    analysis = LLMProjectAnalysis(
        project_name="wrong",
        critical_modules=["main", "ghost.module"],
        external_dependencies=["httpx", "redis"],
        key_entrypoints=["main", "ghost.entry"],
        cleanup_candidates=["ghost.cleanup"],
    )

    sanitized = sanitize_project_analysis(analysis, schema)

    assert sanitized.project_name == "demo"
    assert sanitized.critical_modules == ["main"]
    assert sanitized.external_dependencies == ["httpx"]
    assert sanitized.key_entrypoints == ["main"]
    assert sanitized.cleanup_candidates == []
    assert sanitized.degraded is True
    assert "project_policy_removed_unknown_external_dependency" in sanitized.warning_codes
