"""RUNTIME_SLICE_0001 — Body Structure Evidence Seed.

First (red) test for the single negative causal loop:

    module attach requested WITHOUT passport
      -> rejected (runtime/policy owner)
      -> reason_code MODULE_PASSPORT_MISSING
      -> audit event recorded
      -> read-only ORION evidence stub surfaces rejection as a fact

Until the minimal body-structure / attach-rejection contour exists this module
fails to import (clear "no contour" failure), which is the intended first red.

Scope guard: this test exercises ONLY the loop above. It must not require
Face Map geometry, Thrust/Torque, bayonet hard-lock physics, module economy,
the full 4908 ORION Evidence Card, MFD, NATS/proto/telemetry, etc.
"""

from __future__ import annotations

import pytest

# Slice 0001 runtime/policy contour (does not exist yet -> ImportError = first red).
from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    EventStoreRejectionSink,
    ModuleAttachRequest,
    ModulePassport,
    RejectionAuditEvent,
    attach_module,
    MODULE_PASSPORT_MISSING,
)
from qiki.services.q_core_agent.core.event_store import EventStore

# Read-only ORION evidence stub (consumer only; never validates the passport itself).
from qiki.services.operator_console.orion_v.body_structure_evidence import (
    rejection_to_evidence,
)


class _RecordingAudit:
    """Minimal audit sink for the test: records rejection events as emitted."""

    def __init__(self) -> None:
        self.events: list = []

    def append_rejection(self, event) -> None:
        self.events.append(event)


def test_attach_without_passport_rejected_with_reason_audit_and_evidence() -> None:
    # Given: body_config exists, bayonet_A / bayonet_B exist (skeleton state).
    body = BodyConfigSnapshot.skeleton()
    assert "bayonet_A" in body.bayonet_states
    assert "bayonet_B" in body.bayonet_states
    # Face Map skeleton F00-F11 present, marked skeleton (no geometry claimed).
    assert "F00" in body.face_ids and "F11" in body.face_ids
    assert len(body.face_ids) == 12
    assert body.face_map_status == "skeleton"

    # Given: a module attach is requested with NO passport.
    audit = _RecordingAudit()
    request = ModuleAttachRequest(
        request_id="req-1",
        module_id="mod-x",
        mount_point="F06",
        passport=None,
    )

    # When: the runtime/policy layer validates the attach.
    result = attach_module(body, request, audit_sink=audit)

    # Then: attach is rejected with the stable domain reason.
    assert result.rejected is True
    assert result.reason_code == MODULE_PASSPORT_MISSING
    assert MODULE_PASSPORT_MISSING == "MODULE_PASSPORT_MISSING"

    # Then: no module becomes runtime-ready.
    assert result.runtime_ready is False

    # Then: exactly one audit event is recorded, carrying the required fields.
    assert len(audit.events) == 1
    event = audit.events[0]
    assert event.reason_code == MODULE_PASSPORT_MISSING
    assert event.request_id == "req-1"
    assert event.attempted_mount == "F06"
    assert event.source_owner  # non-empty runtime/policy owner (not ORION)
    assert event.timestamp is not None
    assert event.module_id == "mod-x"
    assert result.module_id == "mod-x"

    # Then: the read-only ORION evidence stub can surface the rejection as a fact.
    # The stub is given the already-produced rejection + audit event; it must not
    # call the attach policy or validate the passport itself.
    evidence = rejection_to_evidence(result, event)
    assert evidence.reason_code == MODULE_PASSPORT_MISSING
    assert evidence.rejection_state in {"rejected", "attach_rejected"}
    assert evidence.source_owner == event.source_owner

    # forbidden-wording guard: ONLY on the operator-facing string the stub produces.
    text = evidence.operator_text.lower()
    for banned in (
        "module installed",
        "module active",
        "bridge allowed",
        "hard lock verified",
        "runtime conforms",
        "qiki body implemented",
    ):
        assert banned not in text
    # honest rejection phrasing.
    assert "passport" in text

    # the stub actually reads the AUDIT event (closes audit-event -> evidence loop).
    assert evidence.audit_request_id == event.request_id
    assert evidence.audit_attempted_mount == event.attempted_mount

    # IF-ORION-EVIDENCE-001-aligned fields (still a stub, not the full #4908 card).
    assert evidence.module_id == "mod-x"
    assert evidence.claim_type == "module_attach_rejection"
    assert evidence.source_type == "audit"
    assert evidence.read_only is True


def test_passport_with_whitespace_fields_is_treated_as_missing() -> None:
    body = BodyConfigSnapshot.skeleton()
    audit = _RecordingAudit()
    request = ModuleAttachRequest(
        request_id="req-2",
        module_id="mod-y",
        mount_point="F07",
        passport=ModulePassport(module_id="  ", module_class="\t", mount_point=" "),
    )

    result = attach_module(body, request, audit_sink=audit)

    assert result.rejected is True
    assert result.reason_code == MODULE_PASSPORT_MISSING
    assert result.runtime_ready is False
    assert len(audit.events) == 1
    assert audit.events[0].reason_code == MODULE_PASSPORT_MISSING


def test_rejection_is_recorded_into_shared_event_store_as_system_event() -> None:
    # Reuses the existing audit layer (event_store.SystemEvent), no second format.
    store = EventStore(backend="memory")
    sink = EventStoreRejectionSink(store)
    body = BodyConfigSnapshot.skeleton()
    request = ModuleAttachRequest(
        request_id="req-3", module_id="mod-z", mount_point="F08", passport=None
    )

    result = attach_module(body, request, audit_sink=sink)
    assert result.reason_code == MODULE_PASSPORT_MISSING

    recorded = store.recent(5)
    assert len(recorded) == 1
    sys_event = recorded[0]
    assert sys_event.event_type == "module_attach_rejected"
    assert sys_event.reason == MODULE_PASSPORT_MISSING
    assert sys_event.payload["request_id"] == "req-3"
    assert sys_event.payload["module_id"] == "mod-z"
    assert sys_event.payload["attempted_mount"] == "F08"
    assert sys_event.payload["reason_code"] == MODULE_PASSPORT_MISSING


def test_evidence_stub_refuses_inconsistent_rejection_and_audit() -> None:
    body = BodyConfigSnapshot.skeleton()
    audit = _RecordingAudit()
    request = ModuleAttachRequest(
        request_id="req-4", module_id="mod-w", mount_point="F09", passport=None
    )
    result = attach_module(body, request, audit_sink=audit)

    # Tamper: an audit event whose reason disagrees with the result.
    bad_event = RejectionAuditEvent(
        reason_code="SOMETHING_ELSE",
        request_id="req-4",
        module_id=result.module_id,
        attempted_mount="F09",
        source_owner=result.source_owner,
        timestamp=1.0,
    )
    with pytest.raises(ValueError):
        rejection_to_evidence(result, bad_event)
