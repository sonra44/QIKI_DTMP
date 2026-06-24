"""RUNTIME_SLICE_0001 — Body Structure Evidence Seed (runtime/policy layer).

Minimal, honest body-structure contour that owns ONE negative causal loop:

    module attach request without a passport
      -> rejected (this layer owns the decision)
      -> reason_code MODULE_PASSPORT_MISSING
      -> audit event recorded via an injected sink (real EventStore in production)

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

from qiki.services.q_core_agent.core.evidence_card_id import make_evidence_card_id

# Domain reason codes (stable). Owned by the runtime/policy layer, not ORION.
MODULE_PASSPORT_MISSING = "MODULE_PASSPORT_MISSING"
# Slice 0004: a mount point already holding a module rejects a second attach.
MOUNT_POINT_OCCUPIED = "MOUNT_POINT_OCCUPIED"
# Slice 0005: a valid passport on a free mount is still rejected if the module class
# is forbidden for that face by the Face Map mount rules.
MODULE_MOUNT_CLASS_FORBIDDEN = "MODULE_MOUNT_CLASS_FORBIDDEN"
# Slice 0006: a passport that is present but structurally invalid (e.g. its module_id
# does not match the attach request) is rejected before any mount validation.
MODULE_PASSPORT_INVALID = "MODULE_PASSPORT_INVALID"
# Slice 0007: a valid passport pointing at a mount point the body does not know is
# rejected before occupancy/class — the unknown mount is never auto-created.
MOUNT_POINT_UNKNOWN = "MOUNT_POINT_UNKNOWN"
# Honest owner of passport-integrity decisions (still runtime/policy, not ORION).
PASSPORT_VALIDATOR_OWNER = "q_core_agent.core.body_structure.passport_validator"

# Face Map mount-class rules — runtime SKELETON / TEST FIXTURE only, NOT canon.
# (Which classes a face accepts is a target-canon decision; this is a placeholder so
# the compatibility guard has something to enforce.)
_FIXTURE_ALLOWED_MOUNT_CLASSES: tuple[str, ...] = ("sensor", "antenna", "science")
_FIXTURE_FORBIDDEN_MOUNT_CLASSES: tuple[str, ...] = ("reactor-class", "heavy-power", "rcs-cluster")

# Honest source owner of the rejection (runtime/policy, not the operator console).
SOURCE_OWNER = "q_core_agent.core.body_structure.attach_policy"

# Face Map skeleton F00..F11 (structural placeholder only; status: skeleton).
FACE_IDS: tuple[str, ...] = tuple(f"F{i:02d}" for i in range(12))

# Slice 0003 registration status vocabulary (stable). Declaration != activation:
# a registered module is occupancy/registry state only, never capability-active.
PASSPORT_STATUS_VALIDATED = "validated"
MODULE_STATUS_ATTACHED = "attached"
CAPABILITY_STATUS_INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class BodyConfigSnapshot:
    """Minimal body-structure snapshot, honestly marked as a skeleton.

    No geometry, normals, adjacency, thrust/torque or verified face positions are
    claimed. Bayonet states represent interface state only.
    """

    face_ids: tuple[str, ...]
    face_map_status: str  # "skeleton" — not calculated
    bayonet_states: dict[str, str]  # represented interface state, not "hard lock works"
    face_occupancy: dict[str, str]  # face_id -> module_id, or "free"
    modules: tuple[dict[str, Any], ...]  # registered module entries (registry/occupancy only)
    # face_id -> {"allowed": (...), "forbidden": (...)}; SKELETON/FIXTURE, not canon.
    face_mount_classes: dict[str, dict[str, tuple[str, ...]]]

    @classmethod
    def skeleton(cls) -> "BodyConfigSnapshot":
        return cls(
            face_ids=FACE_IDS,
            face_map_status="skeleton",
            bayonet_states={"bayonet_A": "unknown", "bayonet_B": "unknown"},
            face_occupancy={face_id: "free" for face_id in FACE_IDS},
            modules=(),
            face_mount_classes={
                face_id: {
                    "allowed": _FIXTURE_ALLOWED_MOUNT_CLASSES,
                    "forbidden": _FIXTURE_FORBIDDEN_MOUNT_CLASSES,
                }
                for face_id in FACE_IDS
            },
        )


@dataclass(frozen=True, slots=True)
class ModulePassport:
    """Minimal module passport shape contract (template-only).

    Slice 0001 only needs to tell "passport present with required shape" vs "missing".
    """

    module_id: str
    module_class: str
    mount_point: str
    # Declared capabilities (template-only). Declaration is NOT activation: slice 0003
    # registration never activates these — capability_status stays inactive.
    provided_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ModuleAttachRequest:
    request_id: str
    module_id: str
    mount_point: str
    passport: ModulePassport | None = None


@dataclass(frozen=True, slots=True)
class RejectionAuditEvent:
    """Audit record for an attach rejection (slice-local; mapped to the shared
    event store via EventStoreRejectionSink — no second audit format invented)."""

    reason_code: str
    request_id: str
    module_id: str
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
    module_id: str
    attempted_mount: str
    source_owner: str


def _passport_has_required_shape(passport: ModulePassport | None) -> bool:
    if passport is None:
        return False
    # "present" means required fields are non-empty AFTER trimming (whitespace == missing).
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
        return self._store.append_new(
            subsystem=event.source_owner,
            event_type="module_attach_rejected",
            payload={
                "request_id": event.request_id,
                "module_id": event.module_id,
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
            module_id=request.module_id,
            attempted_mount=request.mount_point,
            source_owner=SOURCE_OWNER,
            timestamp=time.time(),
        )
        audit_event_id = audit_sink.append_rejection(event)
        return AttachResult(
            rejected=True,
            reason_code=MODULE_PASSPORT_MISSING,
            runtime_ready=False,
            request_id=request.request_id,
            module_id=request.module_id,
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
        module_id=request.module_id,
        attempted_mount=request.mount_point,
        source_owner=SOURCE_OWNER,
    )


# --- RUNTIME_SLICE_0003: valid-passport registration (positive path) ---------------
#
# Registration is occupancy / registry state ONLY. It never activates a capability,
# never makes the module runtime-ready, and never implies power / thermal / command
# readiness. The negative path (attach_module above) is unchanged.


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    status: str  # "attached" on success, "rejected" on occupancy conflict
    module_id: str
    mount_point: str
    passport_status: str  # "validated"
    body_config_updated: bool
    runtime_ready: bool  # always False in slice 0003/0004
    capability_status: str  # "inactive" — capabilities are NOT activated here
    reason_code: str | None
    # Slice 0004 occupancy conflict context (empty for the happy registration path).
    requested_module_id: str = ""
    existing_module_id: str = ""
    # Slice 0006 passport-integrity context (empty unless passport was invalid).
    validation_error: str = ""
    passport_module_id: str = ""
    # Slice 0007 mount-existence context (False only when the mount was unknown).
    known_mount: bool = True
    # Remediation H3: id of the audit event this decision recorded (causal identity).
    audit_event_id: str = ""


class RegistrationAuditSink(Protocol):
    def append_registration(
        self,
        *,
        module_id: str,
        mount_point: str,
        passport_status: str,
        capability_status: str,
        runtime_ready: bool,
        timestamp: float,
    ) -> str: ...

    def append_occupied_rejection(
        self,
        *,
        request_id: str,
        requested_module_id: str,
        existing_module_id: str,
        mount_point: str,
        timestamp: float,
    ) -> str: ...

    def append_class_forbidden_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        module_class: str,
        mount_point: str,
        timestamp: float,
    ) -> str: ...

    def append_invalid_passport_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        passport_module_id: str,
        mount_point: str,
        validation_error: str,
        timestamp: float,
    ) -> str: ...

    def append_unknown_mount_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        mount_point: str,
        timestamp: float,
    ) -> str: ...

    def append_missing_passport_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        mount_point: str,
        timestamp: float,
    ) -> str: ...


class EventStoreRegistrationSink:
    """Adapter: records a successful registration into the shared EventStore as a
    SystemEvent (event_type=module_attach_registered). Reuses the existing audit
    layer — no second audit format."""

    def __init__(self, event_store: Any) -> None:
        self._store = event_store

    def append_registration(
        self,
        *,
        module_id: str,
        mount_point: str,
        passport_status: str,
        capability_status: str,
        runtime_ready: bool,
        timestamp: float,
    ) -> None:
        return self._store.append_new(
            subsystem=SOURCE_OWNER,
            event_type="module_attach_registered",
            payload={
                "module_id": module_id,
                "mount_point": mount_point,
                "passport_status": passport_status,
                "capability_status": capability_status,
                "runtime_ready": runtime_ready,
                "body_config_updated": True,
                "source_owner": SOURCE_OWNER,
            },
            reason="",
            ts=timestamp,
        ).event_id

    def append_occupied_rejection(
        self,
        *,
        request_id: str,
        requested_module_id: str,
        existing_module_id: str,
        mount_point: str,
        timestamp: float,
    ) -> None:
        return self._store.append_new(
            subsystem=SOURCE_OWNER,
            event_type="module_attach_rejected",
            payload={
                # mapping-compat fields (let the existing rejection mapping classify it)
                "module_id": requested_module_id,
                "attempted_mount": mount_point,
                "reason_code": MOUNT_POINT_OCCUPIED,
                # originating request link (keeps card.related_command_id intact)
                "request_id": request_id,
                # domain facts for the occupancy conflict
                "requested_module_id": requested_module_id,
                "existing_module_id": existing_module_id,
                "mount_point": mount_point,
                "body_config_updated": False,
                "source_owner": SOURCE_OWNER,
            },
            reason=MOUNT_POINT_OCCUPIED,
            ts=timestamp,
        ).event_id

    def append_class_forbidden_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        module_class: str,
        mount_point: str,
        timestamp: float,
    ) -> None:
        return self._store.append_new(
            subsystem=SOURCE_OWNER,
            event_type="module_attach_rejected",
            payload={
                # mapping-compat fields (let the existing rejection mapping classify it)
                "module_id": module_id,
                "attempted_mount": mount_point,
                "reason_code": MODULE_MOUNT_CLASS_FORBIDDEN,
                "request_id": request_id,
                # domain facts for the forbidden-class conflict
                "module_class": module_class,
                "mount_point": mount_point,
                "body_config_updated": False,
                "source_owner": SOURCE_OWNER,
            },
            reason=MODULE_MOUNT_CLASS_FORBIDDEN,
            ts=timestamp,
        ).event_id

    def append_invalid_passport_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        passport_module_id: str,
        mount_point: str,
        validation_error: str,
        timestamp: float,
    ) -> None:
        return self._store.append_new(
            subsystem=PASSPORT_VALIDATOR_OWNER,
            event_type="module_attach_rejected",
            payload={
                # mapping-compat fields (let the existing rejection mapping classify it)
                "module_id": module_id,
                "attempted_mount": mount_point,
                "reason_code": MODULE_PASSPORT_INVALID,
                "request_id": request_id,
                # domain facts for the invalid-passport conflict
                "passport_module_id": passport_module_id,
                "mount_point": mount_point,
                "validation_error": validation_error,
                "body_config_updated": False,
                "source_owner": PASSPORT_VALIDATOR_OWNER,
            },
            reason=MODULE_PASSPORT_INVALID,
            ts=timestamp,
        ).event_id

    def append_unknown_mount_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        mount_point: str,
        timestamp: float,
    ) -> None:
        return self._store.append_new(
            subsystem=SOURCE_OWNER,
            event_type="module_attach_rejected",
            payload={
                # mapping-compat fields (let the existing rejection mapping classify it)
                "module_id": module_id,
                "attempted_mount": mount_point,
                "reason_code": MOUNT_POINT_UNKNOWN,
                "request_id": request_id,
                # domain facts for the unknown-mount conflict
                "mount_point": mount_point,
                "known_mount": False,
                "body_config_updated": False,
                "source_owner": SOURCE_OWNER,
            },
            reason=MOUNT_POINT_UNKNOWN,
            ts=timestamp,
        ).event_id

    def append_missing_passport_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        mount_point: str,
        timestamp: float,
    ) -> None:
        return self._store.append_new(
            subsystem=SOURCE_OWNER,
            event_type="module_attach_rejected",
            payload={
                "module_id": module_id,
                "attempted_mount": mount_point,
                "reason_code": MODULE_PASSPORT_MISSING,
                "request_id": request_id,
                "mount_point": mount_point,
                "body_config_updated": False,
                "source_owner": SOURCE_OWNER,
            },
            reason=MODULE_PASSPORT_MISSING,
            ts=timestamp,
        ).event_id


def register_module(
    body: BodyConfigSnapshot,
    request: ModuleAttachRequest,
    *,
    audit_sink: RegistrationAuditSink,
) -> tuple[RegistrationResult, BodyConfigSnapshot]:
    """Register a module that carries a valid minimal passport.

    On a valid passport the module is registered in a NEW body_config snapshot
    (mount point occupied, module entry added), an audit event is recorded, and an
    "attached" result is returned. Capabilities stay inactive; the module is NOT
    runtime-ready. An invalid/missing passport is not registered (no body change).
    """
    if not _passport_has_required_shape(request.passport):
        audit_event_id = audit_sink.append_missing_passport_rejection(
            request_id=request.request_id,
            module_id=request.module_id,
            mount_point=request.mount_point,
            timestamp=time.time(),
        )
        return (
            RegistrationResult(
                status="rejected",
                audit_event_id=audit_event_id,
                module_id=request.module_id,
                mount_point=request.mount_point,
                passport_status="missing",
                body_config_updated=False,
                runtime_ready=False,
                capability_status="not_evaluated",
                reason_code=MODULE_PASSPORT_MISSING,
            ),
            body,
        )

    # Passport integrity guard (slice 0006 + remediation C1): a present, well-shaped
    # passport must be consistent with the attach request — BOTH module_id AND mount_point
    # must match. Any mismatch is rejected BEFORE mount validation, so an invalid passport
    # never reaches the body. (module_id mismatch takes precedence over mount_point.)
    if request.passport is not None:
        if request.passport.module_id.strip() != request.module_id.strip():
            validation_error = "module_id_mismatch"
        elif request.passport.mount_point.strip() != request.mount_point.strip():
            validation_error = "mount_point_mismatch"
        else:
            validation_error = ""
    else:
        validation_error = ""
    if request.passport is not None and validation_error:
        audit_event_id = audit_sink.append_invalid_passport_rejection(
            request_id=request.request_id,
            module_id=request.module_id,
            passport_module_id=request.passport.module_id,
            mount_point=request.mount_point,
            validation_error=validation_error,
            timestamp=time.time(),
        )
        return (
            RegistrationResult(
                status="rejected",
                audit_event_id=audit_event_id,
                module_id=request.module_id,
                mount_point=request.mount_point,
                passport_status="invalid",
                body_config_updated=False,
                runtime_ready=False,
                capability_status="not_evaluated",
                reason_code=MODULE_PASSPORT_INVALID,
                requested_module_id=request.module_id,
                validation_error=validation_error,
                passport_module_id=request.passport.module_id,
            ),
            body,
        )

    # Mount existence guard (slice 0007): a valid passport cannot attach to a mount point
    # the body does not know. Rejected before occupancy/class; the unknown mount is never
    # auto-created.
    if request.mount_point not in body.face_occupancy:
        audit_event_id = audit_sink.append_unknown_mount_rejection(
            request_id=request.request_id,
            module_id=request.module_id,
            mount_point=request.mount_point,
            timestamp=time.time(),
        )
        return (
            RegistrationResult(
                status="rejected",
                audit_event_id=audit_event_id,
                module_id=request.module_id,
                mount_point=request.mount_point,
                passport_status=PASSPORT_STATUS_VALIDATED,
                body_config_updated=False,
                runtime_ready=False,
                capability_status="not_evaluated",
                reason_code=MOUNT_POINT_UNKNOWN,
                requested_module_id=request.module_id,
                known_mount=False,
            ),
            body,
        )

    # Occupancy guard (slice 0004): a mount point already holding a module rejects a
    # second attach. Checked AFTER passport validity, BEFORE any body_config mutation,
    # so the existing module is never silently overwritten.
    occupant = body.face_occupancy.get(request.mount_point, "free")
    if occupant not in ("", "free"):
        audit_event_id = audit_sink.append_occupied_rejection(
            request_id=request.request_id,
            requested_module_id=request.module_id,
            existing_module_id=occupant,
            mount_point=request.mount_point,
            timestamp=time.time(),
        )
        return (
            RegistrationResult(
                status="rejected",
                audit_event_id=audit_event_id,
                module_id=request.module_id,
                mount_point=request.mount_point,
                passport_status=PASSPORT_STATUS_VALIDATED,  # the passport itself was valid
                body_config_updated=False,
                runtime_ready=False,
                capability_status="not_evaluated",
                reason_code=MOUNT_POINT_OCCUPIED,
                requested_module_id=request.module_id,
                existing_module_id=occupant,
            ),
            body,
        )

    # Mount-class compatibility guard (slice 0005): a free, known mount still rejects a
    # module whose class is forbidden for that face by the Face Map rules. Checked after
    # occupancy (occupied mount keeps priority), before any body_config mutation.
    rules = body.face_mount_classes.get(request.mount_point, {})
    module_class = (request.passport.module_class if request.passport else "").strip()
    forbidden_classes = tuple(rules.get("forbidden", ()))
    allowed_classes = tuple(rules.get("allowed", ()))
    if module_class in forbidden_classes or (allowed_classes and module_class not in allowed_classes):
        audit_event_id = audit_sink.append_class_forbidden_rejection(
            request_id=request.request_id,
            module_id=request.module_id,
            module_class=module_class,
            mount_point=request.mount_point,
            timestamp=time.time(),
        )
        return (
            RegistrationResult(
                status="rejected",
                audit_event_id=audit_event_id,
                module_id=request.module_id,
                mount_point=request.mount_point,
                passport_status=PASSPORT_STATUS_VALIDATED,
                body_config_updated=False,
                runtime_ready=False,
                capability_status="not_evaluated",
                reason_code=MODULE_MOUNT_CLASS_FORBIDDEN,
                requested_module_id=request.module_id,
                existing_module_id="",
            ),
            body,
        )

    passport_status = PASSPORT_STATUS_VALIDATED
    capability_status = CAPABILITY_STATUS_INACTIVE  # registration does NOT activate capabilities
    entry: dict[str, Any] = {
        "module_id": request.module_id,
        "mount_point": request.mount_point,
        "status": MODULE_STATUS_ATTACHED,
        "passport_status": passport_status,
        "capability_status": capability_status,
    }
    new_occupancy = dict(body.face_occupancy)
    new_occupancy[request.mount_point] = request.module_id
    # Build a fully de-aliased snapshot (remediation C2): a frozen dataclass does not
    # prevent in-place mutation of nested mutable contents, so every nested structure is
    # copied — pre-existing module entry dicts, the new entry, and each face's mount-class
    # rule dict — so parent and child snapshots never share mutable state.
    updated = BodyConfigSnapshot(
        face_ids=body.face_ids,
        face_map_status=body.face_map_status,
        bayonet_states=dict(body.bayonet_states),
        face_occupancy=new_occupancy,
        modules=tuple(dict(m) for m in body.modules) + (dict(entry),),
        face_mount_classes={k: dict(v) for k, v in body.face_mount_classes.items()},
    )
    audit_event_id = audit_sink.append_registration(
        module_id=request.module_id,
        mount_point=request.mount_point,
        passport_status=passport_status,
        capability_status=capability_status,
        runtime_ready=False,
        timestamp=time.time(),
    )
    return (
        RegistrationResult(
            status=MODULE_STATUS_ATTACHED,
            audit_event_id=audit_event_id,
            module_id=request.module_id,
            mount_point=request.mount_point,
            passport_status=passport_status,
            body_config_updated=True,
            runtime_ready=False,
            capability_status=capability_status,
            reason_code=None,
        ),
        updated,
    )


# --- RUNTIME_SLICE_0008: module attach validation pipeline v1 (orchestrator) ---------
#
# One ordered entrypoint over the slice 0001-0007 guards. It does NOT re-implement the
# checks: it runs register_module (already ordered) and packages the outcome into a
# single deterministic AttachDecision with the deciding stage, the audit event id and an
# ORION evidence-card id. It never mutates body_config itself and never owns truth — the
# decision/audit are runtime-owned; the evidence card stays an ORION projection.

# reason_code -> deciding pipeline stage. A None reason means successful registration.
_STAGE_BY_REASON: dict[str, str] = {
    MODULE_PASSPORT_MISSING: "passport_presence",
    MODULE_PASSPORT_INVALID: "passport_integrity",
    MOUNT_POINT_UNKNOWN: "mount_existence",
    MOUNT_POINT_OCCUPIED: "mount_occupancy",
    MODULE_MOUNT_CLASS_FORBIDDEN: "mount_compatibility",
}


@dataclass(frozen=True, slots=True)
class AttachDecision:
    status: str  # "attached" | "rejected"
    stage: str  # the validation stage that produced the decision
    reason_code: str | None  # set only for rejection
    module_id: str
    mount_point: str
    body_config_updated: bool
    runtime_ready: bool  # always False in this slice
    passport_status: str
    capability_status: str
    audit_event_id: str  # required: every outcome is audit-backed
    evidence_card_id: str  # deterministic ORION card id for audit_event_id (card:<id>)


def run_attach_pipeline(
    body: BodyConfigSnapshot,
    request: ModuleAttachRequest,
    *,
    store: Any,
) -> tuple[AttachDecision, BodyConfigSnapshot]:
    """Run the ordered attach validation pipeline and package one AttachDecision.

    Delegates to register_module (the ordered guard chain), then reads the audit event
    it recorded to build the decision. body_config is mutated only on success (inside
    register_module); a rejection returns the original body unchanged.
    """
    sink = EventStoreRegistrationSink(store)
    result, updated = register_module(body, request, audit_sink=sink)

    stage = "registration" if result.reason_code is None else _STAGE_BY_REASON[result.reason_code]
    # Remediation H3: causal identity comes from the event id the audit write RETURNED
    # (threaded through RegistrationResult), never from positional store.recent(1).
    audit_event_id = result.audit_event_id
    status = MODULE_STATUS_ATTACHED if result.status == MODULE_STATUS_ATTACHED else "rejected"

    return (
        AttachDecision(
            status=status,
            stage=stage,
            reason_code=result.reason_code,
            module_id=result.module_id,
            mount_point=result.mount_point,
            body_config_updated=result.body_config_updated,
            runtime_ready=result.runtime_ready,
            passport_status=result.passport_status,
            capability_status=result.capability_status,
            audit_event_id=audit_event_id,
            # ORION evidence-card id convention (EvidenceCard.card_id == make_evidence_card_id(event_id)).
            # Shared id contract only — the card itself stays an ORION projection.
            evidence_card_id=make_evidence_card_id(audit_event_id),
        ),
        updated,
    )
