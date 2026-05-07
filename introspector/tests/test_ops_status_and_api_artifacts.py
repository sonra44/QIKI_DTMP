from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from analyzer import app as analyzer_app
from project_introspector.models import LLMModuleAnalysis
from project_introspector.tui_client import IntrospectorTuiClient


def test_status_endpoint_is_compatible_with_tui_status_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(analyzer_app, "DATA_DIR", tmp_path)
    client = TestClient(analyzer_app.app)

    response = client.get("/llm/status")
    assert response.status_code == 200
    from project_introspector.tui_models import AnalyzerStatus
    model = AnalyzerStatus(**response.json())

    assert model.storage["backend"] == "sqlite+json-mirror"
    assert model.provider_name is not None


def test_tui_client_can_read_live_module_artifact_from_api_docs(tmp_path: Path, monkeypatch) -> None:
    tui = IntrospectorTuiClient(project_name="demo", analyzer_url="http://unused", introspector_root=tmp_path)
    analysis = LLMModuleAnalysis(module_path="pkg.module", purpose="api replay", status="active")

    payloads = {
        "ops_live_pass_summary": {
            "project_name": "demo",
            "artifact_docs": [
                {
                    "doc_key": "ops_live_module_pkg__module",
                    "module_path": "pkg.module",
                    "variant": "normal",
                    "updated_at": "2026-04-04T00:00:00+00:00",
                }
            ],
            "enrichment": {"status": "done", "provider_configured": True},
            "factual_refresh": {"status": "done"},
        },
        "ops_live_module_pkg__module": analysis.model_dump(mode="json"),
    }

    monkeypatch.setattr(tui, "fetch_derived_doc", lambda doc_key, *, force=False: payloads.get(doc_key))

    artifact = tui.load_module_artifact("pkg.module", force=True)

    assert artifact.analysis is not None
    assert artifact.analysis.purpose == "api replay"
    assert artifact.detail_ref is not None
    assert artifact.detail_ref.source_kind == "live-derived-api"
    assert artifact.detail_ref.doc_key == "ops_live_module_pkg__module"


def test_ops_status_reports_project_counts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(analyzer_app, "DATA_DIR", tmp_path)
    client = TestClient(analyzer_app.app)

    response = client.post(
        "/derived/demo/ops_live_pass_summary",
        json={"project_name": "demo", "enrichment": {"status": "done"}, "factual_refresh": {"status": "done"}},
    )
    assert response.status_code == 200

    ops = client.get("/ops/status/demo")
    assert ops.status_code == 200
    body = ops.json()
    assert body["project_name"] == "demo"
    assert body["derived_docs_count"] >= 1
