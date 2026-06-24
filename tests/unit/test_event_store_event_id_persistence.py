"""REMEDIATION H4 — durable EventStore backends must persist the real event_id.

Audit finding H4: the sqlite backend does not store event_id; _query_sqlite reconstructs
a SYNTHETIC id ("sqlite:{idx}:{ts}"). So an event's audit identity is not stable across a
query/restart on a durable backend — which breaks the H3 audit-id causality the moment a
real backend is used.

These tests append an event (whose real uuid event_id is returned by append_new) and then
query it back through the sqlite path, asserting the queried event keeps the SAME id.
"""

from __future__ import annotations

import pytest

from qiki.services.q_core_agent.core.event_store import EventStore


@pytest.mark.parametrize("backend", ["sqlite", "hybrid"])
def test_event_store_preserves_event_id_across_query(backend: str, tmp_path) -> None:
    store = EventStore(backend=backend, db_path=str(tmp_path / f"ev_{backend}.sqlite"))
    try:
        event = store.append_new(
            subsystem="attach_validator",
            event_type="module_attach_rejected",
            payload={"module_id": "mod-x"},
            reason="MODULE_PASSPORT_MISSING",
        )
        written_id = event.event_id
        store._flush_sqlite_writer()  # ensure the async writer has persisted the row

        queried = store.query()
        match = [e for e in queried if e.event_type == "module_attach_rejected"]

        assert match, "event not found via sqlite query"
        assert match[0].event_id == written_id
        assert not match[0].event_id.startswith("sqlite:")
    finally:
        store.close()
