from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "live_module_pass.py"
SPEC = importlib.util.spec_from_file_location("live_module_pass_script", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_validate_llm_status_fails_early_when_provider_is_unconfigured() -> None:
    with pytest.raises(RuntimeError, match="configured=false"):
        MODULE._validate_llm_status(
            {"configured": False},
            analyzer_url="http://127.0.0.1:8015",
            allow_unconfigured_provider=False,
        )


def test_validate_llm_status_allows_intentional_degraded_path() -> None:
    MODULE._validate_llm_status(
        {"configured": False},
        analyzer_url="http://127.0.0.1:8015",
        allow_unconfigured_provider=True,
    )


def test_ensure_modules_exist_detects_missing_module(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "__init__.py").write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="missing modules"):
        MODULE._ensure_modules_exist(tmp_path, ["demo", "demo.missing"])
