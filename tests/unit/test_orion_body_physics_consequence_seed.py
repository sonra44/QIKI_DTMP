from __future__ import annotations

from pathlib import Path

from qiki.services.operator_console.orion_v.body_physics_view_model import (
    BODY_PHYSICS_CARD_TYPE,
    BODY_PHYSICS_RUNTIME_CONFORMANCE,
    BODY_PHYSICS_SOURCE,
    BODY_PHYSICS_TRANSPORT,
    BODY_PHYSICS_TRUST,
    build_body_physics_evidence_card_vms,
    format_body_physics_cockpit_line,
    format_body_physics_system_summary,
    get_body_physics_console_view_model,
)
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    BODY_STRUCTURE_TEST_MODULE_ID,
    BODY_STRUCTURE_TEST_MOUNT,
    reset_body_structure_interactive_state,
    run_body_structure_interactive_self_check,
)
from qiki.services.operator_console.orion_v.evidence_card_vm import render_card_text

REPO_ROOT = Path(__file__).resolve().parents[2]
ORION_V = REPO_ROOT / "src/qiki/services/operator_console/orion_v"
SCREENS = ORION_V / "screens"
WIDGETS = ORION_V / "widgets"


def _visible_text() -> str:
    return "\n".join(
        [
            format_body_physics_cockpit_line(),
            format_body_physics_system_summary(),
            "\n".join(render_card_text(card) for card in build_body_physics_evidence_card_vms()),
        ]
    )


def test_body_physics_seed_initial_state_has_no_module_impact() -> None:
    reset_body_structure_interactive_state()
    vm = get_body_physics_console_view_model()

    assert vm.module_attached is False
    assert vm.mass_changed is False
    assert vm.mass_state == "unchanged"
    assert vm.module_mass_status == "none"
    assert vm.com_delta_class == "unknown / waiting for attach"
    assert vm.inertia_class == "unknown / waiting for attach"
    assert vm.trust_status == "missing"
    assert vm.thrust_map_status == "TBD"
    assert vm.torque_map_status == "TBD"
    assert vm.source == BODY_PHYSICS_SOURCE
    assert vm.transport == BODY_PHYSICS_TRANSPORT
    assert vm.runtime_conformance == BODY_PHYSICS_RUNTIME_CONFORMANCE

    visible = _visible_text()
    assert "BODY PHYSICS(seed)" in visible
    assert "waiting" in visible
    assert "mass=unchanged" in visible
    assert "CoM=unknown / waiting for attach" in visible
    assert "inertia=unknown / waiting for attach" in visible
    assert "Body / Physical Consequences" in visible
    assert "Mass state         unchanged" in visible
    assert "Thrust Map         TBD" in visible
    assert "Torque Map         TBD" in visible
    assert "Физических последствий пока нет" in visible
    assert "runtime_conformance: not claimed" in visible


def test_body_physics_seed_after_attach_marks_pending_not_calculated() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    vm = get_body_physics_console_view_model()

    assert vm.module_attached is True
    assert vm.module_id == BODY_STRUCTURE_TEST_MODULE_ID
    assert vm.mount_point == BODY_STRUCTURE_TEST_MOUNT
    assert vm.mass_changed is False
    assert vm.mass_state == "pending; requires mass + geometry"
    assert vm.module_mass_status == "test_fixture only / not canon"
    assert vm.com_delta_class == "unknown / requires mass + geometry"
    assert vm.inertia_class == "unknown / requires inertia model"
    assert "aggressive burn not unlocked" in vm.blocked_maneuvers
    assert "BODY_PHYSICS_SEED_ONLY" in vm.reason_codes
    assert "MASS_MODEL_MISSING" in vm.reason_codes
    assert "COM_CALCULATION_REQUIRED" in vm.reason_codes
    assert "INERTIA_MODEL_MISSING" in vm.reason_codes
    assert "THRUST_MAP_TBD" in vm.reason_codes
    assert "TORQUE_MAP_TBD" in vm.reason_codes
    assert vm.evidence_card_type == BODY_PHYSICS_CARD_TYPE
    assert vm.trust_status == BODY_PHYSICS_TRUST
    assert vm.read_only is True
    assert vm.runtime_conformance == "not claimed"


def test_body_physics_seed_does_not_claim_known_com_inertia_or_canon_trust() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    visible = _visible_text()

    assert "BODY_PHYSICAL_CONSEQUENCE_SEED_PENDING" in visible
    assert "CoM=unknown / requires mass + geometry" in visible
    assert "inertia=unknown / requires inertia model" in visible
    assert "trust: seed_only" in visible
    assert "runtime_conformance: not claimed" in visible
    assert "thrust_map=TBD" in visible
    assert "torque_map=TBD" in visible
    assert "Thrust Map         TBD" in visible
    assert "Torque Map         TBD" in visible

    forbidden_fragments = (
        "C1 " + "minor",
        "I1 light-" + "module",
        "trust: seed_" + "backed",
        "BODY_PHYSICAL_CONSEQUENCE_" + "EVALUATED",
        "calculated center of mass",
        "real inertia tensor",
        "full qiki body runtime",
        "runtime_conformance: claimed",
    )
    lowered = visible.lower()
    for fragment in forbidden_fragments:
        assert fragment.lower() not in lowered


def test_f8_evidence_contains_pending_body_physical_consequence_card() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    cards = build_body_physics_evidence_card_vms()
    text = "\n".join(render_card_text(card) for card in cards)

    assert "ФИЗИКА КОРПУСА" in text
    assert "BODY_PHYSICAL_CONSEQUENCE_SEED_PENDING" in text
    assert f"module: {BODY_STRUCTURE_TEST_MODULE_ID}" in text
    assert "mount: F06" in text
    assert "mass_status: test_fixture only / not canon" in text
    assert "CoM_delta_class: unknown / requires mass + geometry" in text
    assert "inertia_class: unknown / requires inertia model" in text
    assert "source: local_body_physics_seed" in text
    assert "trust: seed_only" in text
    assert "read_only: true" in text
    assert "runtime_conformance: not claimed" in text


def test_reset_clears_body_physics_seed() -> None:
    reset_body_structure_interactive_state()
    run_body_structure_interactive_self_check()
    assert get_body_physics_console_view_model().module_attached is True

    reset_body_structure_interactive_state()
    vm = get_body_physics_console_view_model()

    assert vm.module_attached is False
    assert vm.mass_changed is False
    assert vm.com_delta_class == "unknown / waiting for attach"
    assert vm.inertia_class == "unknown / waiting for attach"
    assert "waiting" in format_body_physics_cockpit_line(vm)


def test_orion_f1_f2_f8_files_mount_body_physics_seed_without_touching_power_charge_title() -> None:
    cockpit = (SCREENS / "cockpit.py").read_text()
    systems = (SCREENS / "systems.py").read_text()
    evidence = (SCREENS / "evidence_stream.py").read_text()
    widget = (WIDGETS / "body_physics_panel.py").read_text()

    assert "format_body_physics_cockpit_line" in cockpit
    assert "body_physics_line" in cockpit
    assert "BodyPhysicsPanel" in systems
    assert 'id="orionv-body-physics-panel"' in systems
    assert "BodyPhysicsPanel" in systems
    assert "Питание / Заряд" in systems
    assert "build_body_physics_evidence_card_vms" in evidence
    assert "class BodyPhysicsPanel(Static)" in widget
