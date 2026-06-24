"""RUNTIME_SLICE_0004 — Mount Occupancy Guard / Duplicate Attach Rejection.

Cycle 1 RED test. Once a mount point is occupied (Slice 0003 registration), a second
valid module targeting the same mount point must be REJECTED with MOUNT_POINT_OCCUPIED.
The existing module stays attached, the new module is never registered, body_config is
not mutated, the rejection is audited, and an Evidence Card surfaces it read-only.

Fails to import until ``MOUNT_POINT_OCCUPIED`` exists (intended first red).

Hard boundary: this is a rejection, NOT a replace/detach/override. No silent overwrite.
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    EventStoreRegistrationSink,
    ModuleAttachRequest,
    ModulePassport,
    register_module,
    MOUNT_POINT_OCCUPIED,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.operator_console.orion_v.evidence_card import (
    CARD_TYPE_BODY_MODULE_ATTACH_REJECTION,
    evidence_card_from_audit_event,
)


def _register_first_module(store: EventStore) -> BodyConfigSnapshot:
    body = BodyConfigSnapshot.skeleton()
    passport = ModulePassport("test_sensor_module_001", "sensor", "F06")
    request = ModuleAttachRequest("req-1", "test_sensor_module_001", "F06", passport=passport)
    result, body = register_module(body, request, audit_sink=EventStoreRegistrationSink(store))
    assert result.status == "attached"
    assert body.face_occupancy["F06"] == "test_sensor_module_001"
    return body


def test_attach_second_module_to_occupied_mount_is_rejected_and_audited() -> None:
    store = EventStore(backend="memory")
    body = _register_first_module(store)

    # When: a second valid module targets the already-occupied F06.
    passport2 = ModulePassport("test_sensor_module_002", "sensor", "F06")
    request2 = ModuleAttachRequest("req-2", "test_sensor_module_002", "F06", passport=passport2)
    result, body_after = register_module(
        body, request2, audit_sink=EventStoreRegistrationSink(store)
    )

    # Then: rejected with the stable occupancy reason code.
    assert result.status == "rejected"
    assert result.reason_code == MOUNT_POINT_OCCUPIED
    assert result.requested_module_id == "test_sensor_module_002"
    assert result.existing_module_id == "test_sensor_module_001"
    assert result.body_config_updated is False
    assert result.runtime_ready is False

    # Then: existing module preserved; new module NOT registered; mount unchanged.
    assert body_after.face_occupancy["F06"] == "test_sensor_module_001"
    assert all(m["module_id"] != "test_sensor_module_002" for m in body_after.modules)
    existing = next(m for m in body_after.modules if m["module_id"] == "test_sensor_module_001")
    assert existing["status"] == "attached"
    assert existing["passport_status"] == "validated"
    assert existing["capability_status"] in {"inactive", "not_evaluated"}

    # Then: the occupied-mount rejection is audited (programmatically assertable).
    rejection = store.recent(5)[-1]
    assert rejection.event_type == "module_attach_rejected"
    assert rejection.reason == MOUNT_POINT_OCCUPIED
    assert rejection.payload["requested_module_id"] == "test_sensor_module_002"
    assert rejection.payload["existing_module_id"] == "test_sensor_module_001"
    assert rejection.payload["mount_point"] == "F06"
    assert rejection.payload["reason_code"] == MOUNT_POINT_OCCUPIED
    assert rejection.payload["body_config_updated"] is False

    # Then: an Evidence Card surfaces the rejection from the audit source.
    card = evidence_card_from_audit_event(rejection)
    assert card.card_type == CARD_TYPE_BODY_MODULE_ATTACH_REJECTION
    assert card.subject_type == "module"
    assert card.subject_id == "test_sensor_module_002"
    assert card.subject_status == "rejected"
    assert card.reason_code == MOUNT_POINT_OCCUPIED
    assert card.source_type == "audit"
    assert card.trust_status == "trusted"
    # cross-review lesson: a fully audit-backed rejection must report "implemented".
    assert card.status == "implemented"
    assert card.read_only is True
    assert card.facts.get("existing_module_id") == "test_sensor_module_001"
    assert card.facts.get("requested_module_id") == "test_sensor_module_002"

    # Then: the card must NOT claim replacement / detach / override / second-module attach.
    text = card.operator_summary.lower()
    for banned in (
        "attached",
        "runtime-ready",
        "detached",
        "replacement",
        "override",
        "conflict resolved",
    ):
        assert banned not in text


def test_occupied_mount_rejection_does_not_overwrite_existing_module() -> None:
    """Invariant: the occupancy rejection is a refusal, never a silent replace/detach."""
    store = EventStore(backend="memory")
    body = _register_first_module(store)
    existing_before = dict(
        next(m for m in body.modules if m["module_id"] == "test_sensor_module_001")
    )

    passport2 = ModulePassport("test_sensor_module_002", "sensor", "F06")
    request2 = ModuleAttachRequest("req-2", "test_sensor_module_002", "F06", passport=passport2)
    result, body_after = register_module(
        body, request2, audit_sink=EventStoreRegistrationSink(store)
    )

    assert result.status == "rejected"

    # the existing module entry is unchanged field-for-field.
    existing_after = dict(
        next(m for m in body_after.modules if m["module_id"] == "test_sensor_module_001")
    )
    assert existing_after == existing_before
    assert existing_after["status"] == "attached"
    assert existing_after["passport_status"] == "validated"
    assert existing_after["capability_status"] == "inactive"
    # exactly one module remains — no second entry was created.
    assert len(body_after.modules) == 1

    # no detach / replace audit event was emitted — only the registration + one rejection.
    event_types = [e.event_type for e in store.recent(10)]
    assert "module_detached" not in event_types
    assert "module_replaced" not in event_types
    assert event_types.count("module_attach_rejected") == 1

    # the rejection audit preserves the originating request link (Codex review note).
    rejection = next(e for e in store.recent(10) if e.event_type == "module_attach_rejected")
    assert rejection.payload.get("request_id") == "req-2"
    card = evidence_card_from_audit_event(rejection)
    assert card.related_command_id == "req-2"
