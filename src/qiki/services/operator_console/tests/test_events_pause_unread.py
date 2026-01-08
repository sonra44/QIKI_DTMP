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
async def test_pause_counts_unique_unread_incidents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_path = tmp_path / "incident_rules.yaml"
    history_path = tmp_path / "incident_rules.history.jsonl"
    rules_path.write_text(RULES, encoding="utf-8")

    monkeypatch.setenv("OPERATOR_CONSOLE_INCIDENT_RULES", str(rules_path))
    monkeypatch.setenv("OPERATOR_CONSOLE_INCIDENT_RULES_HISTORY", str(history_path))

    app = OrionApp()
    assert app._events_live is True

    # Pause: table should freeze, unread should count new incident keys (not raw event volume).
    app.action_toggle_events_live()
    assert app._events_live is False
    assert app._events_unread_count == 0

    # Two different subjects → two different incident keys while paused.
    await app.handle_event_data(
        {"subject": "sensor.temp", "data": {"source": "thermal", "subject": "core", "temp": 80}}
    )
    await app.handle_event_data(
        {"subject": "sensor.temp", "data": {"source": "thermal", "subject": "motor", "temp": 80}}
    )
    # Same incident again should not bump unread count.
    await app.handle_event_data(
        {"subject": "sensor.temp", "data": {"source": "thermal", "subject": "core", "temp": 81}}
    )
    assert app._events_unread_count == 2

    # Resume: unread resets and table would catch up.
    app.action_toggle_events_live()
    assert app._events_live is True
    assert app._events_unread_count == 0

