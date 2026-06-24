"""RUNTIME_SLICE_0002 — pure ORION Evidence Card mapping helpers.

This module maps the existing audit event shape into the small evidence-card
vocabulary for Slice 0002. It does not own truth and does not validate module
passports; it only classifies an already-recorded audit event for read-only
ORION presentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qiki.services.q_core_agent.core.body_structure import (
    MODULE_MOUNT_CLASS_FORBIDDEN,
    MODULE_PASSPORT_INVALID,
    MODULE_PASSPORT_MISSING,
    MOUNT_POINT_UNKNOWN,
    MOUNT_POINT_OCCUPIED,
    PASSPORT_VALIDATOR_OWNER,
    SOURCE_OWNER,
)
from qiki.services.q_core_agent.core.event_store import SystemEvent, TruthState

BODY_MODULE_ATTACH_REJECTION = "BODY_MODULE_ATTACH_REJECTION"
BODY_MODULE_ATTACH_REGISTERED = "BODY_MODULE_ATTACH_REGISTERED"
ORION_SOURCE_MISSING = "ORION_SOURCE_MISSING"

SOURCE_TYPE_AUDIT_EVENT = "audit_event"
SOURCE_TYPE_MISSING = "missing"
TRUST_STATUS_AUDIT_BACKED = "audit_backed"
TRUST_STATUS_MISSING = "missing"
EVIDENCE_STATUS_IMPLEMENTED = "implemented"
EVIDENCE_STATUS_MISSING = "missing"
SUBJECT_STATUS_REJECTED = "rejected"
SUBJECT_STATUS_ATTACHED = "attached"
SUBJECT_STATUS_MISSING = "missing"
PASSPORT_STATUS_VALIDATED = "validated"
CAPABILITY_STATUS_INACTIVE = "inactive"

_MODULE_ATTACH_REJECTED = "module_attach_rejected"
_MODULE_ATTACH_REGISTERED = "module_attach_registered"
_REJECTION_REQUIRED_PAYLOAD_FIELDS: tuple[str, ...] = ("module_id", "attempted_mount", "reason_code")
_REGISTRATION_REQUIRED_PAYLOAD_FIELDS: tuple[str, ...] = (
    "module_id",
    "mount_point",
    "passport_status",
    "capability_status",
    "runtime_ready",
)
_FORBIDDEN_OPERATOR_WORDING: tuple[str, ...] = (
    "module installed",
    "module active",
    "capabilities active",
    "powered",
    "command unlocked",
    "pdu enabled",
    "thermally cleared",
    "bridge allowed",
    "hard lock verified",
    "runtime conforms",
    "qiki body implemented",
)
_REJECTION_SUMMARY_BY_REASON: dict[str, str] = {
    MODULE_PASSPORT_INVALID: "attach rejected: passport invalid",
    MODULE_PASSPORT_MISSING: "attach rejected: passport missing",
    MODULE_MOUNT_CLASS_FORBIDDEN: "attach rejected: module class forbidden",
    MOUNT_POINT_UNKNOWN: "attach rejected: mount point unknown",
    MOUNT_POINT_OCCUPIED: "attach rejected: mount point occupied",
}


@dataclass(frozen=True, slots=True)
class EvidenceCardMapping:
    card_type: str
    subject_type: str
    subject_status: str
    status: str
    trust_status: str
    source_type: str
    source_id: str
    reason_code: str
    module_id: str
    attempted_mount: str
    runtime_ready: bool
    read_only: bool
    operator_summary: str
    missing_fields: tuple[str, ...] = ()
    passport_status: str = ""
    capability_status: str = ""


def card_type_for(event: Any) -> str:
    if _is_module_attach_registered(event):
        return BODY_MODULE_ATTACH_REGISTERED
    return BODY_MODULE_ATTACH_REJECTION


_ALLOWED_AUDIT_OWNERS: frozenset[str] = frozenset({SOURCE_OWNER, PASSPORT_VALIDATOR_OWNER})


def _is_genuine_audit_event(event: Any) -> bool:
    """H5 trust gate — only a real, OK, owner-consistent SystemEvent is audit-backed.

    A shaped/duck-typed object, a non-OK ``truth_state``, an unrecognized owner
    subsystem, or a payload whose ``source_owner`` does not match the event
    subsystem must NOT be treated as a trusted audit record (forgery/replay gap,
    audit finding H5).
    """
    if not isinstance(event, SystemEvent):
        return False
    if event.truth_state != TruthState.OK:
        return False
    if event.subsystem not in _ALLOWED_AUDIT_OWNERS:
        return False
    payload = event.payload
    if not isinstance(payload, dict):
        return False
    return str(payload.get("source_owner") or "") == event.subsystem


def source_type_for(event: Any) -> str:
    if _is_supported_module_attach_event(event) and _is_genuine_audit_event(event):
        return SOURCE_TYPE_AUDIT_EVENT
    return SOURCE_TYPE_MISSING


def trust_status_for(event: Any) -> str:
    return TRUST_STATUS_AUDIT_BACKED if source_type_for(event) == SOURCE_TYPE_AUDIT_EVENT else TRUST_STATUS_MISSING


def evidence_status_for(event: Any) -> str:
    if source_type_for(event) == SOURCE_TYPE_AUDIT_EVENT and not missing_fields_for(event):
        return EVIDENCE_STATUS_IMPLEMENTED
    return EVIDENCE_STATUS_MISSING


def subject_status_for(event: Any) -> str:
    if _is_module_attach_rejection(event):
        return SUBJECT_STATUS_REJECTED
    if _is_module_attach_registered(event):
        return SUBJECT_STATUS_ATTACHED
    return SUBJECT_STATUS_MISSING


def missing_fields_for(event: Any) -> list[str]:
    payload = getattr(event, "payload", None)
    required = _required_payload_fields_for(event)
    if not isinstance(payload, dict):
        return [ORION_SOURCE_MISSING, *required]
    missing = [field for field in required if not _payload_field_present(payload, field)]
    if source_type_for(event) == SOURCE_TYPE_MISSING or missing:
        return [ORION_SOURCE_MISSING, *missing]
    return missing


def operator_summary_for(event: Any) -> str:
    if _is_module_attach_registered(event):
        return f"module registered: passport {PASSPORT_STATUS_VALIDATED}, capabilities {CAPABILITY_STATUS_INACTIVE}"
    reason = _reason_code_for(event)
    if reason in _REJECTION_SUMMARY_BY_REASON:
        return _REJECTION_SUMMARY_BY_REASON[reason]
    if reason:
        return f"attach rejected: {reason.lower()}"
    return "attach rejected: source missing"


def forbidden_wording_violations(text: str) -> tuple[str, ...]:
    lower = str(text or "").lower()
    return tuple(item for item in _FORBIDDEN_OPERATOR_WORDING if item in lower)


def map_module_attach_rejection_event(event: Any) -> EvidenceCardMapping:
    payload = getattr(event, "payload", None)
    data = payload if isinstance(payload, dict) else {}
    missing = tuple(missing_fields_for(event))
    source_type = source_type_for(event)
    return EvidenceCardMapping(
        card_type=BODY_MODULE_ATTACH_REJECTION,
        subject_type="module",
        subject_status=subject_status_for(event),
        status=evidence_status_for(event),
        trust_status=trust_status_for(event) if not missing else "missing",
        source_type=source_type,
        source_id=str(getattr(event, "event_id", "") or "") if source_type == SOURCE_TYPE_AUDIT_EVENT else "",
        reason_code=_reason_code_for(event),
        module_id=str(data.get("module_id") or ""),
        attempted_mount=str(data.get("attempted_mount") or ""),
        runtime_ready=False,
        read_only=True,
        operator_summary=operator_summary_for(event),
        missing_fields=missing,
    )


def map_module_attach_registered_event(event: Any) -> EvidenceCardMapping:
    payload = getattr(event, "payload", None)
    data = payload if isinstance(payload, dict) else {}
    missing = tuple(missing_fields_for(event))
    source_type = source_type_for(event)
    return EvidenceCardMapping(
        card_type=card_type_for(event),
        subject_type="module",
        subject_status=subject_status_for(event),
        status=evidence_status_for(event),
        trust_status=trust_status_for(event) if not missing else TRUST_STATUS_MISSING,
        source_type=source_type,
        source_id=str(getattr(event, "event_id", "") or "") if source_type == SOURCE_TYPE_AUDIT_EVENT else "",
        reason_code=_reason_code_for(event),
        module_id=str(data.get("module_id") or ""),
        attempted_mount=str(data.get("attempted_mount") or data.get("mount_point") or ""),
        runtime_ready=bool(data.get("runtime_ready")) if "runtime_ready" in data else False,
        read_only=True,
        operator_summary=operator_summary_for(event),
        missing_fields=missing,
        passport_status=str(data.get("passport_status") or ""),
        capability_status=str(data.get("capability_status") or ""),
    )


def _is_module_attach_rejection(event: Any) -> bool:
    return str(getattr(event, "event_type", "") or "").strip() == _MODULE_ATTACH_REJECTED


def _is_module_attach_registered(event: Any) -> bool:
    return str(getattr(event, "event_type", "") or "").strip() == _MODULE_ATTACH_REGISTERED


def _is_supported_module_attach_event(event: Any) -> bool:
    return _is_module_attach_rejection(event) or _is_module_attach_registered(event)


def _reason_code_for(event: Any) -> str:
    payload = getattr(event, "payload", None)
    if isinstance(payload, dict):
        reason = str(payload.get("reason_code") or "").strip()
        if reason:
            return reason
    return str(getattr(event, "reason", "") or "").strip()


def _required_payload_fields_for(event: Any) -> tuple[str, ...]:
    if _is_module_attach_registered(event):
        return _REGISTRATION_REQUIRED_PAYLOAD_FIELDS
    return _REJECTION_REQUIRED_PAYLOAD_FIELDS


def _payload_field_present(payload: dict[str, Any], field: str) -> bool:
    if field == "runtime_ready":
        return field in payload and isinstance(payload.get(field), bool)
    return bool(str(payload.get(field) or "").strip())
