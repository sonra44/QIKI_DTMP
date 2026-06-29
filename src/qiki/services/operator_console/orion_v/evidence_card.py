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

from qiki.services.q_core_agent.core.evidence_card_id import make_evidence_card_id
from qiki.services.operator_console.orion_v.evidence_card_mapping import (
    ORION_SOURCE_MISSING,
    SOURCE_TYPE_AUDIT,
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
    "runtime_ready",
    "module_class",
    "validation_error",
    "known_mount",
    "source_owner",  # MEDIUM #9 — surface audit provenance owner (ADR-0014: "ORION must show source")
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
    # Evidence conformance only: "implemented" means the card projection is
    # audit-backed and complete. It never means module runtime-ready.
    status: str  # §17 evidence-conformance, e.g. "implemented" / "missing"
    reason_code: str
    source_type: str  # "audit" for trusted audit-backed source
    source_id: str
    source_timestamp: float
    trust_status: str  # canon §17: "trusted" / "missing"
    read_only: bool
    runtime_ready: bool
    facts: Mapping[str, Any]
    missing_fields: tuple[str, ...]
    related_audit_event_id: str
    related_command_id: str | None
    operator_summary: str
    # IF-ORION-EVIDENCE-001 / canon §17 evidence fields — conservative, audit-derived (no overclaim).
    claim_id: str = ""
    claim_text: str = ""
    freshness: str = "unknown"
    related_module_id: str = ""
    reason_codes: tuple[str, ...] = ()
    audit_link: str = ""
    blackbox_relevance: bool = False
    operator_action: str | None = None


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

    card_id = make_evidence_card_id(event_id)
    source_type = source_type_for(audit_event)
    missing_fields = tuple(missing_fields_for(audit_event))
    operator_summary = operator_summary_for(audit_event)
    # reason_codes: existing domain reason + ORION missing-source code when that path is active.
    reason_codes = tuple(
        code
        for code in (reason_code, ORION_SOURCE_MISSING if ORION_SOURCE_MISSING in missing_fields else "")
        if code
    )

    return EvidenceCard(
        card_id=card_id,
        card_type=card_type_for(audit_event),
        title=f"Module attach: {subject_status}",
        subject_type="module",
        subject_id=module_id,
        operation="module_attach",
        subject_status=subject_status,
        status=evidence_status_for(audit_event),
        reason_code=reason_code,
        source_type=source_type,
        source_id=event_id,
        source_timestamp=float(getattr(audit_event, "ts", 0.0) or 0.0),
        trust_status=trust_status_for(audit_event),
        read_only=True,
        runtime_ready=False,
        facts=facts,
        missing_fields=missing_fields,
        related_audit_event_id=event_id,
        related_command_id=payload.get("request_id"),
        operator_summary=operator_summary,
        # IF-ORION-EVIDENCE-001 conservative, audit-derived fields (no overclaim).
        claim_id=card_id,
        claim_text=operator_summary,
        freshness="unknown",
        related_module_id=module_id,
        reason_codes=reason_codes,
        audit_link=event_id if source_type == SOURCE_TYPE_AUDIT else "",
        blackbox_relevance=bool(payload.get("blackbox_relevance", False)),
        operator_action=None,
    )
