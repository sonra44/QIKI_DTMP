from __future__ import annotations

from pathlib import Path

from project_introspector.scanner import scan_project
from project_introspector.schema_builder import build_schema


def test_scanner_extracts_expanded_factual_facts(tmp_path: Path) -> None:
    pkg = tmp_path / "svc"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "peer.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (pkg / "main.py").write_text(
        """
import argparse
import os
from pydantic import BaseModel
from . import peer

class Settings(BaseModel):
    api_key: str
    retries: int = 3

class Worker:
    kind = "worker"
    timeout: int = 10
    def __init__(self):
        self.client = None
        self.ready: bool = False

app = object()

@app.get("/items/{item_id}")
def get_item(item_id: str):
    os.getenv("API_TOKEN", "dev")
    os.environ.get("SERVICE_URL")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, default="config.toml")
    return peer.helper()
""",
        encoding="utf-8",
    )

    snapshot = scan_project(tmp_path, project_name="demo")
    module = next(item for item in snapshot.modules if item.module_path == "svc.main")

    assert any(fact.raw_import == ".peer" and fact.normalized_import == "svc.peer" for fact in module.import_facts)
    assert module.fastapi_routes[0].method == "GET"
    assert module.fastapi_routes[0].path == "/items/{item_id}"
    assert {item.name for item in module.env_vars} == {"API_TOKEN", "SERVICE_URL"}
    assert module.cli_options[0].option_strings == ["--config"]
    assert module.pydantic_models[0].qualified_name == "svc.main.Settings"
    assert {attr.attribute_name for attr in module.class_attributes} >= {"kind", "timeout", "client", "ready"}

    schema = build_schema(snapshot)
    assert any(edge.source == "svc.main" and edge.target == "svc.peer" for edge in schema.edges)
