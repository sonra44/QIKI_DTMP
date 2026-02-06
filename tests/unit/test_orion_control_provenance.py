from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_provenance_marker_classifies_events_and_control_subjects() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp
    from qiki.shared.nats_subjects import RESPONSES_CONTROL

    events_trusted = OrionApp._provenance_marker(channel="events", subject="qiki.events.v1.audit")
    events_untrusted = OrionApp._provenance_marker(channel="events", subject="evil.events.v1.audit")
    control_trusted = OrionApp._provenance_marker(channel="control_response", subject=RESPONSES_CONTROL)
    control_untrusted = OrionApp._provenance_marker(channel="control_response", subject="qiki.responses.fake")

    assert events_trusted == "TRUSTED"
    assert events_untrusted == "UNTRUSTED"
    assert control_trusted == "TRUSTED"
    assert control_untrusted == "UNTRUSTED"


@pytest.mark.asyncio
async def test_control_response_log_contains_provenance_marker() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp
    from qiki.shared.nats_subjects import RESPONSES_CONTROL

    app = OrionApp()
    messages: list[tuple[str, str]] = []
    app._console_log = lambda msg, level="info": messages.append((str(msg), str(level)))  # type: ignore[method-assign]

    await app.handle_control_response(
        {
            "subject": RESPONSES_CONTROL,
            "data": {"success": True, "request_id": "req-1", "payload": {"status": "ok"}},
        }
    )
    await app.handle_control_response(
        {
            "subject": "qiki.responses.rogue",
            "data": {"success": True, "request_id": "req-2"},
        }
    )

    assert any("[TRUSTED]:" in msg and level == "info" for msg, level in messages)
    assert any("[UNTRUSTED]:" in msg and level == "warning" for msg, level in messages)


def test_events_table_row_includes_trust_column() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._incident_store = object()
    app._events_filtered_sorted = lambda: [  # type: ignore[method-assign]
        SimpleNamespace(
            incident_id="inc-1",
            severity="warning",
            type="bios",
            source="bios",
            subject="qiki.events.v1.bios_status",
            last_seen=1_700_000_000.0,
            first_seen=1_700_000_000.0,
            count=1,
            acked=False,
            rule_id="RULE_1",
        )
    ]

    captured_rows: list[tuple[object, ...]] = []

    class _FakeTable:
        id = "events-table"
        cursor_row = 0

        def move_cursor(self, **_kwargs: object) -> None:
            return

    app.query_one = lambda _selector, _cls=None: _FakeTable()  # type: ignore[method-assign]
    app._sync_datatable_rows = lambda _table, rows: captured_rows.extend(rows)  # type: ignore[method-assign]

    app._render_events_table()

    assert captured_rows
    # row layout: key, severity, type, source, subject, trust, age, count, ack
    assert captured_rows[0][5] == "TRUSTED"
