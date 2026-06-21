"""RUNTIME_SLICE_0002 — ORION Evidence Card (read-only projection layer).

Turns an audit-backed body-structure rejection (a recorded
``event_store.SystemEvent`` of type ``module_attach_rejected`` from Slice 0001)
into a structured, read-only ORION Evidence Card.

Hard rule: the card is an ORION *projection* of the audit source. It is NOT a
truth-owner: it never marks a module runtime-ready and never surfaces a fact that
is not present in the audit payload. Canon mapping (enum/wording) lives in
``evidence_card_mapping`` (one owner per concern; this module only assembles).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from qiki.services.operator_console.orion_v.evidence_card_mapping import (
    card_type_for,
    evidence_status_for,
    missing_fields_for,
    operator_summary_for,
    source_type_for,
    subject_status_for,
    trust_status_for,
)

CARD_TYPE_BODY_MODULE_ATTACH_REJECTION = "BODY_MODULE_ATTACH_REJECTION"
CARD_TYPE_BODY_MODULE_ATTACH_REGISTERED = "BODY_MODULE_ATTACH_REGISTERED"

# Audit payload keys this projection is allowed to surface as facts (no invention).
_FACT_KEYS = (
    "module_id",
    "attempted_mount",
    "mount_point",
    "reason_code",
    "passport_status",
    "capability_status",
    "requested_module_id",
    "existing_module_id",
    "body_config_updated",
    "module_class",
    "validation_error",
    "known_mount",
)


@dataclass(frozen=True, slots=True)
class EvidenceCard:
    card_id: str
    card_type: str
    title: str
    subject_type: str
    subject_id: str
    operation: str
    subject_status: str  # domain outcome, e.g. "rejected"
    status: str  # §17 evidence-conformance, e.g. "implemented" / "missing"
    reason_code: str
    source_type: str  # "audit_event"
    source_id: str
    source_timestamp: float
    trust_status: str  # "audit_backed" / "missing"
    read_only: bool
    runtime_ready: bool
    facts: Mapping[str, Any]
    missing_fields: tuple[str, ...]
    related_audit_event_id: str
    related_command_id: str | None
    operator_summary: str


def evidence_card_from_audit_event(audit_event: Any) -> EvidenceCard:
    """Build a read-only EvidenceCard from a recorded audit SystemEvent.

    Reads only the audit source. Canon enum/wording decisions are delegated to
    ``evidence_card_mapping`` so this assembler stays a pure projection.
    """
    payload: dict[str, Any] = dict(getattr(audit_event, "payload", {}) or {})
    reason_code = str(getattr(audit_event, "reason", "") or payload.get("reason_code", ""))
    module_id = str(payload.get("module_id") or payload.get("requested_module_id") or "")
    event_id = str(getattr(audit_event, "event_id", ""))
    subject_status = subject_status_for(audit_event)

    # Facts are surfaced ONLY from the audit payload (no invention).
    facts: dict[str, Any] = {key: payload[key] for key in _FACT_KEYS if key in payload}

    return EvidenceCard(
        card_id=f"card:{event_id}",
        card_type=card_type_for(audit_event),
        title=f"Module attach: {subject_status}",
        subject_type="module",
        subject_id=module_id,
        operation="module_attach",
        subject_status=subject_status,
        status=evidence_status_for(audit_event),
        reason_code=reason_code,
        source_type=source_type_for(audit_event),
        source_id=event_id,
        source_timestamp=float(getattr(audit_event, "ts", 0.0) or 0.0),
        trust_status=trust_status_for(audit_event),
        read_only=True,
        runtime_ready=False,
        facts=facts,
        missing_fields=tuple(missing_fields_for(audit_event)),
        related_audit_event_id=event_id,
        related_command_id=payload.get("request_id"),
        operator_summary=operator_summary_for(audit_event),
    )
