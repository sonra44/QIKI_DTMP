from __future__ import annotations

from pathlib import Path

import pytest

from qiki.services.operator_console.orion_v import procedure_engine as procedure_engine_module
from qiki.services.operator_console.orion_v.procedure_engine import (
    ProcedureDefinition,
    ProcedureEngine,
    ProcedureStep,
    parse_procedure_file,
    resolve_procedures_dir,
)
from qiki.services.operator_console.orion_v.app import OrionVApp


def test_parse_procedure_json(tmp_path: Path) -> None:
    path = tmp_path / "proc.json"
    path.write_text(
        """
{
  "name": "demo",
  "steps": [
    {"command":"sim.pause","expected_ack":"sim.pause","timeout":3,"on_fail":"abort"}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    definition = parse_procedure_file(path)
    assert definition.name == "demo"
    assert len(definition.steps) == 1
    assert definition.steps[0].command == "sim.pause"
    assert definition.steps[0].parameters == {}


@pytest.mark.asyncio
async def test_procedure_engine_success() -> None:
    engine = ProcedureEngine()
    definition = ProcedureDefinition(
        name="ok",
        steps=(
            ProcedureStep(command="sim.pause", expected_ack="sim.pause", timeout=1.0, on_fail="abort"),
            ProcedureStep(command="sim.start", expected_ack="sim.start", timeout=1.0, on_fail="abort"),
        ),
    )
    published: list[tuple[str, dict[str, object] | None]] = []
    audits: list[dict[str, object]] = []

    async def publish_command(cmd: str, parameters: dict[str, object] | None) -> None:
        published.append((cmd, parameters))

    async def wait_ack(expected: str, timeout: float) -> bool:
        return expected in {"sim.pause", "sim.start"} and timeout > 0

    async def publish_audit(payload: dict[str, object]) -> None:
        audits.append(payload)

    ok = await engine.run(
        definition,
        publish_command=publish_command,
        wait_ack=wait_ack,
        publish_audit=publish_audit,
    )
    assert ok is True
    assert published == [("sim.pause", {}), ("sim.start", {})]
    assert engine.state.status == "ok"
    assert audits[-1]["kind"] == "procedure_done"


@pytest.mark.asyncio
async def test_procedure_engine_abort_on_failed_ack() -> None:
    engine = ProcedureEngine()
    definition = ProcedureDefinition(
        name="fail",
        steps=(ProcedureStep(command="sim.pause", expected_ack="sim.pause", timeout=0.1, on_fail="abort"),),
    )

    async def publish_command(_cmd: str, _parameters: dict[str, object] | None) -> None:
        return

    async def wait_ack(_expected: str, _timeout: float) -> bool:
        return False

    async def publish_audit(_payload: dict[str, object]) -> None:
        return

    ok = await engine.run(
        definition,
        publish_command=publish_command,
        wait_ack=wait_ack,
        publish_audit=publish_audit,
    )
    assert ok is False
    assert engine.state.status == "failed"


def test_parse_procedure_json_with_parameters(tmp_path: Path) -> None:
    path = tmp_path / "proc_params.json"
    path.write_text(
        """
{
  "name": "slow_mode",
  "steps": [
    {"command":"sim.start","expected_ack":"sim.start","timeout":3,"parameters":{"speed":0.25},"on_fail":"abort"}
  ]
}
""".strip(),
        encoding="utf-8",
    )
    definition = parse_procedure_file(path)
    assert definition.name == "slow_mode"
    assert definition.steps[0].command == "sim.start"
    assert definition.steps[0].parameters == {"speed": 0.25}


def test_resolve_procedures_dir_falls_back_from_empty_workspace_to_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_dir = tmp_path / "workspace" / "config" / "orion_v" / "procedures"
    workspace_dir.mkdir(parents=True)
    repo_root = tmp_path / "repo"
    repo_dir = repo_root / "config" / "orion_v" / "procedures"
    repo_dir.mkdir(parents=True)
    (repo_dir / "safe_pause_resume.json").write_text(
        """
{
  "name": "safe_pause_resume",
  "steps": [
    {"command":"sim.pause","expected_ack":"sim.pause","timeout":3,"on_fail":"abort"}
  ]
}
    """.strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(procedure_engine_module, "_CANONICAL_PROCEDURES_DIR", workspace_dir)

    resolved = resolve_procedures_dir(
        None,
        repo_root=repo_root,
        module_path=workspace_dir / "placeholder.py",
    )

    assert resolved == repo_dir


def test_orion_v_app_loads_repo_relative_procedures_without_external_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORIONV_PROCEDURES_DIR", raising=False)
    monkeypatch.delenv("QIKI_REPO_ROOT", raising=False)

    app = OrionVApp()

    assert "safe_pause_resume" in app._procedure_engine.names()
