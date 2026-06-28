"""IF-ORION-EVIDENCE §19.4 evidence-claim contract + §19.5 reason mapping."""

from __future__ import annotations

from qiki.services.operator_console.orion_v.evidence_claim import (
    ORION_DATA_STALE,
    ORION_NOT_IMPLEMENTED,
    ORION_SOURCE_MISSING,
    ORION_TARGET_ONLY,
    evidence_claim_from_field,
)
from qiki.services.operator_console.orion_v.hardware_view_model.types import (
    TelemetryField,
    ViewStatus,
)


def _field(**kw) -> TelemetryField:
    base = dict(key="soc_pct", label="SoC", value=82.0, unit="%", status=ViewStatus.OK, hint="следить за зарядом")
    base.update(kw)
    return TelemetryField(**base)


def test_claim_has_all_19_4_required_fields() -> None:
    claim = evidence_claim_from_field(_field(), subsystem_id="power")
    # §19.4 required fields all present + populated.
    assert claim.claim_id == "power.soc_pct"
    assert claim.claim_text == "SoC: 82.0 %"
    assert claim.source_type == "telemetry"
    assert claim.source_id == "soc_pct"
    assert claim.freshness == "unknown"  # not derived -> honest unknown
    assert claim.trust_status == "trusted"  # present, not NO_DATA
    assert claim.status == str(ViewStatus.OK)
    assert claim.related_module_id == "power"
    assert claim.audit_link == "audit://telemetry/soc_pct"
    assert claim.operator_action == "следить за зарядом"
    assert claim.reason_codes == ()  # trusted+fresh -> no ORION reason


def test_missing_maps_to_orion_source_missing() -> None:
    field = _field(value=None, status=ViewStatus.NO_DATA, trust_status="missing",
                   reason_codes=("POWER_TELEM_MISSING",))
    claim = evidence_claim_from_field(field, subsystem_id="power")
    assert claim.trust_status == "missing"
    assert ORION_SOURCE_MISSING in claim.reason_codes


def test_stale_maps_to_orion_data_stale() -> None:
    field = _field(freshness="stale", trust_status="degraded", reason_codes=("POWER_TELEM_STALE",))
    claim = evidence_claim_from_field(field, subsystem_id="power")
    assert claim.freshness == "stale"
    assert ORION_DATA_STALE in claim.reason_codes


def test_comms_not_implemented_maps_to_orion_not_implemented() -> None:
    field = _field(key="link_state", trust_status="missing", reason_codes=("COMMS_NOT_IMPLEMENTED",))
    claim = evidence_claim_from_field(field, subsystem_id="comms")
    assert ORION_NOT_IMPLEMENTED in claim.reason_codes
    assert claim.claim_id == "comms.link_state"


def test_target_only_source_marks_orion_target_only() -> None:
    field = _field(key="nbl_state", value="rules-only", status=ViewStatus.NO_DATA)
    claim = evidence_claim_from_field(field, subsystem_id="nbl", source_type="target-only")
    assert claim.source_type == "target-only"
    assert ORION_TARGET_ONLY in claim.reason_codes


def test_unmapped_domain_reason_is_carried_through() -> None:
    field = _field(key="link_state", trust_status="degraded", reason_codes=("COMMS_POWER_BLOCK",))
    claim = evidence_claim_from_field(field, subsystem_id="comms")
    # Domain reason with no §19.5 mapping is preserved (not dropped).
    assert "COMMS_POWER_BLOCK" in claim.reason_codes
