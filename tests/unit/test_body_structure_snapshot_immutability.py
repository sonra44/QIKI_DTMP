"""REMEDIATION Phase 1 — C2: BodyConfigSnapshot must be a true immutable value object.

Audit finding C2: BodyConfigSnapshot is frozen, but `frozen=True` only blocks attribute
reassignment, not in-place mutation of nested mutable contents. On a successful
registration the derived snapshot shares (by reference) the parent's face_mount_classes
nested dicts and the pre-existing module entry dicts. Mutating the derived snapshot then
silently corrupts the parent.

These tests prove the aliasing (RED on current code) and lock the fix: nested
face_mount_classes rule dicts, pre-existing module entry dicts, and the new entry are all
copied so parent and child snapshots never share mutable state.
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


def _register(body, module_id, mount_point):
    store = EventStore(backend="memory")
    passport = ModulePassport(module_id, "sensor", mount_point)
    request = ModuleAttachRequest("r", module_id, mount_point, passport=passport)
    _, updated = register_module(body, request, audit_sink=EventStoreRegistrationSink(store))
    return updated


def test_body_config_snapshot_does_not_alias_nested_mount_classes() -> None:
    body = BodyConfigSnapshot.skeleton()
    original_allowed = body.face_mount_classes["F06"]["allowed"]

    updated = _register(body, "mod-x", "F06")

    # tamper the derived snapshot's nested mount-class rule.
    updated.face_mount_classes["F06"]["allowed"] = ("TAMPERED",)

    # the parent body must be unaffected (no shared nested dict).
    assert body.face_mount_classes["F06"]["allowed"] == original_allowed
    assert body.face_mount_classes["F06"]["allowed"] != ("TAMPERED",)


def test_body_config_snapshot_does_not_alias_existing_module_dicts() -> None:
    body = BodyConfigSnapshot.skeleton()
    body1 = _register(body, "mod-1", "F06")
    body2 = _register(body1, "mod-2", "F07")

    # tamper the pre-existing module entry via the newer snapshot.
    entry_in_body2 = next(m for m in body2.modules if m["module_id"] == "mod-1")
    entry_in_body2["status"] = "TAMPERED"

    # the earlier snapshot's entry must be unaffected (no shared entry dict).
    entry_in_body1 = next(m for m in body1.modules if m["module_id"] == "mod-1")
    assert entry_in_body1["status"] == "attached"
    assert entry_in_body1["status"] != "TAMPERED"
