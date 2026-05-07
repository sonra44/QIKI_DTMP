from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (SRC, ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from analyzer import app as analyzer_app
from project_introspector import scan_project
from project_introspector.llm import OpenAICompatibleEnrichmentClient
from project_introspector.models import RuntimeEvent


def test_llm_project_endpoint_returns_degraded_result_on_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(analyzer_app, "DATA_DIR", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "svc").mkdir(exist_ok=True)
    (tmp_path / "svc" / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")

    snapshot = scan_project(tmp_path / "svc", project_name="demo")
    client = TestClient(analyzer_app.app)
    static_response = client.post("/events/static", json=snapshot.model_dump(mode="json"))
    assert static_response.status_code == 200

    monkeypatch.setenv("INTROSPECTOR_API_KEY", "dummy")

    class BrokenClient:
        def analyze_project_schema(self, *args, **kwargs):
            raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(analyzer_app, "build_enrichment_client_from_env", lambda: BrokenClient())

    response = client.post("/llm/analyze/project/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["warnings"]
    assert "upstream unavailable" in body["warnings"][0]


def test_generic_module_analysis_endpoint_applies_semantic_gate_to_drifted_valid_llm_output(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(analyzer_app, "DATA_DIR", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)

    snapshot = scan_project(ROOT / "src", project_name="INTROSPECTOR_DEMO")
    client = TestClient(analyzer_app.app)
    static_response = client.post("/events/static", json=snapshot.model_dump(mode="json"))
    assert static_response.status_code == 200

    runtime_response = client.post(
        "/events/runtime",
        json=[
            RuntimeEvent(
                event_type="call",
                project_name="INTROSPECTOR_DEMO",
                module_path="project_introspector.runtime",
                qualified_name="project_introspector.runtime.instrument_function",
            ).model_dump(mode="json")
        ],
    )
    assert runtime_response.status_code == 200

    monkeypatch.setenv("INTROSPECTOR_API_KEY", "dummy")

    fake_parsed = {
        "module_path": "wrong.module.path",
        "purpose": "Invented summary that should be reduced.",
        "responsibilities": ["Invent responsibilities"],
        "public_symbols": ["ghost_symbol", "instrument_function"],
        "outbound_dependencies": ["ghost.dep", "inspect"],
        "runtime_hotspots": ["ghost.hotspot"],
        "stale_doc_signals": [],
        "cleanup_candidates": ["ghost.cleanup", "project_introspector.runtime._emit_safely"],
    }

    def fake_best_effort_chat(self, **kwargs):
        return fake_parsed, '{"fake":"raw"}'

    monkeypatch.setattr(OpenAICompatibleEnrichmentClient, "_best_effort_chat", fake_best_effort_chat)

    response = client.post(
        "/llm/analyze/module/INTROSPECTOR_DEMO",
        params={"module_path": "project_introspector.runtime"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["module_path"] == "project_introspector.runtime"
    assert body["semantic_profile"] == "base"
    assert body["public_symbols"] == ["project_introspector.runtime.instrument_function"]
    assert body["runtime_hotspots"] == ["project_introspector.runtime.instrument_function"]
    assert body["outbound_dependencies"] == ["inspect"]
    assert body["cleanup_candidates"] == ["project_introspector.runtime._emit_safely"]
    assert body["degraded"] is False
