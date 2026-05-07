from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from analyzer import app as analyzer_app
from project_introspector.models import LLMModuleAnalysis
from project_introspector.tui_client import IntrospectorTuiClient


def test_tui_client_prefers_api_backed_derived_module(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(analyzer_app, "DATA_DIR", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    client = TestClient(analyzer_app.app)

    analysis = LLMModuleAnalysis(module_path="pkg.module", purpose="api purpose", status="active")
    response = client.post("/derived/demo/llm_module_pkg__module", json=analysis.model_dump(mode="json"))
    assert response.status_code == 200

    tui = IntrospectorTuiClient(project_name="demo", analyzer_url="http://unused", introspector_root=tmp_path)

    def fake_fetch_derived_doc(doc_key: str, *, force: bool = False):
        if doc_key == "llm_module_pkg__module":
            return analysis.model_dump(mode="json")
        return None

    monkeypatch.setattr(tui, "fetch_derived_doc", fake_fetch_derived_doc)

    artifact = tui.load_module_artifact("pkg.module")

    assert artifact.analysis is not None
    assert artifact.analysis.purpose == "api purpose"


def test_tui_client_reads_live_pass_and_project_scan_from_api(tmp_path: Path, monkeypatch) -> None:
    tui = IntrospectorTuiClient(project_name="demo", analyzer_url="http://unused", introspector_root=tmp_path)

    payloads = {
        "ops_live_pass_summary": {
            "project_name": "demo",
            "output_dir": "/tmp/out",
            "artifacts": ["/tmp/out/mod.json"],
            "enrichment": {
                "status": "done",
                "provider_configured": True,
                "modules_requested": 1,
                "modules_done": 1,
                "modules_degraded": 0,
                "modules_failed": 0,
            },
            "factual_refresh": {"status": "done"},
        },
        "ops_project_scan_summary": {
            "project_name": "demo",
            "source_root": "/tmp/src",
            "modules_scanned": 3,
            "scan_errors": 0,
            "scanned_at": "2026-04-04T00:00:00+00:00",
            "output_dir": "/tmp/project_scan",
            "factual_layer": {
                "status": "done",
                "schema_ready": True,
                "runtime_merged": False,
                "runtime_event_count": 0,
            },
        },
    }

    monkeypatch.setattr(tui, "fetch_derived_doc", lambda doc_key, *, force=False: payloads.get(doc_key))

    live = tui.load_latest_live_pass(force=True)
    scan = tui.load_latest_project_scan(force=True)

    assert live.project_name == "demo"
    assert live.modules_done == 1
    assert scan.project_name == "demo"
    assert scan.modules_scanned == 3
