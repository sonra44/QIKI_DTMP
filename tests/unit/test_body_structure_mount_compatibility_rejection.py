"""RUNTIME_SLICE_0005 — Mount Compatibility Guard / Forbidden Module Class Rejection.

Cycle 1 RED test. A structurally valid passport on a FREE mount point is still
rejected if the module_class is forbidden for that face by the Face Map mount rules.
reason_code MODULE_MOUNT_CLASS_FORBIDDEN, no body_config mutation, audit, Evidence Card.

Fails to import until ``MODULE_MOUNT_CLASS_FORBIDDEN`` exists (intended first red).

Note: the allowed/forbidden classes are a runtime skeleton / TEST FIXTURE rule, NOT canon.
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    EventStoreRegistrationSink,
    ModuleAttachRequest,
    ModulePassport,
    register_module,
    MODULE_MOUNT_CLASS_FORBIDDEN,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.operator_console.orion_v.evidence_card import (
    CARD_TYPE_BODY_MODULE_ATTACH_REJECTION,
    evidence_card_from_audit_event,
)

_BANNED = (
    "attached",
    "runtime-ready",
    "reactor runtime",
    "capabilities active",
    "power available",
    "thermally cleared",
    "override",
)


def test_valid_passport_with_forbidden_mount_class_is_rejected_and_audited() -> None:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    # Given: F06 is free, and reactor-class is forbidden there (fixture rule).
    assert body.face_occupancy["F06"] == "free"

    passport = ModulePassport("test_forbidden_module_001", "reactor-class", "F06")
    request = ModuleAttachRequest("req-1", "test_forbidden_module_001", "F06", passport=passport)
    result, body_after = register_module(
        body, request, audit_sink=EventStoreRegistrationSink(store)
    )

    # Then: rejected for forbidden class.
    assert result.status == "rejected"
    assert result.reason_code == MODULE_MOUNT_CLASS_FORBIDDEN
    assert result.module_id == "test_forbidden_module_001"
    assert result.mount_point == "F06"
    assert result.body_config_updated is False
    assert result.runtime_ready is False

    # Then: F06 stays free, module not registered.
    assert body_after.face_occupancy["F06"] == "free"
    assert all(m["module_id"] != "test_forbidden_module_001" for m in body_after.modules)

    # Then: audit event records the forbidden-class rejection.
    rejection = store.recent(1)[0]
    assert rejection.event_type == "module_attach_rejected"
    assert rejection.reason == MODULE_MOUNT_CLASS_FORBIDDEN
    assert rejection.payload["module_id"] == "test_forbidden_module_001"
    assert rejection.payload["module_class"] == "reactor-class"
    assert rejection.payload["mount_point"] == "F06"
    assert rejection.payload["reason_code"] == MODULE_MOUNT_CLASS_FORBIDDEN

    # Then: Evidence Card surfaces it from the audit source.
    card = evidence_card_from_audit_event(rejection)
    assert card.card_type == CARD_TYPE_BODY_MODULE_ATTACH_REJECTION
    assert card.subject_id == "test_forbidden_module_001"
    assert card.subject_status == "rejected"
    assert card.reason_code == MODULE_MOUNT_CLASS_FORBIDDEN
    assert card.source_type == "audit"
    assert card.trust_status == "trusted"
    assert card.status == "implemented"
    assert card.read_only is True
    assert card.facts.get("module_class") == "reactor-class"

    # Then: no reactor/capability/attachment claim.
    text = card.operator_summary.lower()
    for banned in _BANNED:
        assert banned not in text


def test_free_mount_is_not_sufficient_when_module_class_is_forbidden() -> None:
    """Invariant: passport-valid + mount-free is NOT enough; the class must be allowed."""
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    assert body.face_occupancy["F06"] == "free"

    passport = ModulePassport("test_forbidden_module_001", "reactor-class", "F06")
    request = ModuleAttachRequest("req-1", "test_forbidden_module_001", "F06", passport=passport)
    result, body_after = register_module(
        body, request, audit_sink=EventStoreRegistrationSink(store)
    )

    assert result.status == "rejected"
    assert result.reason_code == MODULE_MOUNT_CLASS_FORBIDDEN
    # body_config completely unchanged.
    assert body_after.modules == ()
    assert body_after.face_occupancy["F06"] == "free"


def test_module_class_is_normalized_before_mount_class_check() -> None:
    """REMEDIATION H6: module_class is compared normalized (stripped), so a trailing-space
    class that is actually allowed is NOT falsely rejected as MODULE_MOUNT_CLASS_FORBIDDEN."""
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    # "sensor " (trailing space) is the allowed class "sensor".
    passport = ModulePassport("mod-x", "sensor ", "F06")
    request = ModuleAttachRequest("r", "mod-x", "F06", passport=passport)
    result, body_after = register_module(
        body, request, audit_sink=EventStoreRegistrationSink(store)
    )

    assert result.reason_code != MODULE_MOUNT_CLASS_FORBIDDEN
    assert result.status == "attached"
    assert body_after.face_occupancy["F06"] == "mod-x"
