from __future__ import annotations

import json
import subprocess
from pathlib import Path

from project_introspector.models import LLMModuleAnalysis
from project_introspector.tui_client import IntrospectorTuiClient


def test_load_derived_analyses_uses_storage_layout(tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir()
    artifact_path = derived_dir / "demo.llm_module_pkg__module.json"
    artifact_path.write_text(
        LLMModuleAnalysis(
            module_path="pkg.module",
            purpose="demo purpose",
            status="active",
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )

    client = IntrospectorTuiClient(project_name="demo", introspector_root=tmp_path)
    analyses = client.load_derived_analyses(
        ["pkg.module"],
        storage_layout={"derived": str(derived_dir)},
    )

    assert analyses["pkg.module"].analysis is not None
    assert analyses["pkg.module"].analysis.purpose == "demo purpose"
    assert analyses["pkg.module"].artifact_path == artifact_path


def test_load_latest_live_pass_reads_summary(tmp_path: Path) -> None:
    output_dir = tmp_path / "tmp" / "live_module_pass"
    output_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.json"
    status_path = output_dir / "llm_status.json"
    status_path.write_text("{}", encoding="utf-8")
    summary_path.write_text(
        json.dumps(
            {
                "project_name": "demo",
                "output_dir": str(output_dir),
                "artifacts": [str(output_dir / "main.json")],
            }
        ),
        encoding="utf-8",
    )

    client = IntrospectorTuiClient(project_name="demo", introspector_root=tmp_path)
    summary = client.load_latest_live_pass()

    assert summary.project_name == "demo"
    assert summary.status_path == status_path
    assert summary.artifact_paths == [output_dir / "main.json"]
    assert summary.artifact_refs[0].source_kind == "live-replay"
    assert summary.artifact_refs[0].variant == "normal"


def test_load_latest_live_pass_cache_invalidation_tracks_summary_changes(tmp_path: Path) -> None:
    output_dir = tmp_path / "tmp" / "live_module_pass"
    output_dir.mkdir(parents=True)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "project_name": "demo-v1",
                "output_dir": str(output_dir),
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )

    client = IntrospectorTuiClient(project_name="demo", introspector_root=tmp_path)
    first = client.load_latest_live_pass()
    second = client.load_latest_live_pass()
    assert first is second

    summary_path.write_text(
        json.dumps(
            {
                "project_name": "demo-v2",
                "output_dir": str(output_dir),
                "artifacts": [],
            }
        ),
        encoding="utf-8",
    )

    updated = client.load_latest_live_pass()

    assert updated.project_name == "demo-v2"
    assert updated is not first


def test_load_latest_live_pass_does_not_refetch_missing_api_doc_on_forced_refresh(
    monkeypatch, tmp_path: Path
) -> None:
    force_values: list[bool] = []

    def fake_fetch(doc_key: str, *, force: bool = False):
        force_values.append(force)
        client._missing_derived_docs.add(doc_key)
        return None

    client = IntrospectorTuiClient(project_name="demo", analyzer_url="http://unused", introspector_root=tmp_path)
    monkeypatch.setattr(client, "fetch_derived_doc", fake_fetch)

    first = client.load_latest_live_pass(force=True)
    second = client.load_latest_live_pass(force=True)

    assert first.summary_path == tmp_path / "tmp" / "live_module_pass" / "summary.json"
    assert second.summary_path == first.summary_path
    assert force_values == [True, False]


def test_client_from_env(monkeypatch) -> None:
    monkeypatch.setenv("INTROSPECTOR_ANALYZER_URL", "http://127.0.0.1:8014")
    monkeypatch.setenv("INTROSPECTOR_PROJECT_NAME", "demo-project")
    monkeypatch.setenv("INTROSPECTOR_SOURCE_ROOT", "/tmp/qiki-src")
    monkeypatch.setenv("PYTHON_BIN", "/tmp/python")

    client = IntrospectorTuiClient.from_env()

    assert client.analyzer_url == "http://127.0.0.1:8014"
    assert client.project_name == "demo-project"
    assert client.source_root == Path("/tmp/qiki-src")
    assert client.python_bin == "/tmp/python"


def test_run_project_scan_passes_explicit_source_root(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    source_root = tmp_path / "qiki-src"
    source_root.mkdir()

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(command, 0, stdout="scan ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = IntrospectorTuiClient(
        project_name="QIKI_DTMP_FRESH",
        introspector_root=tmp_path,
        source_root=source_root,
        python_bin="/tmp/python",
    )

    result = client.run_project_scan()

    command = captured["command"]
    assert result.returncode == 0
    assert "--source-root" in command
    assert command[command.index("--source-root") + 1] == str(source_root.resolve())
    assert "--project-name" in command
    assert command[command.index("--project-name") + 1] == "QIKI_DTMP_FRESH"


def test_load_latest_project_scan_surfaces_configured_source_root_when_missing(
    monkeypatch, tmp_path: Path
) -> None:
    source_root = tmp_path / "qiki-src"
    source_root.mkdir()
    client = IntrospectorTuiClient(
        project_name="QIKI_DTMP_FRESH",
        introspector_root=tmp_path,
        source_root=source_root,
    )
    monkeypatch.setattr(client, "fetch_derived_doc", lambda *args, **kwargs: None)

    summary = client.load_latest_project_scan()

    assert summary.source_root == str(source_root.resolve())
    assert summary.output_dir == str(tmp_path / "tmp" / "project_scan")


def test_load_module_artifact_falls_back_to_live_replay_with_provenance(tmp_path: Path) -> None:
    output_dir = tmp_path / "tmp" / "live_module_pass"
    output_dir.mkdir(parents=True)
    artifact_path = output_dir / "ship_bios_handler.json"
    artifact_path.write_text(
        LLMModuleAnalysis(
            module_path="pkg.ship_bios_handler",
            purpose="demo purpose",
            status="active",
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            {
                "project_name": "demo",
                "output_dir": str(output_dir),
                "artifacts": [str(artifact_path)],
            }
        ),
        encoding="utf-8",
    )

    client = IntrospectorTuiClient(project_name="demo", introspector_root=tmp_path)
    artifact = client.load_module_artifact("pkg.ship_bios_handler")

    assert artifact.analysis is not None
    assert artifact.detail_ref is not None
    assert artifact.detail_ref.source_kind == "live-replay"
    assert artifact.detail_ref.variant == "normal"


def test_run_live_pass_returns_structured_timeout(monkeypatch, tmp_path: Path) -> None:
    client = IntrospectorTuiClient(project_name="demo", introspector_root=tmp_path, timeout=1.0)

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=kwargs.get("args") or args[0],
            timeout=kwargs["timeout"],
            output=b"partial stdout",
            stderr=b"partial stderr",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = client.run_live_pass()

    assert result.returncode == 124
    assert result.timed_out is True
    assert result.stdout == "partial stdout"
    assert result.stderr == "partial stderr"


def test_fetch_status_uses_short_lived_cache(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            calls["count"] += 1
            return {
                "configured": True,
                "base_url": "http://127.0.0.1:8015",
                "default_model": "normal",
                "fallback_model": "cheap",
                "app_name": "project-introspector",
                "build_marker": None,
                "app_file": "/tmp/analyzer/app.py",
                "storage_layout": {"derived": "/tmp/derived"},
            }

    class FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            return FakeResponse()

    import project_introspector.tui_client as tui_client_module

    monkeypatch.setattr(tui_client_module.httpx, "Client", FakeHttpClient)
    client = IntrospectorTuiClient(project_name="demo", introspector_root=tmp_path)

    first = client.fetch_status()
    second = client.fetch_status()
    third = client.fetch_status(force=True)

    assert first == second == third
    assert calls["count"] == 2


def test_fetch_report_uses_cache_and_404_is_non_fatal(monkeypatch, tmp_path: Path) -> None:
    responses = [
        (200, {"report_version": "project-introspector.report.v1"}),
        (404, None),
    ]
    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object] | None) -> None:
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            calls["count"] += 1
            status_code, payload = responses[min(calls["count"] - 1, len(responses) - 1)]
            return FakeResponse(status_code, payload)

    import project_introspector.tui_client as tui_client_module

    monkeypatch.setattr(tui_client_module.httpx, "Client", FakeHttpClient)
    client = IntrospectorTuiClient(project_name="demo", analyzer_url="http://unused", introspector_root=tmp_path)

    assert client.fetch_report() == {"report_version": "project-introspector.report.v1"}
    assert client.fetch_report() == {"report_version": "project-introspector.report.v1"}
    assert calls["count"] == 1
    assert client.fetch_report(force=True) is None
    assert calls["count"] == 2


def test_fetch_derived_doc_caches_missing_result(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}

    class FakeResponse:
        status_code = 404

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {}

    class FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            calls["count"] += 1
            return FakeResponse()

    import project_introspector.tui_client as tui_client_module

    monkeypatch.setattr(tui_client_module.httpx, "Client", FakeHttpClient)
    client = IntrospectorTuiClient(project_name="demo", analyzer_url="http://unused", introspector_root=tmp_path)

    assert client.fetch_derived_doc("missing_doc") is None
    assert client.fetch_derived_doc("missing_doc") is None
    assert calls["count"] == 1

    client.invalidate_runtime_cache()
    assert client.fetch_derived_doc("missing_doc") is None
    assert calls["count"] == 2


def test_fetch_derived_doc_force_bypasses_missing_cache(monkeypatch, tmp_path: Path) -> None:
    responses = [
        (404, None),
        (200, {"doc_key": "missing_doc", "status": "ready"}),
    ]
    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict[str, object] | None) -> None:
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self._payload

    class FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(self, url: str) -> FakeResponse:
            calls["count"] += 1
            status_code, payload = responses[min(calls["count"] - 1, len(responses) - 1)]
            return FakeResponse(status_code, payload)

    import project_introspector.tui_client as tui_client_module

    monkeypatch.setattr(tui_client_module.httpx, "Client", FakeHttpClient)
    client = IntrospectorTuiClient(project_name="demo", analyzer_url="http://unused", introspector_root=tmp_path)

    assert client.fetch_derived_doc("missing_doc") is None
    assert client.fetch_derived_doc("missing_doc") is None
    assert calls["count"] == 1

    payload = client.fetch_derived_doc("missing_doc", force=True)

    assert payload == {"doc_key": "missing_doc", "status": "ready"}
    assert calls["count"] == 2


