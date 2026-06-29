from __future__ import annotations

from pathlib import Path

from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    BODY_STRUCTURE_TEST_MODULE_ID,
    reset_body_structure_interactive_state,
    run_body_structure_interactive_self_check,
    select_next_body_structure_face,
)
from qiki.services.operator_console.orion_v.body_structure_view_model import (
    build_body_structure_evidence_card_vms,
    format_body_structure_cockpit_line,
    format_body_structure_system_summary,
    get_body_structure_console_view_model,
)
from qiki.services.operator_console.orion_v.evidence_card_vm import render_card_text

REPO_ROOT = Path(__file__).resolve().parents[2]
ORION_V = REPO_ROOT / "src/qiki/services/operator_console/orion_v"


def test_face_map_initial_state_shows_12_free_faces() -> None:
    reset_body_structure_interactive_state()
    vm = get_body_structure_console_view_model()
    text = format_body_structure_system_summary(vm)

    assert vm.faces_total == 12
    assert vm.faces_range == "F00-F11"
    assert len(vm.faces) == 12
    assert vm.selected_face_id == "F06"
    assert vm.selected_face_role == "mission"
    assert vm.selected_face_occupancy == "free"
    assert vm.attached_modules_count == 0
    assert "Face Map" in text
    for face_id in [f"F{i:02d}" for i in range(12)]:
        assert face_id in text
    assert "F06" in text
    assert "mission" in text
    assert "Selected face" in text


def test_face_map_after_attach_marks_f06_occupied() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    vm = get_body_structure_console_view_model()
    f2 = format_body_structure_system_summary(vm)

    face_f06 = next(face for face in vm.faces if face.face_id == "F06")
    assert face_f06.occupancy == "occupied"
    assert face_f06.module_id == BODY_STRUCTURE_TEST_MODULE_ID
    assert vm.selected_face_id == "F06"
    assert vm.selected_face_occupancy == "occupied"
    assert vm.selected_face_module_id == BODY_STRUCTURE_TEST_MODULE_ID
    assert "F06 mission" in f2
    assert "OCCUPIED" in f2
    assert BODY_STRUCTURE_TEST_MODULE_ID in f2


def test_selected_face_navigation_cycles_faces_without_changing_attach_target() -> None:
    reset_body_structure_interactive_state()
    vm0 = get_body_structure_console_view_model()
    assert vm0.selected_face_id == "F06"

    select_next_body_structure_face()
    vm1 = get_body_structure_console_view_model()
    select_next_body_structure_face()
    vm2 = get_body_structure_console_view_model()

    assert vm1.selected_face_id == "F07"
    assert vm2.selected_face_id == "F08"

    run_body_structure_interactive_self_check()
    vm_after = get_body_structure_console_view_model()
    assert vm_after.mount_point == "F06"
    assert vm_after.selected_face_id == "F08"
    face_f06 = next(face for face in vm_after.faces if face.face_id == "F06")
    assert face_f06.occupancy == "occupied"


def test_f1_cockpit_includes_face_count_and_selected_face() -> None:
    reset_body_structure_interactive_state()
    line = format_body_structure_cockpit_line()

    assert "BODY STRUCTURE" in line
    assert "faces=12" in line
    assert "modules=0" in line
    assert "selected=F06" in line


def test_f2_systems_renders_face_map_and_selected_face() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    text = format_body_structure_system_summary()

    assert "Face Map" in text
    assert "Selected face" in text
    assert "face_id         F06" in text
    assert "role            mission" in text
    assert "occupancy       occupied" in text
    assert "module          test_sensor_module_001" in text


def test_f8_evidence_includes_face_id_and_face_state() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    body_text = "\n".join(render_card_text(card) for card in build_body_structure_evidence_card_vms())

    assert "BODY_MODULE_ATTACH_REGISTERED" in body_text
    assert "face: F06" in body_text
    assert "face_state: occupied" in body_text
    assert "source: audit" in body_text
    assert "read_only: true" in body_text


def test_orion_app_has_face_map_hotkey_and_action() -> None:
    app = (ORION_V / "app.py").read_text()

    assert "BODY face" in app
    assert "action_select_next_body_structure_face" in app
    assert "select_next_body_structure_face" in app
