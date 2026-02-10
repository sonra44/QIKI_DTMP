from __future__ import annotations

from pathlib import Path
import re


def test_mission_control_terminal_has_no_runtime_autopip() -> None:
    source_path = (
        Path(__file__).resolve().parents[1] / "core" / "mission_control_terminal.py"
    )
    source = source_path.read_text(encoding="utf-8")

    assert "os.system(" not in source
    assert "pip install" not in source
    assert re.search(r"^\s*import\s+prompt_toolkit\b", source, re.MULTILINE) is None
    assert re.search(r"^\s*from\s+prompt_toolkit\b", source, re.MULTILINE) is None
