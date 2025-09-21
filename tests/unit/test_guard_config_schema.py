from pathlib import Path

from qiki.services.q_core_agent.core.guard_table import GuardTableLoader, load_guard_table


def test_default_guard_rules_load_from_resources() -> None:
    table = load_guard_table()

    assert table.schema_version == 1
    assert table.rules, "Guard rules must not be empty"


def test_guard_rule_ids_unique() -> None:
    table = load_guard_table()
    rule_ids = [rule.rule_id for rule in table.rules]

    assert len(rule_ids) == len(set(rule_ids))


def test_loader_accepts_custom_path(tmp_path: Path) -> None:
    custom_file = tmp_path / "guard_rules.yaml"
    custom_file.write_text(
        """
schema_version: 1
rules:
  - id: TEST_RULE
    description: Test rule
    severity: info
    fsm_event: TEST
    min_range_m: 0.0
    max_range_m: 10.0
""".strip(),
        encoding="utf-8",
    )

    table = GuardTableLoader(path=custom_file).load()

    assert table.rules[0].rule_id == "TEST_RULE"
