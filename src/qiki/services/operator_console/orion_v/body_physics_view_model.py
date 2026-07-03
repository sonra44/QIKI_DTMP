"""Visible mass / CoM / inertia *pending* seed for ORION V.

This module deliberately avoids calculating or claiming real body physics. It
only shows the next honest consequence after the visible body-structure attach
loop: once a module is attached, physical integration is still pending until a
real mass model, body-frame geometry, CoM calculation, inertia model, Thrust Map,
and Torque Map exist.

Boundary:
    attached != physically integrated
    physical consequence seed != calculated physics
    seed_only != canon-trusted runtime evidence

The view model is local, deterministic, read-only, and explicitly marked as a
seed. It gives the operator a visible gap to work against without claiming full
QIKI Body runtime conformance.
"""

from __future__ import annotations

from dataclasses import dataclass

from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    BODY_STRUCTURE_TEST_MOUNT,
)
from qiki.services.operator_console.orion_v.body_structure_view_model import (
    BodyStructureConsoleViewModel,
    get_body_structure_console_view_model,
)
from qiki.services.operator_console.orion_v.evidence_card_vm import EvidenceCardVM

BODY_PHYSICS_MODE = "console-visible mass/CoM/inertia pending seed"
BODY_PHYSICS_SOURCE = "local_body_physics_seed"
BODY_PHYSICS_TRANSPORT = "direct in-process adapter"
BODY_PHYSICS_TRUST = "seed_only"
BODY_PHYSICS_CARD_TYPE = "BODY_PHYSICAL_CONSEQUENCE_SEED_PENDING"
BODY_PHYSICS_WAITING_CARD_TYPE = "BODY_PHYSICAL_CONSEQUENCE_WAITING"
BODY_PHYSICS_RUNTIME_CONFORMANCE = "not claimed"
BODY_PHYSICS_BASE_MASS_STATUS = "TBD"
BODY_PHYSICS_MODULE_MASS_STATUS = "test_fixture only / not canon"
BODY_PHYSICS_MASS_WAITING = "unchanged"
BODY_PHYSICS_MASS_PENDING = "pending; requires mass + geometry"
BODY_PHYSICS_COM_WAITING = "unknown / waiting for attach"
BODY_PHYSICS_COM_PENDING = "unknown / requires mass + geometry"
BODY_PHYSICS_INERTIA_WAITING = "unknown / waiting for attach"
BODY_PHYSICS_INERTIA_PENDING = "unknown / requires inertia model"
BODY_PHYSICS_THRUST_MAP_STATUS = "TBD"
BODY_PHYSICS_TORQUE_MAP_STATUS = "TBD"


@dataclass(frozen=True, slots=True)
class BodyPhysicsConsoleViewModel:
    mode: str
    source: str
    transport: str
    trust_status: str
    evidence_card_type: str
    evidence_card_id: str
    read_only: bool
    runtime_conformance: str
    module_attached: bool
    module_id: str
    mount_point: str
    base_body_mass_status: str
    module_mass_status: str
    mass_state: str
    mass_changed: bool
    com_delta_class: str
    inertia_class: str
    maneuver_impact: str
    blocked_maneuvers: tuple[str, ...]
    thrust_map_status: str
    torque_map_status: str
    operator_summary: str
    reason_codes: tuple[str, ...]


def get_body_physics_console_view_model(
    body_vm: BodyStructureConsoleViewModel | None = None,
) -> BodyPhysicsConsoleViewModel:
    """Build the visible body-physics pending seed from Body Structure state."""
    return build_body_physics_console_view_model(body_vm or get_body_structure_console_view_model())


def build_body_physics_console_view_model(
    body_vm: BodyStructureConsoleViewModel,
) -> BodyPhysicsConsoleViewModel:
    """Return deterministic pending physics status for the attach seed.

    The positive state recognizes only that a module is attached in the local
    body-structure self-check. It does not promote fixture mass, CoM, or inertia
    to calculated truth. Later runtime patches can replace this pending seed with
    real mass/CoM/inertia evaluation while preserving the F1/F2/F8 surface.
    """
    module_attached = bool(
        body_vm.attached_modules_count > 0
        and (body_vm.last_decision == "attached" or body_vm.interaction_state == "already_attached")
    )
    if not module_attached:
        return _waiting_vm(body_vm)
    return _pending_vm(body_vm)


