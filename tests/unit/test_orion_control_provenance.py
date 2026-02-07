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


def test_events_text_filter_matches_trust_marker() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    class _FakeStore:
        def __init__(self) -> None:
            self._items = [
                SimpleNamespace(
                    incident_id="inc-trusted",
                    severity="W",
                    type="bios",
                    source="bios",
                    subject="qiki.events.v1.bios_status",
                    title="trusted event",
                    description="ok",
                    last_seen=1_700_000_001.0,
                    acked=False,
                ),
                SimpleNamespace(
                    incident_id="inc-untrusted",
                    severity="W",
                    type="bios",
                    source="rogue",
                    subject="evil.events.v1.bios_status",
                    title="untrusted event",
                    description="spoof",
                    last_seen=1_700_000_000.0,
                    acked=False,
                ),
            ]

        def refresh(self) -> None:
            return

        def list_incidents(self) -> list[SimpleNamespace]:
            return self._items

    app = OrionApp()
    app._incident_store = _FakeStore()

    app._events_filter_text = "trusted"
    trusted = app._events_filtered_sorted()
    assert [str(inc.incident_id) for inc in trusted] == ["inc-trusted"]

    app._events_filter_text = "untrusted"
    untrusted = app._events_filtered_sorted()
    assert [str(inc.incident_id) for inc in untrusted] == ["inc-untrusted"]


@pytest.mark.asyncio
async def test_trust_command_alias_sets_and_clears_events_filter_text() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._console_log = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    app._update_system_snapshot = lambda: None  # type: ignore[method-assign]
    app._render_events_table = lambda: None  # type: ignore[method-assign]
    app._render_summary_table = lambda: None  # type: ignore[method-assign]
    app._render_diagnostics_table = lambda: None  # type: ignore[method-assign]

    await app._run_command("s: trust untrusted")
    assert app._events_filter_text == "untrusted"

    await app._run_command("s: trust off")
    assert app._events_filter_text is None


@pytest.mark.asyncio
async def test_trust_command_routes_to_system_without_prefix() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._console_log = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    app._update_system_snapshot = lambda: None  # type: ignore[method-assign]
    app._render_events_table = lambda: None  # type: ignore[method-assign]
    app._render_summary_table = lambda: None  # type: ignore[method-assign]
    app._render_diagnostics_table = lambda: None  # type: ignore[method-assign]

    async def _unexpected_qiki(_text: str) -> None:
        raise AssertionError("trust command must route to system path")

    app._publish_qiki_intent = _unexpected_qiki  # type: ignore[method-assign]

    await app._run_command("trust untrusted")
    assert app._events_filter_text == "untrusted"


@pytest.mark.asyncio
async def test_ru_trust_alias_routes_to_system_without_prefix() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._console_log = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    app._update_system_snapshot = lambda: None  # type: ignore[method-assign]
    app._render_events_table = lambda: None  # type: ignore[method-assign]
    app._render_summary_table = lambda: None  # type: ignore[method-assign]
    app._render_diagnostics_table = lambda: None  # type: ignore[method-assign]

    async def _unexpected_qiki(_text: str) -> None:
        raise AssertionError("доверие команда должна идти в system path")

    app._publish_qiki_intent = _unexpected_qiki  # type: ignore[method-assign]

    await app._run_command("доверие untrusted")
    assert app._events_filter_text == "untrusted"


def test_command_placeholder_includes_trust_alias_for_discoverability() -> None:
    pytest.importorskip("textual")

    from qiki.services.operator_console.main_orion import OrionApp

    app = OrionApp()
    app._density = "normal"
    app._size = SimpleNamespace(width=400)

    class _FakeInput:
        placeholder = ""

    fake_input = _FakeInput()
    app.query_one = lambda _selector, _cls=None: fake_input  # type: ignore[method-assign]

    app._update_command_placeholder()

    assert "trust/доверие <trusted|untrusted|off>" in fake_input.placeholder
