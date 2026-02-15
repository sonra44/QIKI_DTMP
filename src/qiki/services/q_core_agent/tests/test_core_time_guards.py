from __future__ import annotations

import ast
from pathlib import Path


_DETERMINISTIC_CORE_FILES = (
    "src/qiki/services/q_core_agent/core/radar_pipeline.py",
    "src/qiki/services/q_core_agent/core/radar_replay.py",
    "src/qiki/services/q_core_agent/core/radar_fusion.py",
    "src/qiki/services/q_core_agent/core/radar_situation_engine.py",
    "src/qiki/services/q_core_agent/core/radar_policy_loader.py",
)


def _find_time_calls(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "time":
            if func.attr in {"time", "sleep"}:
                violations.append((int(node.lineno), f"time.{func.attr}"))
    return violations


def test_deterministic_core_has_no_direct_time_sleep_or_time_calls() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    found: list[str] = []
    for rel_path in _DETERMINISTIC_CORE_FILES:
        full = repo_root / rel_path
        for lineno, call_name in _find_time_calls(full):
            found.append(f"{rel_path}:{lineno} -> {call_name}")
    assert found == []
