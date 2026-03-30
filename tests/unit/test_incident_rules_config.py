from qiki.services.operator_console.core.incident_rules import FileRulesRepository


def test_incident_rules_yaml_contains_power_bus_near_limit() -> None:
    repo = FileRulesRepository("config/incident_rules.yaml")
    cfg = repo.load()
    ids = {r.id for r in cfg.rules}
    assert "POWER_BUS_NEAR_LIMIT" in ids
    assert "POWER_BUS_OVERLOAD" in ids
