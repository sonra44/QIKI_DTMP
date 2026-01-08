from __future__ import annotations

import time

from qiki.services.operator_console.core.incident_rules import IncidentRulesConfig
from qiki.services.operator_console.core.incident_rules import IncidentRule, IncidentRuleMatch, IncidentRuleThreshold
from qiki.services.operator_console.core.incidents import IncidentStore


def make_config(min_duration_s: float | None = None) -> IncidentRulesConfig:
    rule = IncidentRule(
        id="TEMP_SPIKE",
        enabled=True,
        title="Temp spike",
        description="Temp too high",
        match=IncidentRuleMatch(type="sensor", source="thermal", subject="core", field="temp"),
        threshold=IncidentRuleThreshold(op=">", value=70, min_duration_s=min_duration_s, cooldown_s=5),
        severity="C",
        require_ack=True,
        auto_clear=True,
    )
    return IncidentRulesConfig(version=1, rules=[rule])


def base_event(ts: float, temp: float) -> dict[str, object]:
    return {
        "type": "sensor",
        "source": "thermal",
        "subject": "core",
        "ts_epoch": ts,
        "payload": {"temp": temp},
    }


def test_grouping_and_count() -> None:
    store = IncidentStore(make_config())
    ts = time.time()
    for i in range(10):
        store.ingest(base_event(ts + i, 80))
    incidents = store.list_incidents()
    assert len(incidents) == 1
    assert incidents[0].count == 10


def test_ack_and_clear() -> None:
    store = IncidentStore(make_config())
    ts = time.time()
    store.ingest(base_event(ts, 80))
    inc_id = store.list_incidents()[0].incident_id
    assert store.ack(inc_id) is True
    assert store.list_incidents()[0].acked is True
    assert store.clear(inc_id) is True
    assert store.list_incidents()[0].state == "cleared"
    removed = store.clear_acked_cleared()
    assert removed == 1
    assert store.list_incidents() == []


def test_min_duration_blocks_short_spike() -> None:
    store = IncidentStore(make_config(min_duration_s=5))
    ts = time.time()
    store.ingest(base_event(ts, 80))
    store.ingest(base_event(ts + 2, 85))
    assert store.list_incidents() == []
    store.ingest(base_event(ts + 6, 90))
    assert len(store.list_incidents()) == 1
