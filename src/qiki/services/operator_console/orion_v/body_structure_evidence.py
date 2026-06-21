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
