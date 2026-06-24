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

_AUDIT_STATE_ATTACH_REQUESTED = "attach_requested"
_AUDIT_STATE_ATTACH_REJECTED = "attach_rejected"
_AUDIT_STATE_MODULE_REGISTERED = "module_registered"
_AUDIT_EFFECT_NOT_APPLIED = "not_applied"
_AUDIT_EFFECT_REGISTRY_UPDATED = "registry_updated"
_AUDIT_SEVERITY_WARNING = "warning"
_AUDIT_SEVERITY_INFO = "info"


def _if_audit_aliases(
    *,
    source: str,
    command_id: str,
    reason_code: str | None,
    previous_state: str,
    new_state: str,
    effect_state: str,
    severity: str,
    blackbox_relevance: bool = False,
) -> dict[str, Any]:
    """IF-AUDIT aliases derived from the local attach audit event only.

    These are audit-level transition labels, not full runtime/world-state
    snapshots and not effect confirmation.
    """
    return {
        "source": source,
        "command_id": command_id,
        "previous_state": previous_state,
        "new_state": new_state,
        "reason_codes": [reason_code] if reason_code else [],
        "effect_state": effect_state,
        "severity": severity,
        "blackbox_relevance": bool(blackbox_relevance),
    }


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
                **_if_audit_aliases(
                    source=event.source_owner,
                    command_id=event.request_id,
                    reason_code=event.reason_code,
                    previous_state=_AUDIT_STATE_ATTACH_REQUESTED,
                    new_state=_AUDIT_STATE_ATTACH_REJECTED,
                    effect_state=_AUDIT_EFFECT_NOT_APPLIED,
                    severity=_AUDIT_SEVERITY_WARNING,
                ),
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


@dataclass(frozen=True, slots=True)
class _RegistrationGuard:
    reason_code: str
    stage: str


@dataclass(frozen=True, slots=True)
class _RegistrationRejection:
    reason_code: str
    passport_status: str
    audit_method: str
    audit_payload: dict[str, Any]
    result_context: dict[str, Any]


_REGISTRATION_GUARDS: tuple[_RegistrationGuard, ...] = (
    _RegistrationGuard(MODULE_PASSPORT_MISSING, "passport_presence"),
    _RegistrationGuard(MODULE_PASSPORT_INVALID, "passport_integrity"),
    _RegistrationGuard(MOUNT_POINT_UNKNOWN, "mount_existence"),
    _RegistrationGuard(MOUNT_POINT_OCCUPIED, "mount_occupancy"),
    _RegistrationGuard(MODULE_MOUNT_CLASS_FORBIDDEN, "mount_compatibility"),
)

_STAGE_BY_REASON: dict[str, str] = {
    guard.reason_code: guard.stage for guard in _REGISTRATION_GUARDS
}


