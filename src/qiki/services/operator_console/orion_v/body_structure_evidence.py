"""RUNTIME_SLICE_0001 — read-only ORION evidence stub.

Surfaces an already-produced module-attach rejection (and its audit event) as an
operator-facing fact. This is the minimal read-only consumer required to show the
MODULE_PASSPORT_MISSING rejection — it is NOT the full #4908 ORION Evidence Card.

Hard rule: ORION does not validate the module passport and does not call the attach
policy. It only displays what the runtime/policy layer already decided.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RejectionEvidence:
    reason_code: str
    rejection_state: str  # "rejected"
    source_owner: str
    operator_text: str


def rejection_to_evidence(result: Any, audit_event: Any) -> RejectionEvidence:
    """Read-only mapping of a rejection + audit event to display evidence.

    Takes the already-produced result/audit objects; never validates the passport
    or invokes attach logic.
    """
    reason = result.reason_code
    if reason == "MODULE_PASSPORT_MISSING":
        operator_text = "attach rejected: passport missing"
    else:
        operator_text = f"attach rejected: {reason.lower()}"
    return RejectionEvidence(
        reason_code=reason,
        rejection_state="rejected" if result.rejected else "accepted",
        source_owner=result.source_owner,
        operator_text=operator_text,
    )
