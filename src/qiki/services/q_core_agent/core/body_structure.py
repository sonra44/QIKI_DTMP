"""RUNTIME_SLICE_0001 — Body Structure Evidence Seed (runtime/policy layer).

Minimal, honest body-structure contour that owns ONE negative causal loop:

    module attach request without a passport
      -> rejected (this layer owns the decision)
      -> reason_code MODULE_PASSPORT_MISSING
      -> audit event recorded via an injected sink

Discipline (QIKI Body v0.2.2, target canon; Canon != implemented):
- Face Map is a *skeleton* (F00-F11) with no geometry / normals / adjacency claimed.
- Bayonet state is *represented*, not "hard lock works".
- Module Passport is a minimal shape contract; the valid-attach happy path is out
  of scope for slice 0001 and is NOT claimed implemented.
- A module never becomes runtime-ready in this slice.
- ORION does not validate the passport; it only displays what this layer decided.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

# Domain reason code (stable). Owned by the runtime/policy layer, not ORION.
MODULE_PASSPORT_MISSING = "MODULE_PASSPORT_MISSING"

# Honest source owner of the rejection (runtime/policy, not the operator console).
SOURCE_OWNER = "q_core_agent.core.body_structure.attach_policy"

# Face Map skeleton F00..F11 (structural placeholder only; status: skeleton).
FACE_IDS: tuple[str, ...] = tuple(f"F{i:02d}" for i in range(12))


@dataclass(frozen=True, slots=True)
class BodyConfigSnapshot:
    """Minimal body-structure snapshot, honestly marked as a skeleton.

    No geometry, normals, adjacency, thrust/torque or verified face positions are
    claimed. Bayonet states represent interface state only.
    """

    face_ids: tuple[str, ...]
    face_map_status: str  # "skeleton" — not calculated
    bayonet_states: dict[str, str]  # represented interface state, not "hard lock works"

    @classmethod
    def skeleton(cls) -> "BodyConfigSnapshot":
        return cls(
            face_ids=FACE_IDS,
            face_map_status="skeleton",
            bayonet_states={"bayonet_A": "unknown", "bayonet_B": "unknown"},
        )


@dataclass(frozen=True, slots=True)
class ModulePassport:
    """Minimal module passport shape contract (template-only).

    Slice 0001 only needs to tell "passport present with required shape" vs "missing".
    """

    module_id: str
    module_class: str
    mount_point: str


@dataclass(frozen=True, slots=True)
class ModuleAttachRequest:
    request_id: str
    module_id: str
    mount_point: str
    passport: ModulePassport | None = None


@dataclass(frozen=True, slots=True)
class RejectionAuditEvent:
    """Audit record for an attach rejection (slice-local; mapped to the shared
    event store via a thin adapter when wired — no second audit format invented)."""

    reason_code: str
    request_id: str
    attempted_mount: str
    source_owner: str
    timestamp: float


class RejectionAuditSink(Protocol):
    def append_rejection(self, event: RejectionAuditEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class AttachResult:
    rejected: bool
    reason_code: str
    runtime_ready: bool
    request_id: str
    attempted_mount: str
    source_owner: str


def _passport_has_required_shape(passport: ModulePassport | None) -> bool:
    if passport is None:
        return False
    return bool(
        passport.module_id.strip()
        and passport.module_class.strip()
        and passport.mount_point.strip()
    )


class EventStoreRejectionSink:
    """Adapter: records a rejection into the shared EventStore as a SystemEvent.

    Reuses the existing project audit layer (``event_store.SystemEvent`` via
    ``EventStore.append_new``) — it does NOT invent a second audit format.
    """

    def __init__(self, event_store: Any) -> None:
        self._store = event_store

    def append_rejection(self, event: "RejectionAuditEvent") -> None:
        self._store.append_new(
            subsystem=event.source_owner,
            event_type="module_attach_rejected",
            payload={
                "request_id": event.request_id,
                "attempted_mount": event.attempted_mount,
                "reason_code": event.reason_code,
                "source_owner": event.source_owner,
            },
            reason=event.reason_code,
            ts=event.timestamp,
        )


def attach_module(
    body: BodyConfigSnapshot,
    request: ModuleAttachRequest,
    *,
    audit_sink: RejectionAuditSink,
) -> AttachResult:
    """Validate a module attach request (runtime/policy owner of the decision).

    Slice 0001 implements only the negative path: a missing or shape-invalid
    passport is rejected with MODULE_PASSPORT_MISSING and recorded to ``audit_sink``.
    No module becomes runtime-ready here.
    """
    if not _passport_has_required_shape(request.passport):
        event = RejectionAuditEvent(
            reason_code=MODULE_PASSPORT_MISSING,
            request_id=request.request_id,
            attempted_mount=request.mount_point,
            source_owner=SOURCE_OWNER,
            timestamp=time.time(),
        )
        audit_sink.append_rejection(event)
        return AttachResult(
            rejected=True,
            reason_code=MODULE_PASSPORT_MISSING,
            runtime_ready=False,
            request_id=request.request_id,
            attempted_mount=request.mount_point,
            source_owner=SOURCE_OWNER,
        )

    # Valid-attach (happy path) is out of scope for slice 0001 and is NOT claimed
    # implemented. Until built with evidence, a shaped passport still does not make
    # a module runtime-ready (no overclaim).
    return AttachResult(
        rejected=True,
        reason_code="MODULE_ATTACH_NOT_IMPLEMENTED",
        runtime_ready=False,
        request_id=request.request_id,
        attempted_mount=request.mount_point,
        source_owner=SOURCE_OWNER,
    )
