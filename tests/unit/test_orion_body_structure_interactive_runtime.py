from __future__ import annotations

from pathlib import Path

from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    BODY_STRUCTURE_TEST_MODULE_ID,
    BODY_STRUCTURE_TEST_MOUNT,
    reset_body_structure_interactive_state,
    run_body_structure_interactive_self_check,
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


def test_initial_body_structure_interactive_state_is_waiting() -> None:
    reset_body_structure_interactive_state()
    vm = get_body_structure_console_view_model()

    assert vm.seed_status == "online"
    assert vm.last_decision == "waiting"
    assert vm.attached_modules_count == 0
    assert vm.after_mount_state == "free"
    assert vm.can_run is True
    assert vm.can_reset is False

    f1 = format_body_structure_cockpit_line(vm)
    f2 = format_body_structure_system_summary(vm)
    f8 = "\n".join(render_card_text(card) for card in build_body_structure_evidence_card_vms(vm))

    assert "BODY STRUCTURE" in f1
    assert "modules=0" in f1
    assert "F06=free" in f1
    assert "press B" in f1
    assert "Attached modules  0" in f2
    assert "Evidence          none yet" in f2
    assert "No body attach evidence yet" in f8


def test_press_b_runs_attach_pipeline_and_updates_f1_f2_f8() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    vm = get_body_structure_console_view_model()

    assert vm.last_decision == "attached"
    assert vm.last_stage == "registration"
    assert vm.before_modules_count == 0
    assert vm.after_modules_count == 1
    assert vm.before_mount_state == "free"
    assert vm.after_mount_state == BODY_STRUCTURE_TEST_MODULE_ID
    assert vm.attached_modules_count == 1
    assert vm.module_id == BODY_STRUCTURE_TEST_MODULE_ID
    assert vm.mount_point == BODY_STRUCTURE_TEST_MOUNT
    assert vm.passport_status == "validated"
    assert vm.runtime_ready is False
    assert vm.capability_status == "inactive"
    assert vm.audit_event_id
    assert vm.evidence_card_id

    f1 = format_body_structure_cockpit_line(vm)
    f2 = format_body_structure_system_summary(vm)
    f8 = "\n".join(render_card_text(card) for card in build_body_structure_evidence_card_vms(vm))

    assert "attached @ F06" in f1
    assert "modules=1" in f1
    assert "Before" in f2
    assert "After" in f2
    assert "modules         0" in f2
    assert "modules         1" in f2
    assert BODY_STRUCTURE_TEST_MODULE_ID in f2
    assert "runtime_ready   false" in f2
    assert "BODY_MODULE_ATTACH_REGISTERED" in f8
    assert "source: audit" in f8
    assert "read_only: true" in f8


def test_reset_returns_body_structure_to_waiting_state() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    reset_body_structure_interactive_state()
    vm = get_body_structure_console_view_model()

    assert vm.last_decision == "waiting"
    assert vm.attached_modules_count == 0
    assert vm.after_mount_state == "free"
    assert vm.evidence_card is None
    assert vm.audit_event_id == ""
    assert vm.last_action == "reset"
    assert "modules=0" in format_body_structure_cockpit_line(vm)


def test_repeated_b_does_not_turn_positive_loop_into_rejection_focus() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    run_body_structure_interactive_self_check()
    vm = get_body_structure_console_view_model()

    assert vm.interaction_state == "already_attached"
    assert vm.attached_modules_count == 1
    assert vm.can_run is False
    assert vm.can_reset is True
    assert "press R to reset" in format_body_structure_cockpit_line(vm)


def test_interactive_body_structure_does_not_claim_runtime_ready_or_active_module() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    vm = get_body_structure_console_view_model()
    visible_text = "\n".join(
        [
            format_body_structure_cockpit_line(vm),
            format_body_structure_system_summary(vm),
            "\n".join(render_card_text(card) for card in build_body_structure_evidence_card_vms(vm)),
        ]
    )

    assert "runtime_ready   false" in visible_text
    assert "capability      inactive" in visible_text
    lowered = visible_text.lower()
    assert "powered" not in lowered
    assert "thermal cleared" not in lowered
    assert "module active" not in lowered


def test_orion_app_has_body_structure_hotkeys_and_actions() -> None:
    app = (ORION_V / "app.py").read_text()
    assert "BODY attach" in app
    assert "BODY reset" in app
    assert "action_run_body_structure_self_check" in app
    assert "action_reset_body_structure_self_check" in app
    assert "run_body_structure_interactive_self_check" in app
    assert "reset_body_structure_interactive_state" in app
