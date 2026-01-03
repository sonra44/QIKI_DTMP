from __future__ import annotations

import json
from pathlib import Path

import pytest

from qiki.services.operator_console.core.incident_rules import FileRulesRepository


VALID_RULES = """
version: 1
rules:
  - id: TEST_RULE
    enabled: true
    title: "Test rule"
    description: "Test description"
    match:
      type: "sensor"
      source: "thermal"
      subject: "core"
      field: "temp"
    threshold:
      op: ">"
      value: 70
      min_duration_s: 1
      cooldown_s: 5
    severity: "W"
    require_ack: true
    auto_clear: true
"""


INVALID_RULES = """
version: 1
rules:
  - id: BAD_RULE
    enabled: true
    title: "Bad rule"
    match:
      type: "sensor"
    threshold:
      op: "?"
      value: 1
    severity: "Z"
"""


def write_rules(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_rules_load_valid(tmp_path: Path) -> None:
    rules_path = tmp_path / "incident_rules.yaml"
    write_rules(rules_path, VALID_RULES)

    repo = FileRulesRepository(str(rules_path))
    config = repo.load()
    assert config.version == 1
    assert len(config.rules) == 1
    assert config.rules[0].id == "TEST_RULE"


def test_rules_load_invalid(tmp_path: Path) -> None:
    rules_path = tmp_path / "incident_rules.yaml"
    write_rules(rules_path, INVALID_RULES)

    repo = FileRulesRepository(str(rules_path))
    with pytest.raises(ValueError):
        repo.load()


def test_rules_reload_writes_history(tmp_path: Path) -> None:
    rules_path = tmp_path / "incident_rules.yaml"
    history_path = tmp_path / "incident_rules.history.jsonl"

    write_rules(rules_path, VALID_RULES)
    repo = FileRulesRepository(str(rules_path), str(history_path))
    repo.load()

    write_rules(rules_path, VALID_RULES.replace("TEST_RULE", "TEST_RULE_2"))
    result = repo.reload()

    assert result.old_hash
    assert result.new_hash
    history_lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(history_lines) == 1
    payload = json.loads(history_lines[0])
    assert payload["old_hash"] == result.old_hash
    assert payload["new_hash"] == result.new_hash
    assert payload["source"] == "file/reload"