class RegistrationAuditSink(Protocol):
    def append_registration(
        self,
        *,
        request_id: str,
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
        request_id: str,
        module_id: str,
        mount_point: str,
        passport_status: str,
        capability_status: str,
        runtime_ready: bool,
        timestamp: float,
    ) -> str:
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
                **_if_audit_aliases(
                    source=SOURCE_OWNER,
                    command_id=request_id,
                    reason_code=None,
                    previous_state=_AUDIT_STATE_ATTACH_REQUESTED,
                    new_state=_AUDIT_STATE_MODULE_REGISTERED,
                    effect_state=_AUDIT_EFFECT_REGISTRY_UPDATED,
                    severity=_AUDIT_SEVERITY_INFO,
                ),
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
    ) -> str:
        return self._append_rejection(
            request_id=request_id,
            module_id=requested_module_id,
            mount_point=mount_point,
            reason_code=MOUNT_POINT_OCCUPIED,
            source_owner=SOURCE_OWNER,
            timestamp=timestamp,
            extra_payload={
                "requested_module_id": requested_module_id,
                "existing_module_id": existing_module_id,
            },
        )

    def append_class_forbidden_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        module_class: str,
        mount_point: str,
        timestamp: float,
    ) -> str:
        return self._append_rejection(
            request_id=request_id,
            module_id=module_id,
            mount_point=mount_point,
            reason_code=MODULE_MOUNT_CLASS_FORBIDDEN,
            source_owner=SOURCE_OWNER,
            timestamp=timestamp,
            extra_payload={"module_class": module_class},
        )

    def append_invalid_passport_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        passport_module_id: str,
        mount_point: str,
        validation_error: str,
        timestamp: float,
    ) -> str:
        return self._append_rejection(
            request_id=request_id,
            module_id=module_id,
            mount_point=mount_point,
            reason_code=MODULE_PASSPORT_INVALID,
            source_owner=PASSPORT_VALIDATOR_OWNER,
            timestamp=timestamp,
            extra_payload={
                "passport_module_id": passport_module_id,
                "validation_error": validation_error,
            },
        )

    def append_unknown_mount_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        mount_point: str,
        timestamp: float,
    ) -> str:
        return self._append_rejection(
            request_id=request_id,
            module_id=module_id,
            mount_point=mount_point,
            reason_code=MOUNT_POINT_UNKNOWN,
            source_owner=SOURCE_OWNER,
            timestamp=timestamp,
            extra_payload={"known_mount": False},
        )

    def append_missing_passport_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        mount_point: str,
        timestamp: float,
    ) -> str:
        return self._append_rejection(
            request_id=request_id,
            module_id=module_id,
            mount_point=mount_point,
            reason_code=MODULE_PASSPORT_MISSING,
            source_owner=SOURCE_OWNER,
            timestamp=timestamp,
        )

    def _append_rejection(
        self,
        *,
        request_id: str,
        module_id: str,
        mount_point: str,
        reason_code: str,
        source_owner: str,
        timestamp: float,
        extra_payload: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "module_id": module_id,
            "attempted_mount": mount_point,
            "reason_code": reason_code,
            "request_id": request_id,
            "mount_point": mount_point,
            "body_config_updated": False,
            "source_owner": source_owner,
            **(extra_payload or {}),
            **_if_audit_aliases(
                source=source_owner,
                command_id=request_id,
                reason_code=reason_code,
                previous_state=_AUDIT_STATE_ATTACH_REQUESTED,
                new_state=_AUDIT_STATE_ATTACH_REJECTED,
                effect_state=_AUDIT_EFFECT_NOT_APPLIED,
                severity=_AUDIT_SEVERITY_WARNING,
            ),
        }
        return self._store.append_new(
            subsystem=source_owner,
            event_type="module_attach_rejected",
            payload=payload,
            reason=reason_code,
            ts=timestamp,
        ).event_id


def _passport_validation_error(request: ModuleAttachRequest) -> str:
    if request.passport is None:
        return ""
    if request.passport.module_id.strip() != request.module_id.strip():
        return "module_id_mismatch"
    if request.passport.mount_point.strip() != request.mount_point.strip():
        return "mount_point_mismatch"
    return ""


