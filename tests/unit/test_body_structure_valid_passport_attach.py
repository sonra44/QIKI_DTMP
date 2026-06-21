"""RUNTIME_SLICE_0003 — Valid Module Passport Registration / Body Config Occupancy.

Cycle 1 RED test (positive mirror of Slice 0001/0002). A module with a valid
minimal passport is REGISTERED in body_config (attached / passport validated) and
occupies a mount point, recording an audit event and surfacing an Evidence Card —
WITHOUT activating any capability.

Fails to import until the Slice 0003 contour exists (intended first red).

Hard boundary: registration == occupancy/registry state only. It must NOT imply
power/thermal/command readiness; capabilities stay inactive; runtime_ready stays
False; no PDU/thermal/command unlocks.
"""

from __future__ import annotations

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    EventStoreRegistrationSink,
    ModuleAttachRequest,
    ModulePassport,
    register_module,
)
from qiki.services.q_core_agent.core.event_store import EventStore
from qiki.services.operator_console.orion_v.evidence_card import (
    CARD_TYPE_BODY_MODULE_ATTACH_REGISTERED,
    evidence_card_from_audit_event,
)


def test_valid_passport_module_attach_registers_body_config_and_evidence() -> None:
    body = BodyConfigSnapshot.skeleton()
    # Given: Face Map F00-F11 exists and F06 is free, no modules yet.
    assert "F06" in body.face_ids
    assert body.face_occupancy.get("F06") == "free"
    assert body.modules == ()

    # Given: a valid minimal passport targeting F06.
    store = EventStore(backend="memory")
    passport = ModulePassport(
        module_id="test_sensor_module_001",
        module_class="sensor",
        mount_point="F06",
    )
    request = ModuleAttachRequest(
        request_id="req-1",
        module_id="test_sensor_module_001",
        mount_point="F06",
        passport=passport,
    )

    # When: registering the module (runtime/policy owner of the decision).
    result, updated = register_module(
        body, request, audit_sink=EventStoreRegistrationSink(store)
    )

    # Then: result is an accepted registration, NOT capability activation.
    assert result.status == "attached"
    assert result.passport_status == "validated"
    assert result.body_config_updated is True
    assert result.runtime_ready is False
    assert result.capability_status in {"inactive", "not_evaluated"}
    assert result.reason_code is None

    # Then: body_config reflects the occupancy + module entry.
    assert updated.face_occupancy["F06"] == "test_sensor_module_001"
    entry = next(m for m in updated.modules if m["module_id"] == "test_sensor_module_001")
    assert entry["mount_point"] == "F06"
    assert entry["status"] == "attached"
    assert entry["passport_status"] == "validated"
    assert entry["capability_status"] in {"inactive", "not_evaluated"}
    # the original snapshot is unchanged (registration returns a new snapshot).
    assert body.face_occupancy.get("F06") == "free"

    # Then: an audit event records the registration.
    events = store.recent(1)
    assert len(events) == 1
    event = events[0]
    assert event.event_type == "module_attach_registered"
    assert event.payload["module_id"] == "test_sensor_module_001"
    assert event.payload["mount_point"] == "F06"
    assert event.payload["passport_status"] == "validated"
    assert event.payload["capability_status"] in {"inactive", "not_evaluated"}

    # Then: an Evidence Card surfaces the registration from the audit source.
    card = evidence_card_from_audit_event(event)
    assert card.card_type == CARD_TYPE_BODY_MODULE_ATTACH_REGISTERED
    assert card.subject_type == "module"
    assert card.subject_id == "test_sensor_module_001"
    assert card.subject_status == "attached"
    assert card.source_type == "audit_event"
    assert card.trust_status == "audit_backed"
    # a fully audit-backed registration must report §17 evidence status "implemented",
    # not "missing" — guards the mount_point/attempted_mount payload-key contract.
    assert card.status == "implemented"
    assert card.read_only is True
    assert card.runtime_ready is False

    # Then: the card does NOT claim capabilities are active.
    text = card.operator_summary.lower()
    for banned in (
        "capabilities active",
        "module active",
        "module powered",
        "mission-ready",
        "module verified",
        "runtime conforms",
        "qiki body implemented",
    ):
        assert banned not in text


def test_valid_passport_attach_does_not_activate_capabilities() -> None:
    """Boundary: a passport may DECLARE capabilities; registration must not ACTIVATE them.

    Guards Slice 0003 against drifting into module economy / command unlocks / PDU.
    """
    body = BodyConfigSnapshot.skeleton()
    store = EventStore(backend="memory")
    passport = ModulePassport(
        module_id="test_sensor_module_001",
        module_class="sensor",
        mount_point="F06",
        provided_capabilities=("sensor_read", "sensor_stream"),
    )
    request = ModuleAttachRequest(
        request_id="req-1",
        module_id="test_sensor_module_001",
        mount_point="F06",
        passport=passport,
    )

    result, updated = register_module(
        body, request, audit_sink=EventStoreRegistrationSink(store)
    )

    # Registration still succeeds...
    assert result.status == "attached"
    # ...but the DECLARED capabilities are NOT activated.
    assert result.capability_status in {"inactive", "not_evaluated"}
    entry = next(m for m in updated.modules if m["module_id"] == "test_sensor_module_001")
    assert entry["capability_status"] in {"inactive", "not_evaluated"}

    # No command-unlock / PDU / thermal / activation surface leaked into the audit.
    event = store.recent(1)[0]
    for forbidden_key in (
        "command_unlocks",
        "commands_unlocked",
        "pdu_load_enabled",
        "pdu_enabled",
        "thermal_cleared",
        "capabilities_active",
        "active_capabilities",
    ):
        assert forbidden_key not in event.payload

    # The result object exposes no activation surface either.
    assert not hasattr(result, "command_unlocks")
    assert not hasattr(result, "active_capabilities")

    # The evidence card does not claim any activation.
    card = evidence_card_from_audit_event(event)
    assert card.runtime_ready is False
    text = card.operator_summary.lower()
    for banned in (
        "capabilities active",
        "module active",
        "module powered",
        "command unlocked",
        "pdu enabled",
        "thermally cleared",
    ):
        assert banned not in text
