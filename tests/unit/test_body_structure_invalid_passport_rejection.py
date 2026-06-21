"""RUNTIME_SLICE_0006 — Module Passport Integrity Guard / Invalid Passport Rejection.

Cycle 1 RED test. A passport that is PRESENT but structurally invalid (first case:
its module_id does not match the attach request) is rejected with MODULE_PASSPORT_INVALID
BEFORE any mount occupancy / compatibility check. No body_config mutation; audit;
read-only Evidence Card.

Fails to import until ``MODULE_PASSPORT_INVALID`` exists (intended first red).
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    EventStoreRegistrationSink,
    ModuleAttachRequest,
    ModulePassport,
    register_module,
    MODULE_PASSPORT_INVALID,
    MOUNT_POINT_OCCUPIED,
    MODULE_MOUNT_CLASS_FORBIDDEN,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.operator_console.orion_v.evidence_card import (
    CARD_TYPE_BODY_MODULE_ATTACH_REJECTION,
    evidence_card_from_audit_event,
)


def test_present_but_invalid_passport_is_rejected_before_mount_validation() -> None:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    # passport is present and well-shaped, but its module_id mismatches the request.
    passport = ModulePassport("other_module_id", "sensor", "F06")
    request = ModuleAttachRequest("req-1", "test_sensor_module_001", "F06", passport=passport)

    result, body_after = register_module(
        body, request, audit_sink=EventStoreRegistrationSink(store)
    )

    assert result.status == "rejected"
    assert result.reason_code == MODULE_PASSPORT_INVALID
    assert result.validation_error == "module_id_mismatch"
    assert result.passport_module_id == "other_module_id"
    assert result.body_config_updated is False
    assert result.runtime_ready is False

    # body_config untouched.
    assert body_after.face_occupancy["F06"] == "free"
    assert body_after.modules == ()

    # audit (from the passport validator).
    rejection = store.recent(1)[0]
    assert rejection.event_type == "module_attach_rejected"
    assert rejection.reason == MODULE_PASSPORT_INVALID
    assert rejection.payload["reason_code"] == MODULE_PASSPORT_INVALID
    assert rejection.payload["validation_error"] == "module_id_mismatch"
    assert rejection.payload["module_id"] == "test_sensor_module_001"

    # evidence card.
    card = evidence_card_from_audit_event(rejection)
    assert card.card_type == CARD_TYPE_BODY_MODULE_ATTACH_REJECTION
    assert card.subject_id == "test_sensor_module_001"
    assert card.subject_status == "rejected"
    assert card.reason_code == MODULE_PASSPORT_INVALID
    assert card.source_type == "audit_event"
    assert card.status == "implemented"
    assert card.read_only is True
    assert card.facts.get("validation_error") == "module_id_mismatch"

    text = card.operator_summary.lower()
    for banned in (
        "attached",
        "runtime-ready",
        "mount checked",
        "class allowed",
        "capabilities active",
        "override",
    ):
        assert banned not in text


def test_invalid_passport_does_not_run_mount_occupancy_or_compatibility() -> None:
    """Invariant: invalid-passport rejection wins BEFORE occupancy / compatibility checks."""
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    # occupy F06 with a valid module first.
    p0 = ModulePassport("test_sensor_module_001", "sensor", "F06")
    r0 = ModuleAttachRequest("req-0", "test_sensor_module_001", "F06", passport=p0)
    _, body = register_module(body, r0, audit_sink=EventStoreRegistrationSink(store))

    # invalid passport (module_id mismatch) AND occupied mount AND forbidden class.
    bad_passport = ModulePassport("other_module_id", "reactor-class", "F06")
    bad_request = ModuleAttachRequest("req-1", "test_sensor_module_002", "F06", passport=bad_passport)
    result, body_after = register_module(
        body, bad_request, audit_sink=EventStoreRegistrationSink(store)
    )

    # invalid-passport reason wins; NOT occupied, NOT forbidden-class.
    assert result.reason_code == MODULE_PASSPORT_INVALID
    assert result.reason_code != MOUNT_POINT_OCCUPIED
    assert result.reason_code != MODULE_MOUNT_CLASS_FORBIDDEN
    # body unchanged — still exactly the first module.
    assert len(body_after.modules) == 1
    assert body_after.face_occupancy["F06"] == "test_sensor_module_001"
