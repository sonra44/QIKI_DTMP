from __future__ import annotations

import json
from pathlib import Path

import pytest

from qiki.services.operator_console.main_orion import OrionApp


RULES = """\
version: 1
rules:
  - id: RULE_A
    enabled: true
    title: "A"
    match:
      type: "sensor"
  - id: RULE_B
    enabled: true
    title: "B"
    match:
      type: "sensor"
"""


def test_toggle_rule_enabled_writes_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_path = tmp_path / "incident_rules.yaml"
    history_path = tmp_path / "incident_rules.history.jsonl"
    rules_path.write_text(RULES, encoding="utf-8")

    monkeypatch.setenv("OPERATOR_CONSOLE_INCIDENT_RULES", str(rules_path))
    monkeypatch.setenv("OPERATOR_CONSOLE_INCIDENT_RULES_HISTORY", str(history_path))

    app = OrionApp()
    assert app._incident_rules is not None

    app._apply_rule_enabled_change("RULE_B", False)
    assert app._incident_rules is not None
    by_id = {r.id: r for r in app._incident_rules.rules}
    assert by_id["RULE_B"].enabled is False

    history_lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(history_lines) == 1
    payload = json.loads(history_lines[0])
    assert payload["source"] == "ui/toggle"

