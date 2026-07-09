from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

_PROCEDURE_FILE_PATTERNS = ("*.json", "*.yaml", "*.yml")
_CANONICAL_PROCEDURES_DIR = Path("/workspace/config/orion_v/procedures")


@dataclass(frozen=True)
class ProcedureStep:
    command: str
    expected_ack: str
    timeout: float
    parameters: dict[str, Any] = field(default_factory=dict)
    on_fail: str = "abort"


@dataclass(frozen=True)
class ProcedureDefinition:
    name: str
    steps: tuple[ProcedureStep, ...]


@dataclass
class ProcedureRunState:
    running: bool = False
    procedure_name: str = ""
    step_index: int = 0
    total_steps: int = 0
    status: str = "idle"
    last_error: str = ""
    progress_log: list[str] = field(default_factory=list)


def _procedure_files(procedures_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in _PROCEDURE_FILE_PATTERNS:
        files.extend(sorted(procedures_dir.glob(pattern)))
    return files


def _has_procedure_files(procedures_dir: Path) -> bool:
    if not procedures_dir.exists():
        return False
    return any(path for pattern in _PROCEDURE_FILE_PATTERNS for path in procedures_dir.glob(pattern))


def _discover_repo_relative_procedures(module_path: Path) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for parent in module_path.resolve().parents:
        candidate = parent / "config" / "orion_v" / "procedures"
        if candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates


def resolve_procedures_dir(
    configured_dir: str | os.PathLike[str] | None = None,
    *,
    repo_root: str | os.PathLike[str] | None = None,
    module_path: Path | None = None,
) -> Path:
    if configured_dir:
        return Path(configured_dir).expanduser()

    candidates: list[Path] = [_CANONICAL_PROCEDURES_DIR]
    if repo_root:
        candidates.append(Path(repo_root).expanduser() / "config" / "orion_v" / "procedures")
    candidates.extend(_discover_repo_relative_procedures(module_path or Path(__file__)))

    seen: set[Path] = set()
    deduped_candidates: list[Path] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped_candidates.append(candidate)

    for candidate in deduped_candidates:
        if _has_procedure_files(candidate):
            return candidate
    for candidate in deduped_candidates:
        if candidate.exists():
            return candidate
    return _CANONICAL_PROCEDURES_DIR


class ProcedureEngine:
    def __init__(self) -> None:
        self._definitions: dict[str, ProcedureDefinition] = {}
        self.state = ProcedureRunState()

    def load_from_dir(self, procedures_dir: Path) -> None:
        loaded: dict[str, ProcedureDefinition] = {}
        if not procedures_dir.exists():
            self._definitions = {}
            return
        for path in _procedure_files(procedures_dir):
            definition = parse_procedure_file(path)
            loaded[definition.name] = definition
        self._definitions = loaded

    def names(self) -> list[str]:
        return sorted(self._definitions)

    def get(self, name: str) -> ProcedureDefinition | None:
        return self._definitions.get(name)

    async def run(
        self,
        definition: ProcedureDefinition,
        *,
        publish_command: Callable[[str, dict[str, Any] | None], Awaitable[str | None]],
        wait_ack: Callable[[str, float, str | None], Awaitable[bool]],
        publish_audit: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> bool:
        self.state = ProcedureRunState(
            running=True,
            procedure_name=definition.name,
            step_index=0,
            total_steps=len(definition.steps),
            status="running",
            progress_log=[f"start {definition.name}"],
        )
        await publish_audit(
            {
                "kind": "procedure_start",
                "procedure": definition.name,
                "steps_total": len(definition.steps),
                "ok": True,
            }
        )

        for idx, step in enumerate(definition.steps, start=1):
            self.state.step_index = idx
            self.state.progress_log.append(f"step {idx}: {step.command}")
            # M2 (пост-фикс аудит): шаг ждёт ACK СВОЕЙ публикации по её id,
            # а не общего слота, который мог перезаписать конкурент.
            command_id = await publish_command(step.command, dict(step.parameters or {}))
            ack_ok = await wait_ack(step.expected_ack, step.timeout, command_id)
            if ack_ok:
                self.state.progress_log.append(f"ack ok: {step.expected_ack}")
                continue

            msg = f"timeout ack={step.expected_ack} step={idx}"
            self.state.last_error = msg
            self.state.progress_log.append(msg)
            await publish_audit(
                {
                    "kind": "procedure_step_failed",
                    "procedure": definition.name,
                    "step_index": idx,
                    "command": step.command,
                    "parameters": dict(step.parameters or {}),
                    "expected_ack": step.expected_ack,
                    "on_fail": step.on_fail,
                    "ok": False,
                }
            )
            if step.on_fail.strip().lower() != "continue":
                self.state.running = False
                self.state.status = "failed"
                return False

        self.state.running = False
        self.state.status = "ok"
        await publish_audit(
            {
                "kind": "procedure_done",
                "procedure": definition.name,
                "steps_total": len(definition.steps),
                "ok": True,
            }
        )
        return True


def parse_procedure_file(path: Path) -> ProcedureDefinition:
    if path.suffix == ".json":
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        try:
            import yaml  # type: ignore[import-untyped]
        except Exception as exc:
            raise RuntimeError(f"PyYAML required for {path.name}") from exc
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise ValueError(f"invalid procedure file: {path}")
    name = str(raw.get("name") or path.stem).strip()
    if not name:
        raise ValueError(f"procedure name missing: {path}")
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ValueError(f"procedure steps missing: {path}")

    steps: list[ProcedureStep] = []
    for item in steps_raw:
        if not isinstance(item, dict):
            raise ValueError(f"invalid step in {path}")
        command = str(item.get("command") or "").strip()
        expected_ack = str(item.get("expected_ack") or "").strip()
        timeout_val = item.get("timeout")
        if not command or not expected_ack:
            raise ValueError(f"command/expected_ack required in {path}")
        if not isinstance(timeout_val, (int, float)) or float(timeout_val) <= 0:
            raise ValueError(f"timeout must be > 0 in {path}")
        on_fail = str(item.get("on_fail") or "abort").strip().lower()
        if on_fail not in {"abort", "continue"}:
            on_fail = "abort"
        parameters_raw = item.get("parameters") or {}
        if not isinstance(parameters_raw, dict):
            raise ValueError(f"parameters must be an object in {path}")
        steps.append(
            ProcedureStep(
                command=command,
                expected_ack=expected_ack,
                timeout=float(timeout_val),
                parameters={str(k): v for k, v in parameters_raw.items()},
                on_fail=on_fail,
            )
        )
    return ProcedureDefinition(name=name, steps=tuple(steps))
