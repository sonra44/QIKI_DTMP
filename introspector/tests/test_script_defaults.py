from __future__ import annotations

import importlib.util
from pathlib import Path

from project_introspector.tui_client import IntrospectorTuiClient


ROOT = Path(__file__).resolve().parents[1]


def _load_script_module(name: str, relative_path: str):
    script_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_scan_project_script_defaults_to_generic_project_name(monkeypatch) -> None:
    module = _load_script_module("scan_project_script", "scripts/scan_project.py")
    monkeypatch.delenv("INTROSPECTOR_ANALYZER_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["scan_project.py"])
    args = module.parse_args()
    assert args.project_name == "INTROSPECTOR_DEMO"
    assert args.analyzer_url == "http://127.0.0.1:8015"


def test_live_module_pass_script_defaults_to_generic_project_name(monkeypatch) -> None:
    module = _load_script_module("live_module_pass_script", "scripts/live_module_pass.py")
    monkeypatch.delenv("INTROSPECTOR_ANALYZER_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["live_module_pass.py"])
    args = module.parse_args()
    assert args.project_name == "INTROSPECTOR_DEMO"
    assert args.analyzer_url == "http://127.0.0.1:8015"


def test_scan_and_live_scripts_share_default_source_root(monkeypatch) -> None:
    scan_module = _load_script_module("scan_project_script_source_root", "scripts/scan_project.py")
    live_module = _load_script_module("live_module_pass_script_source_root", "scripts/live_module_pass.py")
    monkeypatch.delenv("INTROSPECTOR_SOURCE_ROOT", raising=False)

    monkeypatch.setattr("sys.argv", ["scan_project.py"])
    scan_args = scan_module.parse_args()
    monkeypatch.setattr("sys.argv", ["live_module_pass.py"])
    live_args = live_module.parse_args()

    assert scan_args.source_root == live_args.source_root
    assert scan_args.source_root == str(ROOT / "src")


def test_tui_client_from_env_defaults_to_generic_project_name(monkeypatch) -> None:
    monkeypatch.delenv("INTROSPECTOR_ANALYZER_URL", raising=False)
    monkeypatch.delenv("INTROSPECTOR_PROJECT_NAME", raising=False)
    client = IntrospectorTuiClient.from_env()
    assert client.project_name == "INTROSPECTOR_DEMO"
    assert client.analyzer_url == "http://127.0.0.1:8015"


def test_tui_tmux_smoke_script_defaults_to_generic_project_name() -> None:
    script_text = (ROOT / "scripts" / "tui_tmux_smoke.sh").read_text(encoding="utf-8")
    assert 'PROJECT_NAME="${PROJECT_NAME:-INTROSPECTOR_DEMO}"' in script_text