def format_body_physics_cockpit_line(vm: BodyPhysicsConsoleViewModel | None = None) -> str:
    """Compact F1 line for visible body-physics pending consequences."""
    vm = vm or get_body_physics_console_view_model()
    if not vm.module_attached:
        return (
            "BODY PHYSICS(seed) | waiting | mass=unchanged | "
            f"CoM={vm.com_delta_class} | inertia={vm.inertia_class} | press B"
        )
    return (
        "BODY PHYSICS(seed) | mass=pending | "
        f"CoM={vm.com_delta_class} | inertia={vm.inertia_class} | "
        f"thrust_map={vm.thrust_map_status} | torque_map={vm.torque_map_status}"
    )


def format_body_physics_system_summary(vm: BodyPhysicsConsoleViewModel | None = None) -> str:
    """F2 summary for the physical consequence pending seed."""
    vm = vm or get_body_physics_console_view_model()
    blocked = ", ".join(vm.blocked_maneuvers) if vm.blocked_maneuvers else "none"
    reasons = ", ".join(vm.reason_codes) if vm.reason_codes else "none"
    return "\n".join(
        [
            "Body / Physical Consequences",
            f"Source             {vm.source}",
            f"Transport          {vm.transport}",
            f"Trust              {vm.trust_status}",
            f"Runtime            {vm.runtime_conformance}",
            f"Base body mass     {vm.base_body_mass_status}",
            f"Module             {vm.module_id or 'none'}",
            f"Module mass        {vm.module_mass_status}",
            f"Mounted at         {vm.mount_point}",
            f"Mass state         {vm.mass_state}",
            f"CoM delta          {vm.com_delta_class}",
            f"Inertia class      {vm.inertia_class}",
            f"Maneuver impact    {vm.maneuver_impact}",
            f"Blocked maneuvers  {blocked}",
            f"Thrust Map         {vm.thrust_map_status}",
            f"Torque Map         {vm.torque_map_status}",
            f"Reason codes       {reasons}",
            f"Evidence           {vm.evidence_card_type} / {vm.evidence_card_id}",
        ]
    )


def build_body_physics_evidence_card_vms(
    vm: BodyPhysicsConsoleViewModel | None = None,
) -> list[EvidenceCardVM]:
    """Return read-only F8 evidence VMs for the body-physics pending seed."""
    vm = vm or get_body_physics_console_view_model()
    if not vm.module_attached:
        return [
            EvidenceCardVM(
                subsystem="ФИЗИКА КОРПУСА",
                state_key="missing",
                headline="Физических последствий пока нет. Нажмите B — проверка корпуса.",
                reason_text="BODY_PHYSICS_WAITING",
                detail_lines=(
                    f"source: {vm.source}",
                    f"transport: {vm.transport}",
                    "trust: missing",
                    f"runtime_conformance: {vm.runtime_conformance}",
                    f"thrust_map: {vm.thrust_map_status}",
                    f"torque_map: {vm.torque_map_status}",
                ),
            )
        ]
    return [
        EvidenceCardVM(
            subsystem="ФИЗИКА КОРПУСА",
            state_key="target",
            headline=(
                f"{vm.evidence_card_type} | module={vm.module_id} | "
                f"CoM={vm.com_delta_class} | inertia={vm.inertia_class}"
            ),
            reason_text=", ".join(vm.reason_codes),
            detail_lines=(
                f"module: {vm.module_id}",
                f"mount: {vm.mount_point}",
                f"mass_status: {vm.module_mass_status}",
                f"mass_state: {vm.mass_state}",
                f"CoM_delta_class: {vm.com_delta_class}",
                f"inertia_class: {vm.inertia_class}",
                f"maneuver_impact: {vm.maneuver_impact}",
                f"blocked_maneuvers: {', '.join(vm.blocked_maneuvers) if vm.blocked_maneuvers else 'none'}",
                f"thrust_map: {vm.thrust_map_status}",
                f"torque_map: {vm.torque_map_status}",
                f"source: {vm.source}",
                f"transport: {vm.transport}",
                f"trust: {vm.trust_status}",
                f"read_only: {str(vm.read_only).lower()}",
                f"runtime_conformance: {vm.runtime_conformance}",
                f"evidence_card_id: {vm.evidence_card_id}",
            ),
        )
    ]


