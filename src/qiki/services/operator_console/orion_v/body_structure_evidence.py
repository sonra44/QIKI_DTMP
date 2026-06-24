"""RUNTIME_SLICE_0001 — read-only ORION evidence stub.

Surfaces an already-produced module-attach rejection (and its recorded audit
event) as an operator-facing fact. This is the minimal read-only consumer needed
to show the MODULE_PASSPORT_MISSING rejection — NOT the full #4908 ORION Evidence
Card.

Hard rule: ORION does not validate the module passport and does not call the
attach policy. It only displays what the runtime/policy layer already decided and
recorded in the audit event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RejectionEvidence:
    claim_type: str  # "module_attach_rejection"
    source_type: str  # "audit"
    read_only: bool  # True
    reason_code: str
    rejection_state: str  # "rejected"
    module_id: str
    source_owner: str
    operator_text: str
    audit_request_id: str
    audit_attempted_mount: str


def rejection_to_evidence(result: Any, audit_event: Any) -> RejectionEvidence:
    """Read-only mapping of a rejection + its audit event to display evidence.

    Closes the loop ``audit event -> ORION evidence``: the displayed fact is built
    from the recorded ``audit_event`` and must stay consistent with ``result``.
    Never validates the passport or invokes attach logic.
    """
    # Consistency guard: refuse to surface evidence that disagrees with the audit
    # record (the audit event is the recorded truth of the rejection).
    if (
        result.reason_code != audit_event.reason_code
        or result.source_owner != audit_event.source_owner
        or result.module_id != audit_event.module_id
    ):
        raise ValueError(
            "rejection/audit mismatch: refusing to surface inconsistent evidence"
        )

    reason = audit_event.reason_code
    if reason == "MODULE_PASSPORT_MISSING":
        operator_text = "attach rejected: passport missing"
    else:
        operator_text = f"attach rejected: {reason.lower()}"

    return RejectionEvidence(
        claim_type="module_attach_rejection",
        source_type="audit",
        read_only=True,
        reason_code=reason,
        rejection_state="rejected" if result.rejected else "accepted",
        module_id=audit_event.module_id,
        source_owner=audit_event.source_owner,
        operator_text=operator_text,
        audit_request_id=audit_event.request_id,
        audit_attempted_mount=audit_event.attempted_mount,
    )


@dataclass(frozen=True, slots=True)
class CommandLifecycleEvidence:
    """IF-CMD-BUS-001 (§18.7) read-only ORION surface of a command lifecycle.

    ADR-0015: ACK is not effect confirmation. publish/ACK/effect are surfaced exactly
    as the record reports them (missing / target-only in Stage 1); ORION never upgrades
    an unproduced stage to a positive label.
    """

    claim_type: str  # "command_lifecycle"
    source_type: str  # "audit"
    read_only: bool
    command_id: str
    validation_label: str
    published_label: str
    ack_label: str
    effect_label: str
    audit_label: str
    reason_codes: tuple[str, ...]
    operator_text: str


# §18.7 positive operator labels keyed by the raw lifecycle state. A stage only earns a
# positive label if its raw state is an explicit positive value; everything else
# (missing / target-only / unknown) is surfaced verbatim and never upgraded.
_POSITIVE_PUBLISH = {"published": "published"}
_POSITIVE_ACK = {"accepted": "ACK accepted", "ack_accepted": "ACK accepted"}
_POSITIVE_EFFECT = {"confirmed": "effect confirmed", "effect_confirmed": "effect confirmed"}


def _lifecycle_label(raw: str, positive: dict[str, str]) -> str:
    return positive.get(str(raw or ""), str(raw or ""))


def command_lifecycle_to_evidence(record: Any) -> CommandLifecycleEvidence:
    """Read-only ORION projection of a CommandLifecycleRecord (IF-CMD-BUS-001).

    Surfaces validation + audit (known from the attach path) and keeps publish/ACK/
    effect exactly as reported. Never validates or executes; never claims a missing
    effect as confirmed (ADR-0015).
    """
    validation = str(record.validation_state or "")
    published = _lifecycle_label(record.publish_state, _POSITIVE_PUBLISH)
    ack = _lifecycle_label(record.ACK_state, _POSITIVE_ACK)
    effect = _lifecycle_label(record.effect_state, _POSITIVE_EFFECT)

    if validation == "rejected":
        operator_text = "command rejected at validation; downstream stages not observed"
    else:
        # Stage-aware honesty: report exactly which stages are observed vs not, never
        # deny an observed stage and never claim an unobserved one (ADR-0015).
        observed = [
            lbl
            for lbl, is_positive in (
                (published, published == "published"),
                (ack, ack == "ACK accepted"),
                (effect, effect == "effect confirmed"),
            )
            if is_positive
        ]
        missing = [
            name
            for name, lbl, positive in (
                ("publish", published, "published"),
                ("ACK", ack, "ACK accepted"),
                ("effect", effect, "effect confirmed"),
            )
            if lbl != positive
        ]
        parts = ["command validated (allowed)"]
        if observed:
            parts.append("observed: " + ", ".join(observed))
        if missing:
            parts.append("not yet observed: " + "/".join(missing) + " (target-only)")
        operator_text = "; ".join(parts)

    return CommandLifecycleEvidence(
        claim_type="command_lifecycle",
        source_type="audit",
        read_only=True,
        command_id=str(record.command_id or ""),
        validation_label=validation,
        published_label=published,
        ack_label=ack,
        effect_label=effect,
        audit_label=str(record.audit_state or ""),
        reason_codes=tuple(record.reason_codes),
        operator_text=operator_text,
    )
