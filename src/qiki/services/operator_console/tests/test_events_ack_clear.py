from __future__ import annotations

from pathlib import Path

import pytest

from qiki.services.operator_console.main_orion import OrionApp


RULES = """\
version: 1
rules:
  - id: TEMP_HIGH
    enabled: true
    title: "High temperature"
    match:
      type: "sensor"
      source: "thermal"
      field: "temp"
    threshold:
      op: ">"
      value: 70
    severity: "W"
    require_ack: false
    auto_clear: true
"""


@pytest.mark.asyncio
async def test_x_clears_acknowledged_incidents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_path = tmp_path / "incident_rules.yaml"
    history_path = tmp_path / "incident_rules.history.jsonl"
    rules_path.write_text(RULES, encoding="utf-8")

    monkeypatch.setenv("OPERATOR_CONSOLE_INCIDENT_RULES", str(rules_path))
    monkeypatch.setenv("OPERATOR_CONSOLE_INCIDENT_RULES_HISTORY", str(history_path))

    app = OrionApp()
    app.active_screen = "events"

    await app.handle_event_data(
        {"subject": "sensor.temp", "data": {"source": "thermal", "subject": "core", "temp": 80}}
    )

    assert app._incident_store is not None
    incidents = app._incident_store.list_incidents()
    assert len(incidents) == 1

    inc_id = incidents[0].incident_id
    assert app._incident_store.ack(inc_id) is True

    # Avoid running the full Textual app loop in this unit test; exercise the
    # underlying clear logic directly.
    removed = app._clear_acked_incidents()
    assert removed == 1

    assert app._incident_store.list_incidents() == []