def _evaluate_registration_guard(
    body: BodyConfigSnapshot,
    request: ModuleAttachRequest,
    guard: _RegistrationGuard,
) -> _RegistrationRejection | None:
    if guard.reason_code == MODULE_PASSPORT_MISSING:
        if _passport_has_required_shape(request.passport):
            return None
        return _RegistrationRejection(
            reason_code=guard.reason_code,
            passport_status="missing",
            audit_method="append_missing_passport_rejection",
            audit_payload={
                "module_id": request.module_id,
                "mount_point": request.mount_point,
            },
            result_context={},
        )

    if guard.reason_code == MODULE_PASSPORT_INVALID:
        validation_error = _passport_validation_error(request)
        if request.passport is None or not validation_error:
            return None
        return _RegistrationRejection(
            reason_code=guard.reason_code,
            passport_status="invalid",
            audit_method="append_invalid_passport_rejection",
            audit_payload={
                "module_id": request.module_id,
                "passport_module_id": request.passport.module_id,
                "mount_point": request.mount_point,
                "validation_error": validation_error,
            },
            result_context={
                "requested_module_id": request.module_id,
                "validation_error": validation_error,
                "passport_module_id": request.passport.module_id,
            },
        )

    if guard.reason_code == MOUNT_POINT_UNKNOWN:
        if request.mount_point in body.face_occupancy:
            return None
        return _RegistrationRejection(
            reason_code=guard.reason_code,
            passport_status=PASSPORT_STATUS_VALIDATED,
            audit_method="append_unknown_mount_rejection",
            audit_payload={
                "module_id": request.module_id,
                "mount_point": request.mount_point,
            },
            result_context={
                "requested_module_id": request.module_id,
                "known_mount": False,
            },
        )

    if guard.reason_code == MOUNT_POINT_OCCUPIED:
        occupant = body.face_occupancy.get(request.mount_point, "free")
        if occupant in ("", "free"):
            return None
        return _RegistrationRejection(
            reason_code=guard.reason_code,
            passport_status=PASSPORT_STATUS_VALIDATED,
            audit_method="append_occupied_rejection",
            audit_payload={
                "requested_module_id": request.module_id,
                "existing_module_id": occupant,
                "mount_point": request.mount_point,
            },
            result_context={
                "requested_module_id": request.module_id,
                "existing_module_id": occupant,
            },
        )

    if guard.reason_code == MODULE_MOUNT_CLASS_FORBIDDEN:
        rules = body.face_mount_classes.get(request.mount_point, {})
        module_class = (request.passport.module_class if request.passport else "").strip()
        forbidden_classes = tuple(rules.get("forbidden", ()))
        allowed_classes = tuple(rules.get("allowed", ()))
        if module_class not in forbidden_classes and (
            not allowed_classes or module_class in allowed_classes
        ):
            return None
        return _RegistrationRejection(
            reason_code=guard.reason_code,
            passport_status=PASSPORT_STATUS_VALIDATED,
            audit_method="append_class_forbidden_rejection",
            audit_payload={
                "module_id": request.module_id,
                "module_class": module_class,
                "mount_point": request.mount_point,
            },
            result_context={
                "requested_module_id": request.module_id,
                "existing_module_id": "",
            },
        )

    raise ValueError(f"Unhandled registration guard: {guard.reason_code}")


def _rejected_registration_result(
    request: ModuleAttachRequest,
    *,
    audit_event_id: str,
    reason_code: str,
    passport_status: str,
    result_context: dict[str, Any],
) -> RegistrationResult:
    return RegistrationResult(
        status="rejected",
        audit_event_id=audit_event_id,
        module_id=request.module_id,
        mount_point=request.mount_point,
        passport_status=passport_status,
        body_config_updated=False,
        runtime_ready=False,
        capability_status="not_evaluated",
        reason_code=reason_code,
        **result_context,
    )


def _registration_rejection_outcome(
    body: BodyConfigSnapshot,
    request: ModuleAttachRequest,
    *,
    audit_sink: RegistrationAuditSink,
    rejection: _RegistrationRejection,
) -> tuple[RegistrationResult, BodyConfigSnapshot]:
    append_audit = getattr(audit_sink, rejection.audit_method)
    audit_event_id = append_audit(
        request_id=request.request_id,
        timestamp=time.time(),
        **rejection.audit_payload,
    )
    return (
        _rejected_registration_result(
            request,
            audit_event_id=audit_event_id,
            reason_code=rejection.reason_code,
            passport_status=rejection.passport_status,
            result_context=rejection.result_context,
        ),
        body,
    )


def _registered_module_entry(
    request: ModuleAttachRequest,
    *,
    passport_status: str,
    capability_status: str,
) -> dict[str, Any]:
    return {
        "module_id": request.module_id,
        "mount_point": request.mount_point,
        "status": MODULE_STATUS_ATTACHED,
        "passport_status": passport_status,
        "capability_status": capability_status,
    }