def test_load_module_artifact_prefers_local_resolution_over_api_and_live(monkeypatch, tmp_path: Path) -> None:
    derived_dir = tmp_path / "derived"
    derived_dir.mkdir()
    local_path = derived_dir / "demo.llm_module_pkg__mod.json"
    local_path.write_text(
        LLMModuleAnalysis(module_path="pkg.mod", purpose="local", status="active").model_dump_json(),
        encoding="utf-8",
    )
    live_dir = tmp_path / "tmp" / "live_module_pass"
    live_dir.mkdir(parents=True)
    live_path = live_dir / "mod.json"
    live_path.write_text(
        LLMModuleAnalysis(module_path="pkg.mod", purpose="live", status="active").model_dump_json(),
        encoding="utf-8",
    )
    (live_dir / "summary.json").write_text(
        json.dumps({"project_name": "demo", "output_dir": str(live_dir), "artifacts": [str(live_path)]}),
        encoding="utf-8",
    )

    client = IntrospectorTuiClient(project_name="demo", introspector_root=tmp_path)
    monkeypatch.setattr(client, "_known_derived_doc_exists", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        client,
        "_load_analysis_from_api",
        lambda *args, **kwargs: LLMModuleAnalysis(module_path="pkg.mod", purpose="api", status="active"),
    )

    artifact = client.load_module_artifact("pkg.mod", storage_layout={"derived": str(derived_dir)})

    assert artifact.analysis is not None
    assert artifact.analysis.purpose == "local"
    assert artifact.detail_ref is not None
    assert artifact.detail_ref.source_kind == "derived"
