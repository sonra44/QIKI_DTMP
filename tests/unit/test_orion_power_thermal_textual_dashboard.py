from __future__ import annotations

from pathlib import Path

from qiki.services.operator_console.orion_v.evidence_card_vm import render_card_text
from qiki.services.operator_console.orion_v.power_thermal_view_model import (
    ThermalNodeView,
    build_power_thermal_console_view_model,
    build_power_thermal_console_view_model_from_telemetry,
    build_power_thermal_evidence_card_vms,
    format_power_thermal_cockpit_line,
    format_power_thermal_system_summary,
    get_power_thermal_console_view_model,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ORION_V = REPO_ROOT / "src/qiki/services/operator_console/orion_v"
WIDGETS = ORION_V / "widgets"
SCREENS = ORION_V / "screens"


def test_power_thermal_seed_surfaces_battery_supercap_and_thermal_nodes() -> None:
    vm = get_power_thermal_console_view_model()

    assert vm.battery_soc_pct is None
    assert vm.supercap_soc_pct is None
    assert vm.bus_state == "unknown"
    assert vm.pdu_state == "unknown"
    assert vm.peak_readiness == "unknown"
    assert len(vm.thermal_nodes) >= 6
    assert {node.node_id for node in vm.thermal_nodes} >= {
        "T_battery",
        "T_supercap",
        "T_pdu",
        "T_sensor_head",
        "T_comms",
        "T_core",
    }
    assert vm.source == "local_power_thermal_seed_fixture"
    assert vm.transport == "direct in-process adapter"
    assert vm.runtime_conformance == "not claimed"
    assert vm.read_only is True
    assert "POWER_TELEM_MISSING" in vm.reason_codes


def test_explicit_power_thermal_seed_values_still_drive_readiness() -> None:
    vm = build_power_thermal_console_view_model(battery_soc_pct=84, supercap_soc_pct=61)

    assert vm.battery_soc_pct == 84
    assert vm.supercap_soc_pct == 61
    assert vm.battery_soc_pct != vm.supercap_soc_pct
    assert vm.peak_readiness == "limited"
    assert "PEAK_LIMITED" in vm.reason_codes


def test_low_supercap_blocks_peak_and_shows_cap_low() -> None:
    vm = build_power_thermal_console_view_model(supercap_soc_pct=12)

    assert vm.peak_ready is False
    assert vm.peak_readiness == "blocked"
    assert "CAP_LOW" in vm.reason_codes
    assert "boost" in vm.blocked_commands

    line = format_power_thermal_cockpit_line(vm)
    assert "SoC_cap=12%" in line
    assert "peak=blocked" in line
    assert "CAP_LOW" in line


def test_f1_power_line_surfaces_freshness_and_marks_stale() -> None:
    # F-4: the glanceable F1 POWER line must carry telemetry freshness (owned
    # per-subsystem by the power VM) and mark stale data, not hide it.
    fresh_line = format_power_thermal_cockpit_line(
        build_power_thermal_console_view_model_from_telemetry(
            {"power": {"soc_pct": 80.0, "bus_v": 27.9}, "freshness": "fresh"}
        )
    )
    assert "freshness=fresh" in fresh_line
    assert "[УСТАРЕЛО]" not in fresh_line
    stale_line = format_power_thermal_cockpit_line(
        build_power_thermal_console_view_model_from_telemetry(
            {"power": {"soc_pct": 80.0, "bus_v": 27.9}, "freshness": "stale"}
        )
    )
    assert "freshness=stale [УСТАРЕЛО]" in stale_line


def test_thermal_orange_marks_blocked_command_and_reason_code() -> None:
    vm = build_power_thermal_console_view_model(
        thermal_nodes=(
            ThermalNodeView("T_battery", "green", 28.0),
            ThermalNodeView(
                "T_supercap",
                "orange",
                55.0,
                blocked_commands=("boost",),
                reason_codes=("THERMAL_SUPERCAP_ORANGE",),
            ),
        )
    )

    assert vm.peak_ready is False
    assert vm.thermal_status == "orange"
    assert "THERMAL_SUPERCAP_ORANGE" in vm.reason_codes
    assert "boost" in vm.blocked_commands


def test_f1_f2_and_f8_render_power_thermal_status() -> None:
    vm = get_power_thermal_console_view_model()
    f1 = format_power_thermal_cockpit_line(vm)
    f2 = format_power_thermal_system_summary(vm)
    f8 = "\n".join(render_card_text(card) for card in build_power_thermal_evidence_card_vms(vm))

    assert "POWER(local_power_thermal_seed_fixture) | SoC_bat=unknown | SoC_cap=unknown" in f1
    assert "peak=unknown" in f1
    assert "Power / Thermal / Accumulator" in f2
    assert "SoC_bat: unknown" in f2
    assert "SoC_cap: unknown" in f2
    assert "canonical_chain: source -> battery -> bus -> supercap -> peak consumers" in f2
    assert "PDU_boundary: target-only; no full PDU runtime in this patch" in f2
    assert "Thermal Nodes" in f2
    assert "POWER_THERMAL_STATUS" in f8
    assert "SoC_bat: unknown" in f8
    assert "SoC_cap: unknown" in f8
    assert build_power_thermal_evidence_card_vms(vm)[0].state_key == "missing"
    assert "source: local_power_thermal_seed_fixture" in f8
    assert "POWER_TELEM_MISSING" in f8
    assert "read_only: true" in f8
    assert "runtime_conformance: not claimed" in f8


def test_power_accumulator_terminology_uses_current_soc_terms() -> None:
    vm = build_power_thermal_console_view_model(battery_soc_pct=84, supercap_soc_pct=61)
    f2 = format_power_thermal_system_summary(vm)

    assert "SoC_bat: 84%" in f2
    assert "SoC_cap: 61%" in f2
    assert "Battery / Long-duration reserve" in f2
    assert "Supercap / Peak buffer" in f2
    assert "role: peak-action readiness for short peak actions" in f2
    assert "single energy" not in f2.lower()


def test_power_accumulator_nullable_values_are_unknown_and_block_peaks() -> None:
    vm = build_power_thermal_console_view_model(battery_soc_pct=None, supercap_soc_pct=None)
    f1 = format_power_thermal_cockpit_line(vm)
    f2 = format_power_thermal_system_summary(vm)
    f8 = "\n".join(render_card_text(card) for card in build_power_thermal_evidence_card_vms(vm))

    assert vm.peak_ready is False
    assert vm.peak_readiness == "unknown"
    assert "POWER_TELEM_MISSING" in vm.reason_codes
    assert "SoC_bat=unknown" in f1
    assert "SoC_cap=unknown" in f1
    assert "SoC_bat: unknown" in f2
    assert "SoC_cap: unknown" in f2
    assert "SoC_bat: unknown" in f8
    assert "SoC_cap: unknown" in f8
    assert "None%" not in f1 + f2 + f8
    assert "-%" not in f1 + f2 + f8


def test_f1_f2_f8_files_mount_power_thermal_surfaces() -> None:
    cockpit = (SCREENS / "cockpit.py").read_text()
    systems = (SCREENS / "systems.py").read_text()
    evidence = (SCREENS / "evidence_stream.py").read_text()

    assert "format_power_thermal_cockpit_line" in cockpit
    assert "power_thermal_line" in cockpit
    assert "PowerThermalTextualDashboard" in systems
    assert 'id="orionv-power-thermal-dashboard"' in systems
    assert "build_power_thermal_console_view_model_from_telemetry(self._telemetry)" in systems
    assert "build_power_thermal_evidence_card_vms" in evidence
    assert "POWER_THERMAL_STATUS" in (ORION_V / "power_thermal_view_model.py").read_text()


def test_power_thermal_textual_widget_files_use_textual_widgets() -> None:
    dashboard = (SCREENS / "power_thermal_textual.py").read_text()
    panel = (WIDGETS / "power_thermal_panel.py").read_text()
    table = (WIDGETS / "thermal_node_table.py").read_text()
    status = (WIDGETS / "power_status_bar.py").read_text()

    assert "PowerThermalTextualDashboard" in dashboard
    assert "PowerStatusBar" in dashboard
    assert "PowerThermalPanel" in dashboard
    assert "ThermalNodeTable" in dashboard
    assert "class ThermalNodeTable(DataTable)" in table
    assert "add_columns" in table
    assert "add_row" in table
    assert "class PowerStatusBar(Static)" in status
    assert "class PowerThermalPanel(Static)" in panel


def test_power_thermal_textual_imports_when_textual_dependency_is_installed() -> None:
    import pytest

    pytest.importorskip("textual")
    from qiki.services.operator_console.orion_v.screens.power_thermal_textual import (  # noqa: PLC0415
        PowerThermalTextualDashboard,
    )

    widget = PowerThermalTextualDashboard(get_power_thermal_console_view_model())
    assert widget is not None
