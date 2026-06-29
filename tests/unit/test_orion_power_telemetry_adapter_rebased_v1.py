from __future__ import annotations

from dataclasses import dataclass

from qiki.services.operator_console.orion_v.evidence_card_vm import render_card_text
from qiki.services.operator_console.orion_v.power_evidence import power_to_evidence
from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    build_power_thermal_console_view_model,
    build_power_thermal_console_view_model_from_telemetry,
    build_power_thermal_evidence_card_vms,
    format_power_accumulator_mfd_lines,
    format_power_thermal_cockpit_line,
)


def _render(vm) -> str:
    evidence = "\n".join(render_card_text(card) for card in build_power_thermal_evidence_card_vms(vm))
    return (
        format_power_thermal_cockpit_line(vm)
        + "\n"
        + "\n".join(format_power_accumulator_mfd_lines(vm))
        + "\n"
        + evidence
    )


def test_power_telemetry_adapter_missing_snapshot_is_unknown_and_not_seed_defaults() -> None:
    vm = build_power_thermal_console_view_model_from_telemetry({})
    rendered = _render(vm)

    assert vm.source == "missing_power_telemetry"
    assert vm.transport == "orion telemetry snapshot adapter"
    assert vm.trust_status == "missing"
    assert vm.battery_soc_pct is None
    assert vm.supercap_soc_pct is None
    assert "POWER_TELEM_MISSING" in vm.reason_codes
    assert "SoC_bat=unknown" in rendered
    assert "SoC_cap=unknown" in rendered
    assert "SoC_bat: unknown" in rendered
    assert "SoC_cap: unknown" in rendered
    assert "SoC_bat=84%" not in rendered
    assert "SoC_cap=61%" not in rendered
    assert "None%" not in rendered
    assert "-%" not in rendered


def test_default_power_seed_is_unknown_not_legacy_84_61_fixture() -> None:
    vm = build_power_thermal_console_view_model()
    rendered = _render(vm)

    assert vm.trust_status == "fixture_only"
    assert vm.battery_soc_pct is None
    assert vm.supercap_soc_pct is None
    assert "SoC_bat=unknown" in rendered
    assert "SoC_cap=unknown" in rendered
    assert "84%" not in rendered
    assert "61%" not in rendered


def test_power_telemetry_adapter_uses_runtime_power_fields_and_current_terms() -> None:
    vm = build_power_thermal_console_view_model_from_telemetry(
        {
            "source": "q_sim_service.world_model.power",
            "power": {
                "soc_pct": 42.0,
                "supercap_soc_pct": 79.0,
                "bus_v": 28.0,
                "bus_a": 1.25,
                "loads_w": {"base": 10.0, "radar": 5.5},
                "sources_w": {"solar": 40.0, "supercap_discharge": 12.0},
                "pdu_throttled": False,
            },
            "thermal": {"nodes": [{"id": "battery", "temp_c": 29.0}]},
        }
    )
    rendered = _render(vm)

    assert vm.battery_soc_pct == 42
    assert vm.supercap_soc_pct == 79
    assert vm.source == "q_sim_service.world_model.power"
    assert vm.trust_status == "trusted"
    assert vm.runtime_conformance == "telemetry adapter; full PDU runtime not claimed"
    assert vm.source_generation_w == 40.0
    assert vm.bus_voltage_v == 28.0
    assert vm.bus_current_a == 1.25
    assert ("base", 10.0) in vm.loads_w
    assert "SoC_bat=42%" in rendered
    assert "SoC_cap=79%" in rendered
    assert "source_generation_W: 40.0" in rendered
    assert "bus_voltage_V: 28.00" in rendered
    assert "loads_W: base=10.0, radar=5.5" in rendered
    assert "PDU_boundary: target-only; no full PDU runtime in this patch" in rendered
    assert "PDU_allowance" not in rendered
    assert "telemetry_backed" not in rendered
    assert "degraded" not in rendered


def test_power_telemetry_adapter_uses_stale_conflicting_missing_trust_vocabulary() -> None:
    stale = build_power_thermal_console_view_model_from_telemetry(
        {
            "freshness": "stale",
            "power": {
                "soc_pct": 80.0,
                "supercap_soc_pct": 80.0,
                "bus_v": 28.0,
                "bus_a": 1.0,
                "loads_w": {},
            },
        }
    )
    conflicting = build_power_thermal_console_view_model_from_telemetry(
        {
            "power": {
                "soc_pct": 80.0,
                "supercap_soc_pct": 80.0,
                "bus_v": 0.0,
                "bus_a": 1.0,
                "loads_w": {},
                "sources_w": {"solar": 0.0},
            }
        }
    )
    missing = build_power_thermal_console_view_model_from_telemetry({})

    assert stale.trust_status == "stale"
    assert "POWER_TELEM_STALE" in stale.reason_codes
    assert conflicting.trust_status == "conflicting"
    assert "BUS_UNSTABLE" in conflicting.reason_codes
    assert missing.trust_status == "missing"


@dataclass(frozen=True)
class _LegacyPowerRecord:
    battery_soc_pct: float | None = None
    supercap_soc_pct: float | None = None
    battery_temp_state: str | None = None
    supercap_temp_state: str | None = None
    bus_voltage_V: float | None = None
    bus_current_A: float | None = None
    freshness: str = ""
    trust_status: str = ""
    reason_codes: tuple[str, ...] = ()


def test_legacy_power_evidence_uses_soc_terms_and_unknown() -> None:
    evidence = power_to_evidence(_LegacyPowerRecord())

    assert evidence.battery_soc_label == "unknown"
    assert evidence.supercap_soc_label == "unknown"
    assert evidence.soc_bat_label == "unknown"
    assert evidence.soc_cap_label == "unknown"
    assert "SoC_bat unknown" in evidence.operator_text
    assert "SoC_cap unknown" in evidence.operator_text
    assert "battery: SoC" not in evidence.operator_text
    assert "supercap: SoC" not in evidence.operator_text
    assert "missing" not in evidence.operator_text
