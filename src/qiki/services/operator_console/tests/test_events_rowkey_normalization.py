from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


class _RowKey:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:  # pragma: no cover
        return f"RowKey({self.value})"


@pytest.mark.asyncio
async def test_events_row_highlight_uses_row_key_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rules_path = tmp_path / "incident_rules.yaml"
    history_path = tmp_path / "incident_rules.history.jsonl"
    rules_path.write_text(RULES, encoding="utf-8")

    monkeypatch.setenv("OPERATOR_CONSOLE_INCIDENT_RULES", str(rules_path))
    monkeypatch.setenv("OPERATOR_CONSOLE_INCIDENT_RULES_HISTORY", str(history_path))

    app = OrionApp()
    # Don't require a running Textual screen stack in this unit test.
    app.active_screen = "system"

    await app.handle_event_data(
        {"subject": "sensor.temp", "data": {"source": "thermal", "subject": "core", "temp": 80}}
    )

    assert app._incident_store is not None
    incidents = app._incident_store.list_incidents()
    assert len(incidents) == 1

    inc_id = incidents[0].incident_id

    dummy_table = SimpleNamespace(id="events-table")
    event = SimpleNamespace(data_table=dummy_table, row_key=_RowKey(inc_id))

    app.on_data_table_row_highlighted(event)

    assert app._selection_by_app["events"].key == inc_id
