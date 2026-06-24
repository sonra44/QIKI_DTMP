"""Phase 4 #10 — module attach audit payloads expose IF-AUDIT aliases.

QIKI Body v0.2.2 IF-AUDIT-001 requires audit events to carry source,
command_id, previous_state, new_state, reason_codes, effect_state, severity,
and blackbox_relevance. These tests pin conservative audit-level aliases:
they are not full runtime snapshots and not effect confirmation.
"""

from __future__ import annotations

import pytest

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    EventStoreRegistrationSink,
    MODULE_MOUNT_CLASS_FORBIDDEN,
    MODULE_PASSPORT_INVALID,
    MODULE_PASSPORT_MISSING,
    MOUNT_POINT_OCCUPIED,
    MOUNT_POINT_UNKNOWN,
    ModuleAttachRequest,
    ModulePassport,
    register_module,
    run_attach_pipeline,
)
from qiki.services.q_core_agent.core.event_store import EventStore

_MID = "test_sensor_module_001"


def _occupied_body() -> BodyConfigSnapshot:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    request = ModuleAttachRequest(
        request_id="req-occupied-seed",
        module_id="existing_module",
        mount_point="F06",
        passport=ModulePassport("existing_module", "sensor", "F06"),
    )
    _, body = register_module(body, request, audit_sink=EventStoreRegistrationSink(store))
    return body


def _case_missing() -> tuple[BodyConfigSnapshot, ModuleAttachRequest, str, str]:
    return (
        BodyConfigSnapshot.skeleton(),
        ModuleAttachRequest("req-missing", _MID, "F06", passport=None),
        MODULE_PASSPORT_MISSING,
        "req-missing",
    )


def _case_invalid() -> tuple[BodyConfigSnapshot, ModuleAttachRequest, str, str]:
    return (
        BodyConfigSnapshot.skeleton(),
        ModuleAttachRequest("req-invalid", _MID, "F06", passport=ModulePassport("other", "sensor", "F06")),
        MODULE_PASSPORT_INVALID,
        "req-invalid",
    )


def _case_unknown() -> tuple[BodyConfigSnapshot, ModuleAttachRequest, str, str]:
    return (
        BodyConfigSnapshot.skeleton(),
        ModuleAttachRequest("req-unknown", _MID, "F99", passport=ModulePassport(_MID, "sensor", "F99")),
        MOUNT_POINT_UNKNOWN,
        "req-unknown",
    )


def _case_occupied() -> tuple[BodyConfigSnapshot, ModuleAttachRequest, str, str]:
    return (
        _occupied_body(),
        ModuleAttachRequest("req-occupied", _MID, "F06", passport=ModulePassport(_MID, "sensor", "F06")),
        MOUNT_POINT_OCCUPIED,
        "req-occupied",
    )


def _case_forbidden() -> tuple[BodyConfigSnapshot, ModuleAttachRequest, str, str]:
    return (
        BodyConfigSnapshot.skeleton(),
        ModuleAttachRequest("req-forbidden", _MID, "F06", passport=ModulePassport(_MID, "reactor-class", "F06")),
        MODULE_MOUNT_CLASS_FORBIDDEN,
        "req-forbidden",
    )


@pytest.mark.parametrize(
    "case_factory",
    [_case_missing, _case_invalid, _case_unknown, _case_occupied, _case_forbidden],
)
def test_rejection_audit_payload_exposes_if_audit_aliases(case_factory) -> None:
    body, request, reason_code, command_id = case_factory()
    store = EventStore(backend="memory")

    decision, _ = run_attach_pipeline(body, request, store=store)
    event = next(e for e in store.recent(20) if e.event_id == decision.audit_event_id)
    payload = event.payload

    assert payload["source"] == payload["source_owner"] == event.subsystem
    assert payload["command_id"] == command_id == payload["request_id"]
    assert payload["previous_state"] == "attach_requested"
    assert payload["new_state"] == "attach_rejected"
    assert payload["reason_codes"] == [reason_code]
    assert payload["effect_state"] == "not_applied"
    assert payload["severity"] == "warning"
    assert payload["blackbox_relevance"] is False
    assert payload["module_id"]


def test_registration_audit_payload_exposes_if_audit_aliases_without_runtime_overclaim() -> None:
    body = BodyConfigSnapshot.skeleton()
    request = ModuleAttachRequest(
        request_id="req-valid",
        module_id=_MID,
        mount_point="F06",
        passport=ModulePassport(_MID, "sensor", "F06"),
    )
    store = EventStore(backend="memory")

    decision, _ = run_attach_pipeline(body, request, store=store)
    event = next(e for e in store.recent(20) if e.event_id == decision.audit_event_id)
    payload = event.payload

    assert event.event_type == "module_attach_registered"
    assert payload["source"] == payload["source_owner"] == event.subsystem
    assert payload["command_id"] == "req-valid"
    assert payload["previous_state"] == "attach_requested"
    assert payload["new_state"] == "module_registered"
    assert payload["reason_codes"] == []
    assert payload["effect_state"] == "registry_updated"
    assert payload["severity"] == "info"
    assert payload["blackbox_relevance"] is False
    assert payload["module_id"] == _MID
    assert payload["runtime_ready"] is False
    assert payload["capability_status"] == "inactive"
