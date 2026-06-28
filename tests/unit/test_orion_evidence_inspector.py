"""Unified §19 evidence inspector renderer."""

from __future__ import annotations

from qiki.services.operator_console.orion_v.evidence_inspector import (
    claims_for_subsystem,
    format_evidence_claim,
    format_subsystem_inspector,
)
from qiki.services.operator_console.orion_v.evidence_claim import evidence_claim_from_field
from qiki.services.operator_console.orion_v.hardware_view_model.types import (
    SubsystemView,
    TelemetryField,
    ViewStatus,
)


def _view() -> SubsystemView:
    return SubsystemView(
        id="power",
        title="Power / Charge",
        status=ViewStatus.WARN,
        summary="Заряд 12%",
        fields=[
            TelemetryField(key="soc_pct", label="SoC", value=12.0, unit="%", status=ViewStatus.WARN,
                           hint="снизить нагрузку", trust_status="trusted", freshness="fresh"),
            TelemetryField(
                key="battery_1_voltage_v",
                label="Battery 1",
                value=28.4,
                unit="V",
                status=ViewStatus.OK,
                hint="",
                trust_status="trusted",
                freshness="fresh",
            ),
            TelemetryField(
                key="battery_2_voltage_v",
                label="Battery 2",
                value=27.9,
                unit="V",
                status=ViewStatus.OK,
                hint="",
                trust_status="trusted",
                freshness="fresh",
            ),
            TelemetryField(key="supercap_soc_pct", label="Supercap", value=None, unit="%",
                           status=ViewStatus.NO_DATA, hint="", trust_status="missing",
                           reason_codes=("POWER_TELEM_MISSING",)),
        ],
    )


def test_format_evidence_claim_canonical_order() -> None:
    claim = evidence_claim_from_field(_view().fields[0], subsystem_id="power")
    lines = format_evidence_claim(claim)
    text = "\n".join(lines)
    assert "power.soc_pct" in lines[0]
    assert "Сводка/Summary:" in text
    assert "Доверие/Trust:" in text and "источник/source: telemetry:soc_pct" in text
    assert "Действие/Action: снизить нагрузку" in text
    assert "Аудит/Raw:" in text

def test_claims_for_subsystem_one_per_field() -> None:
    claims = claims_for_subsystem(_view())
    assert [c.claim_id for c in claims] == [
        "power.soc_pct",
        "power.battery_1_voltage_v",
        "power.battery_2_voltage_v",
        "power.supercap_soc_pct",
    ]
    # missing supercap carries the §19.5 ORION_SOURCE_MISSING
    assert "ORION_SOURCE_MISSING" in claims[3].reason_codes


def test_format_subsystem_inspector_header_and_blocks() -> None:
    lines = format_subsystem_inspector(_view())
    text = "\n".join(lines)
    assert "ИНСПЕКТОР/INSPECTOR — Power / Charge" in lines[0]
    assert (
        "power.soc_pct" in text
        and "power.battery_1_voltage_v" in text
        and "power.battery_2_voltage_v" in text
        and "power.supercap_soc_pct" in text
    )
    assert "ORION_SOURCE_MISSING" in text  # missing field evidence visible


def test_inspector_none_view_is_honest() -> None:
    assert "нет данных" in format_subsystem_inspector(None)[0]
