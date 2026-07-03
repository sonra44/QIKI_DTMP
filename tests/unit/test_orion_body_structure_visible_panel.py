from __future__ import annotations

from pathlib import Path

from qiki.services.operator_console.orion_v.body_structure_view_model import (
    BODY_STRUCTURE_MODE,
    BODY_STRUCTURE_SOURCE,
    BODY_STRUCTURE_TRANSPORT,
    build_body_structure_evidence_card_vms,
    build_body_structure_self_check_view_model,
    format_body_structure_cockpit_line,
    format_body_structure_system_summary,
)
from qiki.services.operator_console.orion_v.evidence_card_vm import render_card_text


REPO_ROOT = Path(__file__).resolve().parents[2]
ORION_V = REPO_ROOT / "src/qiki/services/operator_console/orion_v"


def test_body_structure_view_model_shows_attached_module() -> None:
    vm = build_body_structure_self_check_view_model()

    assert vm.seed_status == "online"
    assert vm.mode == BODY_STRUCTURE_MODE
    assert vm.transport == BODY_STRUCTURE_TRANSPORT
    assert vm.source == BODY_STRUCTURE_SOURCE
    assert vm.faces_total == 12
    assert vm.faces_range == "F00-F11"
    assert vm.attached_modules_count == 1
    assert vm.last_decision == "attached"
    assert vm.last_stage == "registration"
    assert vm.module_id == "test_sensor_module_001"
    assert vm.mount_point == "F06"
    assert vm.passport_status == "validated"
    assert vm.runtime_ready is False
    assert vm.capability_status == "inactive"
    assert vm.trust_status == "audit_backed"
    assert vm.audit_event_id
    assert vm.evidence_card_id
    assert vm.evidence_card_type == "BODY_MODULE_ATTACH_REGISTERED"
    assert vm.read_only is True


def test_f1_cockpit_body_status_line_is_visible() -> None:
    line = format_body_structure_cockpit_line(build_body_structure_self_check_view_model())

    assert "BODY STRUCTURE | online" in line
    assert "modules=1 @ F06" in line  # dedup: no more repeated "BODY online: 1 module" tail
    assert "ready=false" in line
    assert "audit_backed" in line


def test_f2_systems_body_structure_summary_has_operator_fields() -> None:
    text = format_body_structure_system_summary(build_body_structure_self_check_view_model())

    assert "Body / Structure / Modules" in text
    assert "Seed status       online" in text
    assert "Faces             F00-F11 (12)" in text
    assert "Module            test_sensor_module_001" in text
    assert "Mount             F06" in text
    assert "Runtime ready     false" in text
    assert "Capability        inactive" in text
    assert "Source            body_structure.runtime_seed" in text
    assert "Trust             audit_backed" in text
    assert "Evidence          card:" in text


def test_f8_evidence_contains_body_attach_registered_card() -> None:
    body_vms = build_body_structure_evidence_card_vms(build_body_structure_self_check_view_model())
    body_text = "\n".join(render_card_text(vm) for vm in body_vms)

    assert "BODY" in body_text
    assert "модуль test_sensor_module_001 установлен @ F06" in body_text
    assert "BODY_MODULE_ATTACH_REGISTERED" in body_text
    assert "источник: audit" in body_text
    assert "доверие: trusted" in body_text
    assert "только чтение: true" in body_text
    assert "готов к работе: false" in body_text


def test_orion_screen_modules_are_wired_to_body_structure_view_model() -> None:
    cockpit = (ORION_V / "screens/cockpit.py").read_text()
    systems = (ORION_V / "screens/systems.py").read_text()
    evidence = (ORION_V / "screens/evidence_stream.py").read_text()

    assert "format_body_structure_cockpit_line" in cockpit
    assert "body_structure_line" in cockpit
    assert "body_structure" in systems
    assert "Body / Structure / Modules" in systems
    assert "_build_body_structure_card" in systems
    assert "build_body_structure_evidence_card_vms" in evidence
    assert "build_evidence_card_vms" in evidence
