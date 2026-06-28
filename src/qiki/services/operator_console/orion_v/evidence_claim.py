"""IF-ORION-EVIDENCE §19 generic evidence-claim contract.

Canon (06_INTERFACE_CONTROL §19.4) requires that EVERY operator claim ORION shows
carries a uniform evidence record — not just freshness/trust/reason. This module
defines that record (OrionEvidenceClaim) and a single builder that projects a
view-model TelemetryField into it, so any screen (the unified Inspector, F8
evidence, audit) reads one contract instead of per-screen ad-hoc fields.

ADR-0014 / §19.6: never a confident state without source; mark
target-only / not-implemented / stale / conflicting; ACK != effect.
"""

from __future__ import annotations

from dataclasses import dataclass

from qiki.services.operator_console.orion_v.hardware_view_model.types import (
    TelemetryField,
    ViewStatus,
)

# §19.5 ORION evidence reason codes.
ORION_SOURCE_MISSING = "ORION_SOURCE_MISSING"
ORION_DATA_STALE = "ORION_DATA_STALE"
ORION_TRUST_CONFLICT = "ORION_TRUST_CONFLICT"
ORION_TARGET_ONLY = "ORION_TARGET_ONLY"
ORION_NOT_IMPLEMENTED = "ORION_NOT_IMPLEMENTED"
ORION_CALCULATION_REQUIRED = "ORION_CALCULATION_REQUIRED"
ORION_EFFECT_UNCONFIRMED = "ORION_EFFECT_UNCONFIRMED"

# Map subsystem-domain reason codes (IF-POWER/THERMAL/COMMS-TELEM) onto the §19.5
# ORION evidence vocabulary. Anything not listed stays a domain code carried as-is.
_DOMAIN_TO_ORION_REASON: dict[str, str] = {
    "POWER_TELEM_MISSING": ORION_SOURCE_MISSING,
    "THERMAL_TELEM_MISSING": ORION_SOURCE_MISSING,
    "COMMS_NOT_IMPLEMENTED": ORION_NOT_IMPLEMENTED,
    "COMMS_UNAVAILABLE": ORION_SOURCE_MISSING,
    "POWER_TELEM_STALE": ORION_DATA_STALE,
    "THERMAL_TELEM_STALE": ORION_DATA_STALE,
    "COMMS_TELEM_STALE": ORION_DATA_STALE,
}


@dataclass(frozen=True, slots=True)
class OrionEvidenceClaim:
    """§19.4 required-fields evidence record for one operator claim."""

    claim_id: str
    claim_text: str
    source_type: str  # telemetry | derived | calculation | target-only | event | command
    source_id: str
    freshness: str  # fresh | stale | unknown
    trust_status: str  # trusted | degraded | missing
    status: str  # operator-facing claim status (ViewStatus value)
    related_command_id: str | None
    related_module_id: str | None
    reason_codes: tuple[str, ...]  # §19.5 ORION_* (+ any unmapped domain codes)
    audit_link: str | None
    blackbox_relevance: str  # none | low | high
    operator_action: str


def _orion_reason_codes(
    domain_reason_codes: tuple[str, ...],
    *,
    trust_status: str,
    freshness: str,
    source_type: str,
) -> tuple[str, ...]:
    """Project domain reason codes onto §19.5, then add evidence-state defaults."""
    out: list[str] = []
    for code in domain_reason_codes:
        out.append(_DOMAIN_TO_ORION_REASON.get(code, code))
    # Evidence-state fallbacks so the §19.5 status is never silently absent.
    if trust_status == "missing" and ORION_SOURCE_MISSING not in out:
        out.append(ORION_SOURCE_MISSING)
    if freshness == "stale" and ORION_DATA_STALE not in out:
        out.append(ORION_DATA_STALE)
    if source_type == "target-only" and ORION_TARGET_ONLY not in out:
        out.append(ORION_TARGET_ONLY)
    return tuple(dict.fromkeys(out))


def evidence_claim_from_field(
    field: TelemetryField,
    *,
    subsystem_id: str,
    source_type: str = "telemetry",
    related_command_id: str | None = None,
    operator_action: str = "",
    blackbox_relevance: str = "none",
) -> OrionEvidenceClaim:
    """Project a view-model TelemetryField into a §19.4 evidence claim (no invention).

    trust_status defaults honestly: present field -> trusted, NO_DATA -> missing.
    freshness defaults to "unknown" when the subsystem has not derived it.
    """
    freshness = field.freshness or "unknown"
    if field.trust_status is not None:
        trust_status = field.trust_status
    elif field.status is ViewStatus.NO_DATA:
        trust_status = "missing"
    else:
        trust_status = "trusted"

    claim_id = field.key if field.key.startswith(f"{subsystem_id}.") else f"{subsystem_id}.{field.key}"
    value_text = "" if field.value is None else str(field.value)
    unit_text = f" {field.unit}" if field.unit else ""
    claim_text = f"{field.label}: {value_text}{unit_text}".strip()

    return OrionEvidenceClaim(
        claim_id=claim_id,
        claim_text=claim_text,
        source_type=source_type,
        source_id=field.key,
        freshness=freshness,
        trust_status=trust_status,
        status=str(field.status),
        related_command_id=related_command_id,
        related_module_id=subsystem_id,
        reason_codes=_orion_reason_codes(
            field.reason_codes,
            trust_status=trust_status,
            freshness=freshness,
            source_type=source_type,
        ),
        audit_link=f"audit://telemetry/{field.key}",
        blackbox_relevance=blackbox_relevance,
        operator_action=operator_action or field.hint or "",
    )
