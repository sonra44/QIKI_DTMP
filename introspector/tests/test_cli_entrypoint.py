from __future__ import annotations

import json

from project_introspector.cli import parse_args
from project_introspector.cli import run_tui_health


def test_cli_exposes_scan_report_run_validate_tui_commands() -> None:
    assert parse_args(["scan"]).command == "scan"
    assert parse_args(["report", "--project-name", "demo", "--out", "report.json"]).command == "report"
    assert parse_args(["run", "--project-name", "demo", "--source-root", "src", "--out-dir", "tmp/runs"]).command == "run"
    assert parse_args(["validate", "tmp/runs/demo"]).command == "validate"
    assert parse_args(["tui"]).command == "tui"
    assert parse_args(["tui-health"]).command == "tui-health"


def test_cli_tui_health_exposes_non_interactive_options() -> None:
    args = parse_args([
        "tui-health",
        "--check-analyzer",
        "--analyzer-url",
        "http://127.0.0.1:9999",
        "--project-name",
        "demo",
        "--timeout",
        "0.1",
    ])

    assert args.command == "tui-health"
    assert args.check_analyzer is True
    assert args.analyzer_url == "http://127.0.0.1:9999"
    assert args.project_name == "demo"
    assert args.timeout == 0.1


def test_cli_run_exposes_orchestrator_options() -> None:
    args = parse_args([
        "run",
        "--project-name",
        "demo",
        "--source-root",
        "src",
        "--out-dir",
        "tmp/runs",
        "--offline",
        "--run-id",
        "manual_run",
        "--module",
        "project_introspector.scanner",
        "--max-modules",
        "3",
        "--keep-going",
        "--timeout",
        "5",
    ])

    assert args.command == "run"
    assert args.offline is True
    assert args.run_id == "manual_run"
    assert args.module == ["project_introspector.scanner"]
    assert args.max_modules == 3
    assert args.keep_going is True
    assert args.timeout == 5


def test_tui_health_without_analyzer_check_does_not_start_tui(monkeypatch, capsys) -> None:
    monkeypatch.setattr("project_introspector.cli._textual_available", lambda: True)

    exit_code = run_tui_health(
        analyzer_url="http://127.0.0.1:8015",
        project_name="demo",
        check_analyzer=False,
        timeout=0.1,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["textual_available"] is True
    assert payload["analyzer_checked"] is False
    assert payload["project_name"] == "demo"


def test_tui_health_reports_missing_textual(monkeypatch, capsys) -> None:
    monkeypatch.setattr("project_introspector.cli._textual_available", lambda: False)

    exit_code = run_tui_health(
        analyzer_url="http://127.0.0.1:8015",
        project_name=None,
        check_analyzer=True,
        timeout=0.1,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["status"] == "missing_tui_dependency"
    assert payload["textual_available"] is False
    assert payload["analyzer_checked"] is False


def test_tui_health_checks_analyzer(monkeypatch, capsys) -> None:
    monkeypatch.setattr("project_introspector.cli._textual_available", lambda: True)
    monkeypatch.setattr(
        "project_introspector.cli._fetch_analyzer_status",
        lambda analyzer_url, timeout: {"configured": True, "app_name": "project-introspector"},
    )

    exit_code = run_tui_health(
        analyzer_url="http://127.0.0.1:8015",
        project_name="demo",
        check_analyzer=True,
        timeout=0.1,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["analyzer_checked"] is True
    assert payload["analyzer_status"]["configured"] is True


def test_tui_health_reports_analyzer_unavailable(monkeypatch, capsys) -> None:
    monkeypatch.setattr("project_introspector.cli._textual_available", lambda: True)

    def raise_timeout(analyzer_url: str, timeout: float) -> dict[str, object]:
        raise TimeoutError("timed out")

    monkeypatch.setattr("project_introspector.cli._fetch_analyzer_status", raise_timeout)

    exit_code = run_tui_health(
        analyzer_url="http://127.0.0.1:8015",
        project_name="demo",
        check_analyzer=True,
        timeout=0.1,
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 3
    assert payload["status"] == "analyzer_unavailable"
    assert payload["analyzer_checked"] is True
    assert "TimeoutError" in payload["error"]
