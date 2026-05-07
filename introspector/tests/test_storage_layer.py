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
from project_introspector.models import RuntimeEvent


def test_status_reports_sqlite_storage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(analyzer_app, "DATA_DIR", tmp_path)
    client = TestClient(analyzer_app.app)

    response = client.get("/llm/status")
    assert response.status_code == 200
    body = response.json()
    assert body["storage"]["backend"] == "sqlite+json-mirror"
    assert body["storage_layout"]["sqlite"].endswith("analyzer.sqlite3")


def test_runtime_ingest_writes_sqlite_and_json_mirror(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(analyzer_app, "DATA_DIR", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "svc").mkdir(exist_ok=True)
    (tmp_path / "svc" / "main.py").write_text("def live_flow():\n    return 1\n", encoding="utf-8")

    snapshot = scan_project(tmp_path / "svc", project_name="demo")
    client = TestClient(analyzer_app.app)
    assert client.post("/events/static", json=snapshot.model_dump(mode="json")).status_code == 200
    runtime_payload = [
        RuntimeEvent(
            event_type="call",
            project_name="demo",
            module_path="main",
            qualified_name="main.live_flow",
        ).model_dump(mode="json")
    ]
    assert client.post("/events/runtime", json=runtime_payload).status_code == 200

    sqlite_path = tmp_path / "analyzer.sqlite3"
    runtime_json_path = tmp_path / "runtime" / "demo.json"
    assert sqlite_path.exists()
    assert runtime_json_path.exists()
    assert client.get("/schema/demo").json()["runtime_event_count"] == 1
