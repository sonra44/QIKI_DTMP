from __future__ import annotations

from pathlib import Path

from qiki.services.operator_console.orion_v.mfd_layout import (
    MFD_LEFT_BUTTONS,
    MFD_RIGHT_BUTTONS,
    mfd_button_specs,
    softkey_bar,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ORION_V = REPO_ROOT / "src/qiki/services/operator_console/orion_v"
SCREENS = ORION_V / "screens"


def test_mfd_button_catalog_restores_left_and_right_operator_sets() -> None:
    assert tuple(button.label for button in MFD_LEFT_BUTTONS) == ("РАДАР", "НАВ", "ЦЕЛЬ", "СЕКТОР", "МИССИЯ")
    assert tuple(button.label for button in MFD_RIGHT_BUTTONS) == (
        "СИСТ",
        "СЕНС",
        "ПИТ",
        "ТЕПЛО",
        "СВЯЗЬ",
        "ДВИГ",
        "СТЫК",
        "ЖУРН",
        "ПРОЦ",
    )
    assert mfd_button_specs("left") == MFD_LEFT_BUTTONS
    assert mfd_button_specs("right") == MFD_RIGHT_BUTTONS
    assert "B проверка корпуса" in softkey_bar()
    assert "F8 улики" in softkey_bar()


def test_f1_cockpit_restores_left_right_mfd_shell_and_keeps_legacy_buttons() -> None:
    cockpit = (SCREENS / "cockpit.py").read_text()

    assert "orionv-mfd-root" in cockpit
    assert "orionv-mfd-status" in cockpit
    assert "orionv-mfd-left-buttons" in cockpit
    assert "orionv-mfd-left-screen" in cockpit
    assert "orionv-mfd-right-screen" in cockpit
    assert "orionv-mfd-right-buttons" in cockpit
    assert "orionv-mfd-qiki" in cockpit

    assert "mfd_button_specs(\"left\")" in cockpit
    assert "mfd_button_specs(\"right\")" in cockpit
    assert 'mfd_page_label("right", page)' in cockpit
    assert 'mfd_page_label("left", page)' in cockpit
    assert "page={page}" in cockpit

    # App-level quick-jump buttons remain present for existing routing tests.
    assert "orionv-cockpit-jump-power" in cockpit
    assert "orionv-cockpit-jump-docking" in cockpit
    assert "orionv-cockpit-qiki-confirm" in cockpit


def test_f2_systems_uses_mfd_panes_instead_of_flattened_seed_scroll() -> None:
    systems = (SCREENS / "systems.py").read_text()

    assert "orionv-systems-mfd-root" in systems
    assert "orionv-systems-mfd-left-screen" in systems
    assert "orionv-systems-mfd-right-screen" in systems
    assert "orionv-systems-mfd-softkeys" in systems
    assert "render_left_mfd_page(" in systems
    assert "render_right_mfd_page(" in systems
    assert "active_right_page" in systems
    assert "orionv-systems-compat" in systems
    assert "display: none" in systems

    # Existing dashboards remain mounted only as compatibility/data anchors.
    assert 'id="orionv-body-structure-dashboard"' in systems
    assert 'id="orionv-body-physics-panel"' in systems
    assert 'id="orionv-power-thermal-dashboard"' in systems
    assert "Power / Charge" in systems
    assert "Power / Charge (telemetry source)" not in systems


def test_f8_evidence_restores_list_detail_mfd_split() -> None:
    evidence = (SCREENS / "evidence_stream.py").read_text()

    assert "orionv-evidence-mfd-root" in evidence
    assert "orionv-evidence-mfd-left-screen" in evidence
    assert "orionv-evidence-mfd-right-screen" in evidence
    assert "ЛЕВЫЙ MFD / СПИСОК УЛИК" in evidence
    assert "ПРАВЫЙ MFD / ДЕТАЛИ УЛИКИ" in evidence
    assert "панель улик не исполняет команды" in evidence
    assert "orionv-evidence-stream" in evidence
    assert "display: none" in evidence


def test_mfd_restore_patch_does_not_add_forbidden_runtime_claims() -> None:
    changed_text = "\n".join(
        [
            (ORION_V / "mfd_layout.py").read_text(),
            (SCREENS / "cockpit.py").read_text(),
            (SCREENS / "systems.py").read_text(),
            (SCREENS / "evidence_stream.py").read_text(),
        ]
    ).lower()

    forbidden = (
        "c1 minor",
        "i1 light-module",
        "body_physical_consequence_evaluated",
        "full qiki body runtime conformance: claimed",
        "pdu runtime implemented",
        "thermal simulation implemented",
        "proto changes",
        "nats changes",
        "grpc changes",
    )
    for fragment in forbidden:
        assert fragment not in changed_text
