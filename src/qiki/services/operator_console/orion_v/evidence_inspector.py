"""Unified ORION evidence Inspector — one render contract for §19 claims.

Canon (ORION_OS_SYSTEM inspector + IF-ORION-EVIDENCE §19): every operator claim is
inspected in the SAME order — Summary -> evidence Fields -> Reasons/Action -> Raw
(source/audit). Today F1/F2/F3/F8 each render evidence their own way; this module
gives a single reusable formatter over the §19.4 OrionEvidenceClaim so any screen
shows the identical, honest inspector block (no per-screen ad-hoc layout).
"""

from __future__ import annotations

from qiki.services.operator_console.orion_v.evidence_claim import (
    OrionEvidenceClaim,
    evidence_claim_from_field,
)
from qiki.services.operator_console.orion_v.hardware_view_model.types import SubsystemView


def format_evidence_claim(claim: OrionEvidenceClaim) -> list[str]:
    """Canonical inspector block for one §19.4 claim (Summary/Fields/Reasons/Action/Raw)."""
    lines = [f"◆ {claim.claim_id}  [{claim.status}]"]
    lines.append(f"  Сводка/Summary: {claim.claim_text}")
    lines.append(
        f"  Доверие/Trust: {claim.trust_status} | свежесть/freshness: {claim.freshness} | "
        f"источник/source: {claim.source_type}:{claim.source_id}"
    )
    if claim.reason_codes:
        lines.append(f"  Причины/Reasons: {', '.join(claim.reason_codes)}")
    if claim.operator_action:
        lines.append(f"  Действие/Action: {claim.operator_action}")
    lines.append(
        f"  Аудит/Raw: {claim.audit_link or '—'} | blackbox: {claim.blackbox_relevance}"
        + (f" | cmd: {claim.related_command_id}" if claim.related_command_id else "")
    )
    return lines


def claims_for_subsystem(
    view: SubsystemView | None,
    *,
    source_type: str = "telemetry",
) -> list[OrionEvidenceClaim]:
    """Project every field of a SubsystemView into a §19.4 evidence claim."""
    if view is None:
        return []
    return [
        evidence_claim_from_field(field, subsystem_id=view.id, source_type=source_type)
        for field in view.fields
    ]


def format_subsystem_inspector(
    view: SubsystemView | None,
    *,
    source_type: str = "telemetry",
    max_claims: int = 6,
) -> list[str]:
    """Full inspector text for a subsystem: header + per-field §19 claim blocks."""
    if view is None:
        return ["ИНСПЕКТОР/INSPECTOR: нет данных/no selection"]
    lines = [f"ИНСПЕКТОР/INSPECTOR — {view.title} [{view.status}]"]
    claims = claims_for_subsystem(view, source_type=source_type)
    if not claims:
        lines.append("  нет полей/no fields")
        return lines
    for claim in claims[:max_claims]:
        lines.extend(format_evidence_claim(claim))
    if len(claims) > max_claims:
        lines.append(f"  … +{len(claims) - max_claims} ещё/more")
    return lines
