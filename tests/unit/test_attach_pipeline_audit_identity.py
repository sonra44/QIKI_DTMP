"""REMEDIATION H3 — run_attach_pipeline must identify its audit event by the RETURNED
event id, not by position (store.recent(1)[0]).

Audit finding H3: the pipeline reads "the last event in the store" to obtain
audit_event_id / evidence_card_id. With a reused / shared / concurrent store, the last
event may not be the one this attach wrote, so the decision points at an unrelated event.

This test uses a store wrapper that lands an UNRELATED noise event right AFTER every
write (simulating a concurrent writer). On the buggy code, store.recent(1) returns the
noise event and the decision gets the wrong id (RED). The fix threads the real event id
returned by append_new through the sink and the result, so the decision is correct.
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    ModuleAttachRequest,
    ModulePassport,
    run_attach_pipeline,
)
from qiki.services.q_core_agent.core.event_store import EventStore


class _NoiseAfterStore:
    """Wraps EventStore; after each append_new it lands an unrelated event, so the most
    recent event is never the one the caller just wrote."""

    def __init__(self) -> None:
        self._real = EventStore(backend="memory")
        self._real.append_new(subsystem="noise", event_type="unrelated", payload={}, reason="")

    def append_new(self, **kwargs):
        event = self._real.append_new(**kwargs)
        # an unrelated concurrent writer lands AFTER our event:
        self._real.append_new(subsystem="noise", event_type="unrelated", payload={}, reason="")
        return event

    def recent(self, n: int = 20):
        return self._real.recent(n)

    def snapshot(self):
        return self._real.snapshot()


def test_attach_pipeline_uses_returned_audit_event_id_not_recent_last() -> None:
    store = _NoiseAfterStore()
    body = BodyConfigSnapshot.skeleton()
    request = ModuleAttachRequest(
        "r", "mod-x", "F06", passport=ModulePassport("mod-x", "sensor", "F06")
    )

    decision, _updated = run_attach_pipeline(body, request, store=store)

    # the attach's OWN audit event (identified by its payload), NOT the noise after it.
    attach_event = next(e for e in store.recent(50) if e.payload.get("module_id") == "mod-x")
    assert decision.audit_event_id == attach_event.event_id
    assert decision.evidence_card_id == f"card:{attach_event.event_id}"
