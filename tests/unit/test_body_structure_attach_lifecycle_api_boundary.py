"""Attach lifecycle API boundary hardening.

These tests prevent future agents from treating the legacy Slice 0001 helper
``attach_module`` as the current full module attach lifecycle. The current
0001-0008 lifecycle entrypoint is ``run_attach_pipeline``.
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    CURRENT_ATTACH_LIFECYCLE_ENTRYPOINT,
    LEGACY_ATTACH_LIFECYCLE_HELPER,
    BodyConfigSnapshot,
    EventStoreRejectionSink,
    ModuleAttachRequest,
    ModulePassport,
    attach_lifecycle_entrypoint_name,
    attach_module,
    run_attach_pipeline,
)
from qiki.services.q_core_agent.core.event_store import EventStore


def _valid_request(request_id: str = "req-api") -> ModuleAttachRequest:
    return ModuleAttachRequest(
        request_id=request_id,
        module_id="test_sensor_module_001",
        mount_point="F06",
        passport=ModulePassport("test_sensor_module_001", "sensor", "F06"),
    )


def test_current_attach_lifecycle_entrypoint_is_explicit() -> None:
    assert CURRENT_ATTACH_LIFECYCLE_ENTRYPOINT == "run_attach_pipeline"
    assert LEGACY_ATTACH_LIFECYCLE_HELPER == "attach_module"
    assert attach_lifecycle_entrypoint_name() == CURRENT_ATTACH_LIFECYCLE_ENTRYPOINT


def test_run_attach_pipeline_is_the_full_lifecycle_entrypoint_for_valid_attach() -> None:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")

    decision, updated = run_attach_pipeline(body, _valid_request(), store=store)

    assert decision.status == "attached"
    assert decision.stage == "registration"
    assert decision.audit_event_id
    assert decision.evidence_card_id
    assert decision.body_config_updated is True
    assert decision.runtime_ready is False
    assert updated.face_occupancy["F06"] == "test_sensor_module_001"


def test_attach_module_remains_legacy_negative_path_helper_not_full_lifecycle() -> None:
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")

    result = attach_module(
        body,
        _valid_request("req-legacy"),
        audit_sink=EventStoreRejectionSink(store),
    )

    assert result.rejected is True
    assert result.reason_code == "MODULE_ATTACH_NOT_IMPLEMENTED"
    assert result.runtime_ready is False
    assert store.recent(10) == []
    assert body.face_occupancy["F06"] == "free"


def test_legacy_attach_module_result_does_not_disprove_pipeline_implementation() -> None:
    body = BodyConfigSnapshot.skeleton()

    legacy_store = EventStore(backend="memory")
    legacy = attach_module(
        body,
        _valid_request("req-legacy-boundary"),
        audit_sink=EventStoreRejectionSink(legacy_store),
    )
    assert legacy.reason_code == "MODULE_ATTACH_NOT_IMPLEMENTED"

    pipeline_store = EventStore(backend="memory")
    decision, _updated = run_attach_pipeline(
        body,
        _valid_request("req-pipeline-boundary"),
        store=pipeline_store,
    )

    assert decision.status == "attached"
    assert decision.reason_code is None
    assert decision.stage == "registration"