def _registered_body_snapshot(
    body: BodyConfigSnapshot,
    request: ModuleAttachRequest,
    *,
    entry: dict[str, Any],
) -> BodyConfigSnapshot:
    new_occupancy = dict(body.face_occupancy)
    new_occupancy[request.mount_point] = request.module_id
    # Build a fully de-aliased snapshot (remediation C2): a frozen dataclass does not
    # prevent in-place mutation of nested mutable contents, so every nested structure is
    # copied — pre-existing module entry dicts, the new entry, and each face's mount-class
    # rule dict — so parent and child snapshots never share mutable state.
    return BodyConfigSnapshot(
        face_ids=body.face_ids,
        face_map_status=body.face_map_status,
        bayonet_states=dict(body.bayonet_states),
        face_occupancy=new_occupancy,
        modules=tuple(dict(m) for m in body.modules) + (dict(entry),),
        face_mount_classes={k: dict(v) for k, v in body.face_mount_classes.items()},
    )


def _attached_registration_result(
    request: ModuleAttachRequest,
    *,
    audit_event_id: str,
    passport_status: str,
    capability_status: str,
) -> RegistrationResult:
    return RegistrationResult(
        status=MODULE_STATUS_ATTACHED,
        audit_event_id=audit_event_id,
        module_id=request.module_id,
        mount_point=request.mount_point,
        passport_status=passport_status,
        body_config_updated=True,
        runtime_ready=False,
        capability_status=capability_status,
        reason_code=None,
    )


def _registration_success_outcome(
    body: BodyConfigSnapshot,
    request: ModuleAttachRequest,
    *,
    audit_sink: RegistrationAuditSink,
) -> tuple[RegistrationResult, BodyConfigSnapshot]:
    passport_status = PASSPORT_STATUS_VALIDATED
    capability_status = CAPABILITY_STATUS_INACTIVE  # registration does NOT activate capabilities
    entry = _registered_module_entry(
        request,
        passport_status=passport_status,
        capability_status=capability_status,
    )
    updated = _registered_body_snapshot(body, request, entry=entry)
    audit_event_id = audit_sink.append_registration(
        request_id=request.request_id,
        module_id=request.module_id,
        mount_point=request.mount_point,
        passport_status=passport_status,
        capability_status=capability_status,
        runtime_ready=False,
        timestamp=time.time(),
    )
    return (
        _attached_registration_result(
            request,
            audit_event_id=audit_event_id,
            passport_status=passport_status,
            capability_status=capability_status,
        ),
        updated,
    )


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
    for guard in _REGISTRATION_GUARDS:
        rejection = _evaluate_registration_guard(body, request, guard)
        if rejection is None:
            continue
        return _registration_rejection_outcome(
            body,
            request,
            audit_sink=audit_sink,
            rejection=rejection,
        )
    return _registration_success_outcome(body, request, audit_sink=audit_sink)


# --- RUNTIME_SLICE_0008: module attach validation pipeline v1 (orchestrator) ---------
#
# One ordered entrypoint over the slice 0001-0007 guards. It does NOT re-implement the
# checks: it runs register_module (already ordered) and packages the outcome into a
# single deterministic AttachDecision with the deciding stage, the audit event id and an
# ORION evidence-card id. It never mutates body_config itself and never owns truth — the
# decision/audit are runtime-owned; the evidence card stays an ORION projection.

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
    # Rejection context copied from RegistrationResult; empty/default on success.
    requested_module_id: str = ""
    existing_module_id: str = ""
    validation_error: str = ""
    passport_module_id: str = ""
    known_mount: bool = True


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
            requested_module_id=result.requested_module_id,
            existing_module_id=result.existing_module_id,
            validation_error=result.validation_error,
            passport_module_id=result.passport_module_id,
            known_mount=result.known_mount,
        ),
        updated,
    )
