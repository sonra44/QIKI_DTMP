from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tui_tmux_smoke.sh"


def _has_provider_credentials() -> bool:
    return any(
        os.getenv(name)
        for name in (
            "OPENROUTER_API_KEY",
            "INTROSPECTOR_API_KEY",
            "LLM_PROVIDER_API_KEY",
            "INCEPTION_API_KEY",
        )
    )


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_smoke(mode: str, port: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHON_BIN", str(ROOT / ".venv" / "bin" / "python"))
    return subprocess.run(
        [str(SCRIPT), "--mode", mode, "--port", str(port)],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )


def _extract_status_payload(stdout: str) -> dict[str, object]:
    for line in stdout.splitlines():
        if line.startswith("STATUS_JSON="):
            return json.loads(line.split("=", 1)[1])
    raise AssertionError(stdout)


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is not installed")
def test_tui_tmux_smoke_unconfigured() -> None:
    completed = _run_smoke("unconfigured", _free_port())
    assert completed.returncode == 0, completed.stderr or completed.stdout
    status_payload = _extract_status_payload(completed.stdout)
    assert "TMUX_SMOKE_OK" in completed.stdout
    assert status_payload["configured"] is False
    assert status_payload["app_name"] == "project-introspector"
    assert "TUI_CAPTURE_BEGIN" in completed.stdout
    assert "module_path:" in completed.stdout
    assert "source_path:" in completed.stdout
    assert "enrichment:" in completed.stdout


@pytest.mark.skipif(shutil.which("tmux") is None, reason="tmux is not installed")
def test_tui_tmux_smoke_configured_when_key_is_present() -> None:
    if not _has_provider_credentials():
        pytest.skip("provider credentials are not available in this shell")

    completed = _run_smoke("configured", _free_port())
    assert completed.returncode == 0, completed.stderr or completed.stdout
    status_payload = _extract_status_payload(completed.stdout)
    assert "TMUX_SMOKE_OK" in completed.stdout
    assert status_payload["configured"] is True
    assert status_payload["app_name"] == "project-introspector"
