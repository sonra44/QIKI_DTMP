"""RUNTIME_SLICE_0007 — Mount Point Existence Guard / Unknown Mount Rejection.

Cycle 1 RED test. A structurally valid passport pointing at a mount_point the body
does not know (e.g. F99) is rejected with MOUNT_POINT_UNKNOWN, BEFORE occupancy /
compatibility checks. The unknown mount is NOT auto-created; body_config is not mutated;
audit + read-only Evidence Card.

Fails to import until ``MOUNT_POINT_UNKNOWN`` exists (intended first red).
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    EventStoreRegistrationSink,
    ModuleAttachRequest,
    ModulePassport,
    register_module,
    MOUNT_POINT_UNKNOWN,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.operator_console.orion_v.evidence_card import (
    CARD_TYPE_BODY_MODULE_ATTACH_REJECTION,
    evidence_card_from_audit_event,
)


def test_valid_passport_with_unknown_mount_point_is_rejected_and_audited() -> None:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    assert "F99" not in body.face_occupancy  # unknown mount

    passport = ModulePassport("test_sensor_module_001", "sensor", "F99")
    request = ModuleAttachRequest("req-1", "test_sensor_module_001", "F99", passport=passport)
    result, body_after = register_module(
        body, request, audit_sink=EventStoreRegistrationSink(store)
    )

    assert result.status == "rejected"
    assert result.reason_code == MOUNT_POINT_UNKNOWN
    assert result.mount_point == "F99"
    assert result.known_mount is False
    assert result.body_config_updated is False
    assert result.runtime_ready is False

    # F99 is NOT created; nothing registered.
    assert "F99" not in body_after.face_occupancy
    assert body_after.modules == ()

    # audit.
    rejection = store.recent(1)[0]
    assert rejection.event_type == "module_attach_rejected"
    assert rejection.reason == MOUNT_POINT_UNKNOWN
    assert rejection.payload["mount_point"] == "F99"
    assert rejection.payload["reason_code"] == MOUNT_POINT_UNKNOWN
    assert rejection.payload["known_mount"] is False

    # evidence card.
    card = evidence_card_from_audit_event(rejection)
    assert card.card_type == CARD_TYPE_BODY_MODULE_ATTACH_REJECTION
    assert card.subject_id == "test_sensor_module_001"
    assert card.reason_code == MOUNT_POINT_UNKNOWN
    assert card.source_type == "audit_event"
    assert card.status == "implemented"
    assert card.read_only is True
    assert card.facts.get("known_mount") is False

    text = card.operator_summary.lower()
    for banned in ("attached", "f99 exists", "f99 created", "runtime-ready", "override"):
        assert banned not in text


def test_unknown_mount_rejection_does_not_create_mount_point() -> None:
    """Invariant: an unknown mount is rejected, never auto-created or reserved."""
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    faces_before = set(body.face_occupancy.keys())

    passport = ModulePassport("test_sensor_module_001", "sensor", "F99")
    request = ModuleAttachRequest("req-1", "test_sensor_module_001", "F99", passport=passport)
    result, body_after = register_module(
        body, request, audit_sink=EventStoreRegistrationSink(store)
    )

    assert result.reason_code == MOUNT_POINT_UNKNOWN
    # Face Map keys unchanged — F99 not created.
    assert set(body_after.face_occupancy.keys()) == faces_before
    assert "F99" not in body_after.face_occupancy
    assert body_after.modules == ()
