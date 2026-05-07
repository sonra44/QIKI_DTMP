from __future__ import annotations

from pathlib import Path

from project_introspector.import_normalization import normalize_import
from project_introspector.scanner import scan_project
from project_introspector.schema_builder import build_schema


def test_normalize_relative_imports_across_package_levels() -> None:
    assert normalize_import("pkg.sub.mod", ".peer") == ("pkg.sub.peer", "relative", "pkg")
    assert normalize_import("pkg.sub.mod", "..core.service") == ("pkg.core.service", "relative", "pkg")
    assert normalize_import("pkg.sub.mod", "...") == ("", "relative", None)


def test_scanner_extracts_edge_case_routes_cli_env_pydantic_and_attributes(tmp_path: Path) -> None:
    pkg = tmp_path / "svc"
    nested = pkg / "api"
    nested.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (nested / "__init__.py").write_text("", encoding="utf-8")
    (nested / "routes.py").write_text(
        '''
import argparse
import os
from .. import core
from pydantic import BaseModel as BM

router = object()

class Payload(BM):
    name: str
    count: int = 1

class Service:
    category = "api"
    retries: int = 3
    def __init__(self):
        self.client = None
        self.ready: bool = False

@router.post(path="/items")
async def create_item():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run")
    run.add_argument("-c", "--config", action="store_true", required=False, help="Use config")
    os.getenv("TOKEN")
    os.environ["SECRET"]
    os.environ.setdefault("MODE", "dev")
    return core.VALUE
''',
        encoding="utf-8",
    )

    snapshot = scan_project(tmp_path, project_name="demo")
    module = next(item for item in snapshot.modules if item.module_path == "svc.api.routes")
    schema = build_schema(snapshot)

    assert any(fact.raw_import == "..core" and fact.normalized_import == "svc.core" for fact in module.import_facts)
    assert any(edge.source == "svc.api.routes" and edge.target == "svc.core" for edge in schema.edges)
    assert [(route.method, route.path, route.app_name) for route in module.fastapi_routes] == [("POST", "/items", "router")]
    env_access = {env.name: env.access_kind for env in module.env_vars}
    assert env_access["TOKEN"] == "getenv"
    assert env_access["SECRET"] == "getitem"
    assert env_access["MODE"] == "setdefault"
    assert module.cli_options[0].option_strings == ["-c", "--config"]
    assert module.cli_options[0].action == "store_true"
    assert module.cli_options[0].required is False
    assert module.pydantic_models[0].qualified_name == "svc.api.routes.Payload"
    assert {field.name for field in module.pydantic_models[0].fields} == {"name", "count"}
    assert {attr.attribute_name for attr in module.class_attributes} >= {"category", "retries", "client", "ready"}