def _waiting_vm(body_vm: BodyStructureConsoleViewModel) -> BodyPhysicsConsoleViewModel:
    return BodyPhysicsConsoleViewModel(
        mode=BODY_PHYSICS_MODE,
        source=BODY_PHYSICS_SOURCE,
        transport=BODY_PHYSICS_TRANSPORT,
        trust_status="missing",
        evidence_card_type=BODY_PHYSICS_WAITING_CARD_TYPE,
        evidence_card_id="body-physics-seed:waiting",
        read_only=True,
        runtime_conformance=BODY_PHYSICS_RUNTIME_CONFORMANCE,
        module_attached=False,
        module_id="",
        mount_point=body_vm.selected_face_id or BODY_STRUCTURE_TEST_MOUNT,
        base_body_mass_status=BODY_PHYSICS_BASE_MASS_STATUS,
        module_mass_status="none",
        mass_state=BODY_PHYSICS_MASS_WAITING,
        mass_changed=False,
        com_delta_class=BODY_PHYSICS_COM_WAITING,
        inertia_class=BODY_PHYSICS_INERTIA_WAITING,
        maneuver_impact="none; waiting for attach self-check",
        blocked_maneuvers=(),
        thrust_map_status=BODY_PHYSICS_THRUST_MAP_STATUS,
        torque_map_status=BODY_PHYSICS_TORQUE_MAP_STATUS,
        operator_summary="No attached module physical consequence yet; press B to run body attach self-check.",
        reason_codes=("BODY_PHYSICS_WAITING",),
    )


def _pending_vm(body_vm: BodyStructureConsoleViewModel) -> BodyPhysicsConsoleViewModel:
    module_id = body_vm.module_id or (body_vm.modules[0].module_id if body_vm.modules else "unknown_module")
    mount_point = body_vm.mount_point or (
        body_vm.modules[0].mount_point if body_vm.modules else BODY_STRUCTURE_TEST_MOUNT
    )
    return BodyPhysicsConsoleViewModel(
        mode=BODY_PHYSICS_MODE,
        source=BODY_PHYSICS_SOURCE,
        transport=BODY_PHYSICS_TRANSPORT,
        trust_status=BODY_PHYSICS_TRUST,
        evidence_card_type=BODY_PHYSICS_CARD_TYPE,
        evidence_card_id=f"body-physics-seed-pending:{module_id}:{mount_point}",
        read_only=True,
        runtime_conformance=BODY_PHYSICS_RUNTIME_CONFORMANCE,
        module_attached=True,
        module_id=module_id,
        mount_point=mount_point,
        base_body_mass_status=BODY_PHYSICS_BASE_MASS_STATUS,
        module_mass_status=BODY_PHYSICS_MODULE_MASS_STATUS,
        mass_state=BODY_PHYSICS_MASS_PENDING,
        mass_changed=False,
        com_delta_class=BODY_PHYSICS_COM_PENDING,
        inertia_class=BODY_PHYSICS_INERTIA_PENDING,
        maneuver_impact=(
            "pending; do not unlock aggressive burn until real mass/CoM/inertia and "
            "Thrust/Torque maps exist"
        ),
        blocked_maneuvers=("aggressive burn not unlocked",),
        thrust_map_status=BODY_PHYSICS_THRUST_MAP_STATUS,
        torque_map_status=BODY_PHYSICS_TORQUE_MAP_STATUS,
        operator_summary=(
            f"{module_id} attached at {mount_point}; physical consequence remains pending "
            "until mass, geometry, CoM, inertia, Thrust Map and Torque Map are calculated."
        ),
        reason_codes=(
            "BODY_PHYSICS_SEED_ONLY",
            "MASS_MODEL_MISSING",
            "COM_CALCULATION_REQUIRED",
            "INERTIA_MODEL_MISSING",
            "THRUST_MAP_TBD",
            "TORQUE_MAP_TBD",
        ),
    )


__all__ = [
    "BODY_PHYSICS_CARD_TYPE",
    "BODY_PHYSICS_SOURCE",
    "BODY_PHYSICS_TRANSPORT",
    "BODY_PHYSICS_TRUST",
    "BODY_PHYSICS_RUNTIME_CONFORMANCE",
    "BodyPhysicsConsoleViewModel",
    "build_body_physics_console_view_model",
    "build_body_physics_evidence_card_vms",
    "format_body_physics_cockpit_line",
    "format_body_physics_system_summary",
    "get_body_physics_console_view_model",
]
