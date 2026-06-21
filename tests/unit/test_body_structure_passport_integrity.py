"""REMEDIATION Phase 1 — C1: passport.mount_point must match request.mount_point.

Audit finding C1: the slice-0006 integrity guard checks only module_id; a passport
whose mount_point differs from the request's mount_point is silently accepted and the
module registers at the request's mount point, defeating the passport as an
authorization document.

This test proves the bug (RED on current code: the module registers instead of being
rejected) and locks the fix: a mount_point mismatch is MODULE_PASSPORT_INVALID with
validation_error="mount_point_mismatch" (no new reason_code).

New-DoD invariants asserted here: returns the right reason, does NOT return a wrong
mount reason, and does NOT mutate body_config.
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
    MOUNT_POINT_UNKNOWN,
    MODULE_MOUNT_CLASS_FORBIDDEN,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.operator_console.orion_v.evidence_card import (
    CARD_TYPE_BODY_MODULE_ATTACH_REJECTION,
    evidence_card_from_audit_event,
)


def test_passport_mount_point_mismatch_is_rejected_as_invalid_passport() -> None:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")

    # module_id MATCHES the request; mount_point does NOT (passport says F01, request F06).
    passport = ModulePassport(module_id="mod-x", module_class="sensor", mount_point="F01")
    request = ModuleAttachRequest(
        request_id="r", module_id="mod-x", mount_point="F06", passport=passport
    )

    result, body_after = register_module(
        body, request, audit_sink=EventStoreRegistrationSink(store)
    )

    # rejected as an invalid passport (mount_point_mismatch).
    assert result.status == "rejected"
    assert result.reason_code == MODULE_PASSPORT_INVALID
    assert result.validation_error == "mount_point_mismatch"
    assert result.body_config_updated is False
    assert result.runtime_ready is False

    # exclusion: the mount checks must NOT be the reason (integrity fails first).
    assert result.reason_code != MOUNT_POINT_OCCUPIED
    assert result.reason_code != MOUNT_POINT_UNKNOWN
    assert result.reason_code != MODULE_MOUNT_CLASS_FORBIDDEN

    # no-mutation: module not registered, requested mount stays free.
    assert all(m["module_id"] != "mod-x" for m in body_after.modules)
    assert body_after.face_occupancy["F06"] == "free"
    assert body_after.modules == ()

    # audit records the invalid-passport rejection.
    rejection = store.recent(1)[0]
    assert rejection.event_type == "module_attach_rejected"
    assert rejection.reason == MODULE_PASSPORT_INVALID
    assert rejection.payload["reason_code"] == MODULE_PASSPORT_INVALID
    assert rejection.payload["validation_error"] == "mount_point_mismatch"

    # evidence card surfaces it, read-only.
    card = evidence_card_from_audit_event(rejection)
    assert card.card_type == CARD_TYPE_BODY_MODULE_ATTACH_REJECTION
    assert card.reason_code == MODULE_PASSPORT_INVALID
    assert card.read_only is True
    assert card.facts.get("validation_error") == "mount_point_mismatch"
