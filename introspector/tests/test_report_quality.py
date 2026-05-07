from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from analyzer import app as analyzer_app
from project_introspector import scan_project
from project_introspector.models import LLMModuleAnalysis


def _write_demo_source(root: Path) -> None:
    package = root / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "module.py").write_text(
        '"""Demo module."""\n\n'
        'def run(value: int) -> int:\n'
        '    """Return the next value."""\n'
        '    return value + 1\n',
        encoding="utf-8",
    )


def _client_with_static(tmp_path: Path, monkeypatch) -> tuple[TestClient, Path]:
    monkeypatch.setattr(analyzer_app, "DATA_DIR", tmp_path / "data")
    analyzer_app._STORAGE_CACHE = None
    analyzer_app._STORAGE_CACHE_KEY = None
    source_root = tmp_path / "src"
    _write_demo_source(source_root)
    snapshot = scan_project(source_root, project_name="demo")
    client = TestClient(analyzer_app.app)
    response = client.post("/events/static", json=snapshot.model_dump(mode="json"))
    assert response.status_code == 200
    return client, source_root


def test_report_endpoint_returns_factual_only_report(tmp_path: Path, monkeypatch) -> None:
    client, source_root = _client_with_static(tmp_path, monkeypatch)
    scan_summary = {
        "project_name": "demo",
        "source_root": str(source_root),
        "modules_scanned": 2,
        "scan_errors": 0,
        "scanned_at": "2026-04-26T00:00:00+00:00",
        "factual_layer": {"status": "done", "schema_ready": True, "runtime_event_count": 0},
    }
    response = client.post("/derived/demo/ops_project_scan_summary", json=scan_summary)
    assert response.status_code == 200

    report_response = client.get("/report/demo")

    assert report_response.status_code == 200
    report = report_response.json()
    assert report["report_version"] == "project-introspector.report.v1"
    assert report["scope"]["project_name"] == "demo"
    assert report["scope"]["source_root"] == str(source_root)
    assert report["factual_layer"]["modules_scanned"] == 2
    assert report["factual_layer"]["scan_errors"] == 0
    assert report["runtime_layer"]["status"] == "absent"
    assert report["enrichment_layer"]["status"] == "absent"
    assert report["enrichment_layer"]["artifacts_status"] == "absent"
    assert report["enrichment_layer"]["provider_probe_status"] == "not_checked"
    assert any(item["code"] == "runtime_absent" for item in report["limits"])
    assert report["provenance"]["llm_is_truth_source"] is False


def test_report_endpoint_marks_degraded_enrichment_and_module_findings(tmp_path: Path, monkeypatch) -> None:
    client, source_root = _client_with_static(tmp_path, monkeypatch)
    client.post(
        "/derived/demo/ops_project_scan_summary",
        json={
            "project_name": "demo",
            "source_root": str(source_root),
            "modules_scanned": 2,
            "scan_errors": 0,
            "factual_layer": {"status": "done", "schema_ready": True},
        },
    ).raise_for_status()
    client.post(
        "/derived/demo/ops_live_pass_summary",
        json={
            "project_name": "demo",
            "enrichment": {
                "status": "degraded",
                "provider_configured": False,
                "modules_requested": 1,
                "modules_done": 0,
                "modules_degraded": 1,
                "modules_failed": 0,
            },
            "llm_status": {
                "configured": False,
                "provider_name": "openrouter",
                "default_model": "normal",
                "fallback_model": "cheap",
            },
            "factual_refresh": {"status": "skipped", "schema_ready": True},
        },
    ).raise_for_status()
    analysis = LLMModuleAnalysis(
        module_path="pkg.module",
        purpose="demo purpose",
        status="active",
        degraded=True,
        warnings=["provider unavailable"],
        actionable_hints=["retry enrichment later"],
    )
    client.post(
        "/derived/demo/ops_live_module_pkg__module",
        json=analysis.model_dump(mode="json"),
    ).raise_for_status()

    report_response = client.get("/report/demo")

    assert report_response.status_code == 200
    report = report_response.json()
    assert report["enrichment_layer"]["status"] == "degraded"
    assert report["enrichment_layer"]["artifacts_status"] == "present"
    assert report["enrichment_layer"]["provider_configured"] is False
    assert report["enrichment_layer"]["modules_degraded"] == 1
    assert report["module_findings_total"] == 1
    assert report["module_findings"][0]["module_path"] == "pkg.module"
    assert report["module_findings"][0]["purpose"] == "demo purpose"
    assert report["module_findings"][0]["provenance"]["trust_layer"] == "llm_enrichment"
    assert any(item["code"] == "enrichment_degraded" for item in report["limits"])


def test_report_endpoint_separates_provider_credentials_from_missing_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client, source_root = _client_with_static(tmp_path, monkeypatch)
    monkeypatch.setenv("INTROSPECTOR_API_KEY", "dummy")
    client.post(
        "/derived/demo/ops_project_scan_summary",
        json={
            "project_name": "demo",
            "source_root": str(source_root),
            "analyzer_url": "http://127.0.0.1:8015",
            "modules_scanned": 2,
            "scan_errors": 0,
            "factual_layer": {"status": "done", "schema_ready": True},
        },
    ).raise_for_status()

    report_response = client.get("/report/demo")

    assert report_response.status_code == 200
    report = report_response.json()
    assert report["scope"]["analyzer_url"] == "http://127.0.0.1:8015"
    assert report["enrichment_layer"]["status"] == "absent"
    assert report["enrichment_layer"]["artifacts_status"] == "absent"
    assert report["enrichment_layer"]["provider_configured"] is True
    assert report["enrichment_layer"]["provider_credentials_configured"] is True
    assert report["enrichment_layer"]["provider_probe_status"] == "not_checked"
    assert any(item["code"] == "enrichment_absent" for item in report["limits"])
    assert not any(item["code"] == "enrichment_degraded" for item in report["limits"])


def test_report_endpoint_marks_partial_artifacts_without_live_pass_summary(
    tmp_path: Path, monkeypatch
) -> None:
    client, source_root = _client_with_static(tmp_path, monkeypatch)
    client.post(
        "/derived/demo/ops_project_scan_summary",
        json={
            "project_name": "demo",
            "source_root": str(source_root),
            "modules_scanned": 2,
            "scan_errors": 0,
            "factual_layer": {"status": "done", "schema_ready": True},
        },
    ).raise_for_status()
    analysis = LLMModuleAnalysis(module_path="pkg.module", purpose="partial purpose", status="active")
    client.post("/derived/demo/llm_module_pkg__module", json=analysis.model_dump(mode="json")).raise_for_status()

    report_response = client.get("/report/demo")

    assert report_response.status_code == 200
    report = report_response.json()
    assert report["enrichment_layer"]["status"] == "partial_no_live_pass"
    assert report["enrichment_layer"]["artifacts_status"] == "partial_no_live_pass"
    assert report["module_findings_total"] == 1


def test_report_endpoint_returns_404_without_static_schema(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(analyzer_app, "DATA_DIR", tmp_path / "data")
    analyzer_app._STORAGE_CACHE = None
    analyzer_app._STORAGE_CACHE_KEY = None
    client = TestClient(analyzer_app.app)

    response = client.get("/report/missing")

    assert response.status_code == 404
