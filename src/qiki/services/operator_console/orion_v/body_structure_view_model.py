"""Visible ORION view-model for the QIKI Body Structure attach seed.

This is the deliberately visible operator-console bridge for the already
unit-verified body_structure attach lifecycle seed. It does not implement PDU,
thermal clearance, bayonet bridge, capability activation, module catalog, or
transport telemetry.

Default ORION screens now use an interactive local runtime seed:

    B -> run the real ``run_attach_pipeline`` path
    R -> reset to the pre-action state
    N -> select next Face Map entry for inspection

The data remains explicitly marked as local/direct so it is visible without
pretending NATS/gRPC flight telemetry already exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    ModuleAttachRequest,
    ModulePassport,
    run_attach_pipeline,
)
from qiki.services.q_core_agent.core.event_store import EventStore, SystemEvent
from qiki.services.operator_console.orion_v.body_structure_face_map import (
    BodyStructureFaceView,
    build_face_views,
    default_selected_face_id,
    format_face_map_lines,
    selected_face_view,
)
from qiki.services.operator_console.orion_v.body_structure_interactive_controller import (
    BODY_STRUCTURE_INTERACTIVE_MODE,
    BODY_STRUCTURE_INTERACTIVE_SOURCE,
    BODY_STRUCTURE_INTERACTIVE_TRANSPORT,
    BODY_STRUCTURE_INTERACTIVE_TRUST,
    BODY_STRUCTURE_TEST_MOUNT,
    BodyStructureInteractiveSnapshot,
    get_body_structure_interactive_snapshot,
)
from qiki.services.operator_console.orion_v.evidence_card import EvidenceCard, evidence_card_from_audit_event
from qiki.services.operator_console.orion_v.evidence_card_vm import EvidenceCardVM

BODY_STRUCTURE_SOURCE = BODY_STRUCTURE_INTERACTIVE_SOURCE
BODY_STRUCTURE_MODE = BODY_STRUCTURE_INTERACTIVE_MODE
BODY_STRUCTURE_TRANSPORT = BODY_STRUCTURE_INTERACTIVE_TRANSPORT
BODY_STRUCTURE_TRUST = BODY_STRUCTURE_INTERACTIVE_TRUST


@dataclass(frozen=True, slots=True)
class BodyStructureModuleRow:
    module_id: str
    mount_point: str
    status: str
    passport_status: str
    capability_status: str
    runtime_ready: bool


@dataclass(frozen=True, slots=True)
class BodyStructureConsoleViewModel:
    seed_status: str
    mode: str
    transport: str
    source: str
    trust_status: str
    faces_total: int
    faces_range: str
    attached_modules_count: int
    modules: tuple[BodyStructureModuleRow, ...]
    last_decision: str
    last_stage: str
    last_reason_code: str
    module_id: str
    mount_point: str
    passport_status: str
    runtime_ready: bool
    capability_status: str
    audit_event_id: str
    evidence_card_id: str
    evidence_card_type: str
    read_only: bool
    operator_summary: str
    evidence_card: EvidenceCard | None = None
    interaction_state: str = "attached"
    last_action: str = "self_check"
    before_modules_count: int = 0
    after_modules_count: int = 0
    before_mount_state: str = "unknown"
    after_mount_state: str = "unknown"
    can_run: bool = False
    can_reset: bool = True
    operator_hint: str = "press R to reset"
    selected_face_id: str = BODY_STRUCTURE_TEST_MOUNT
    selected_face_role: str = "mission"
    selected_face_occupancy: str = "unknown"
    selected_face_module_id: str = ""
    faces: tuple[BodyStructureFaceView, ...] = ()


# ---------------------------------------------------------------------------
# Stateless helper kept for legacy tests and direct smoke checks. It immediately
# runs one positive attach. Screens should use get_body_structure_console_view_model().


def build_body_structure_self_check_view_model() -> BodyStructureConsoleViewModel:
    """Run the real attach lifecycle once and return a display-ready snapshot.

    This is not fake flight telemetry. The transport is explicitly marked as a
    local in-process self-check, but the data comes from the real attach pipeline,
    the shared EventStore audit event, and the ORION Evidence Card projection.
    """
    store = EventStore(backend="memory")
    body = BodyConfigSnapshot.skeleton()
    request = ModuleAttachRequest(
        request_id="orion-visible-body-self-check",
        module_id="test_sensor_module_001",
        mount_point=BODY_STRUCTURE_TEST_MOUNT,
        passport=ModulePassport(
            module_id="test_sensor_module_001",
            module_class="sensor",
            mount_point=BODY_STRUCTURE_TEST_MOUNT,
            provided_capabilities=("basic_sensor_read",),
        ),
    )
    decision, updated_body = run_attach_pipeline(body, request, store=store)
    audit_event = _find_audit_event(store, decision.audit_event_id)
    card = evidence_card_from_audit_event(audit_event) if audit_event is not None else None
    return _build_view_model(
        body=updated_body,
        decision=decision,
        card=card,
        interaction_state=decision.status,
        last_action="attach_self_check",
        before_modules_count=0,
        after_modules_count=len(updated_body.modules),
        before_mount_state="free",
        after_mount_state=str(updated_body.face_occupancy.get(BODY_STRUCTURE_TEST_MOUNT) or "unknown"),
        can_run=False,
        can_reset=True,
        operator_hint="attach self-check completed; press R to reset",
        selected_face_id=BODY_STRUCTURE_TEST_MOUNT,
    )


# ---------------------------------------------------------------------------
# Interactive screen entrypoint.


def get_body_structure_console_view_model() -> BodyStructureConsoleViewModel:
    """Return the current interactive body-structure state for F1/F2/F8."""
    return build_body_structure_view_model_from_interactive_snapshot(
        get_body_structure_interactive_snapshot()
    )


def build_body_structure_view_model_from_interactive_snapshot(
    snapshot: BodyStructureInteractiveSnapshot,
) -> BodyStructureConsoleViewModel:
    decision = snapshot.decision
    card = snapshot.evidence_card
    return _build_view_model(
        body=snapshot.body,
        decision=decision,
        card=card,
        interaction_state=snapshot.interaction_state,
        last_action=snapshot.last_action,
        before_modules_count=snapshot.before_modules_count,
        after_modules_count=snapshot.after_modules_count,
        before_mount_state=snapshot.before_mount_state,
        after_mount_state=snapshot.after_mount_state,
        can_run=snapshot.can_run,
        can_reset=snapshot.can_reset,
        operator_hint=snapshot.operator_hint,
        selected_face_id=snapshot.selected_face_id,
    )


def _build_view_model(
    *,
    body: BodyConfigSnapshot,
    decision: Any | None,
    card: EvidenceCard | None,
    interaction_state: str,
    last_action: str,
    before_modules_count: int,
    after_modules_count: int,
    before_mount_state: str,
    after_mount_state: str,
    can_run: bool,
    can_reset: bool,
    operator_hint: str,
    selected_face_id: str,
) -> BodyStructureConsoleViewModel:
    modules = _module_rows(body)
    faces_range = f"{body.face_ids[0]}-{body.face_ids[-1]}" if body.face_ids else "missing"
    selected_face_id = selected_face_id or default_selected_face_id()
    faces = build_face_views(body, selected_face_id=selected_face_id)
    selected = selected_face_view(body, selected_face_id=selected_face_id)
    common = {
        "faces": faces,
        "selected_face_id": selected.face_id,
        "selected_face_role": selected.role,
        "selected_face_occupancy": selected.occupancy,
        "selected_face_module_id": selected.module_id,
    }
    if decision is None:
        return BodyStructureConsoleViewModel(
            seed_status="online",
            mode=BODY_STRUCTURE_MODE,
            transport=BODY_STRUCTURE_TRANSPORT,
            source=BODY_STRUCTURE_SOURCE,
            trust_status="waiting",
            faces_total=len(body.face_ids),
            faces_range=faces_range,
            attached_modules_count=len(modules),
            modules=modules,
            last_decision="waiting",
            last_stage="waiting",
            last_reason_code="",
            module_id="",
            mount_point=BODY_STRUCTURE_TEST_MOUNT,
            passport_status="waiting",
            runtime_ready=False,
            capability_status="inactive",
            audit_event_id="",
            evidence_card_id="",
            evidence_card_type="none",
            read_only=True,
            operator_summary="No body attach evidence yet. Press B to run attach self-check.",
            evidence_card=None,
            interaction_state=interaction_state,
            last_action=last_action,
            before_modules_count=before_modules_count,
            after_modules_count=after_modules_count,
            before_mount_state=before_mount_state,
            after_mount_state=after_mount_state,
            can_run=can_run,
            can_reset=can_reset,
            operator_hint=operator_hint,
            **common,
        )

    trust_status = BODY_STRUCTURE_TRUST if card is not None and card.source_type == "audit" else "missing"
    return BodyStructureConsoleViewModel(
        seed_status="online" if decision.audit_event_id else "missing",
        mode=BODY_STRUCTURE_MODE,
        transport=BODY_STRUCTURE_TRANSPORT,
        source=BODY_STRUCTURE_SOURCE,
        trust_status=trust_status,
        faces_total=len(body.face_ids),
        faces_range=faces_range,
        attached_modules_count=len(modules),
        modules=modules,
        last_decision=str(decision.status),
        last_stage=str(decision.stage),
        last_reason_code=str(decision.reason_code or ""),
        module_id=str(decision.module_id or ""),
        mount_point=str(decision.mount_point or BODY_STRUCTURE_TEST_MOUNT),
        passport_status=str(decision.passport_status or ""),
        runtime_ready=bool(decision.runtime_ready),
        capability_status=str(decision.capability_status or ""),
        audit_event_id=str(decision.audit_event_id or ""),
        evidence_card_id=str(decision.evidence_card_id or ""),
        evidence_card_type=card.card_type if card is not None else "missing",
        read_only=True if card is not None else False,
        operator_summary=card.operator_summary if card is not None else "body structure evidence missing",
        evidence_card=card,
        interaction_state=interaction_state,
        last_action=last_action,
        before_modules_count=before_modules_count,
        after_modules_count=after_modules_count,
        before_mount_state=before_mount_state,
        after_mount_state=after_mount_state,
        can_run=can_run,
        can_reset=can_reset,
        operator_hint=operator_hint,
        **common,
    )


# ---------------------------------------------------------------------------
# Screen formatting helpers.


def format_body_structure_cockpit_line(vm: BodyStructureConsoleViewModel | None = None) -> str:
    vm = vm or get_body_structure_console_view_model()
    ready = str(vm.runtime_ready).lower()
    if vm.last_decision == "already_attached" or vm.interaction_state == "already_attached":
        return (
            f"BODY STRUCTURE | already attached | faces={vm.faces_total} | modules={vm.attached_modules_count} | "
            f"{BODY_STRUCTURE_TEST_MOUNT}={vm.after_mount_state} | selected={vm.selected_face_id} | press R to reset"
        )
    if vm.last_decision == "attached":
        return (
            f"BODY STRUCTURE | online | faces={vm.faces_total} | "
            f"modules={vm.attached_modules_count} @ {vm.mount_point} | "
            f"ready={ready} | {vm.trust_status}"
        )
    if vm.last_decision == "waiting":
        return (
            f"BODY STRUCTURE | online | faces={vm.faces_total} | modules={vm.attached_modules_count} | "
            f"selected={vm.selected_face_id} | {BODY_STRUCTURE_TEST_MOUNT}={vm.after_mount_state} | action: press B"
        )
    reason = vm.last_reason_code or "no_reason"
    return f"BODY STRUCTURE | online | last={vm.last_decision} | {reason} | {vm.trust_status}"


def format_body_structure_system_summary(vm: BodyStructureConsoleViewModel | None = None) -> str:
    vm = vm or get_body_structure_console_view_model()
    module_lines = [
        f"- {row.module_id} | {row.mount_point} | {row.status} | "
        f"passport={row.passport_status} | ready={str(row.runtime_ready).lower()} | "
        f"capability={row.capability_status}"
        for row in vm.modules
    ] or ["- none"]
    face_map_lines = list(format_face_map_lines(vm.faces))
    selected_lines = [
        "Selected face",
        f"  face_id         {vm.selected_face_id}",
        f"  role            {vm.selected_face_role}",
        f"  occupancy       {vm.selected_face_occupancy}",
        f"  module          {vm.selected_face_module_id or 'none'}",
    ]
    if vm.last_decision == "waiting":
        return "\n".join(
            [
                "Body / Structure / Modules",
                f"Status            {vm.seed_status}",
                f"Mode              {vm.mode}",
                f"Transport         {vm.transport}",
                f"Faces             {vm.faces_range} ({vm.faces_total})",
                f"Attached modules  {vm.attached_modules_count}",
                f"{BODY_STRUCTURE_TEST_MOUNT}               {vm.after_mount_state}",
                *face_map_lines,
                *selected_lines,
                f"Last action       {vm.last_action}",
                f"Last decision     {vm.last_decision}",
                "Evidence          none yet",
                f"Next              {vm.operator_hint}",
                "Modules",
                *module_lines,
            ]
        )
    return "\n".join(
        [
            "Body / Structure / Modules",
            f"Seed status       {vm.seed_status}",
            f"Status            {vm.seed_status}",
            f"Mode              {vm.mode}",
            f"Transport         {vm.transport}",
            f"Faces             {vm.faces_range} ({vm.faces_total})",
            *face_map_lines,
            *selected_lines,
            f"Action            {vm.last_action}",
            f"Decision          {vm.last_decision}",
            f"Stage             {vm.last_stage}",
            "Before",
            f"  modules         {vm.before_modules_count}",
            f"  {BODY_STRUCTURE_TEST_MOUNT}             {vm.before_mount_state}",
            "After",
            f"  modules         {vm.after_modules_count}",
            f"  {BODY_STRUCTURE_TEST_MOUNT}             {vm.after_mount_state}",
            "Module",
            f"Module            {vm.module_id or 'none'}",
            f"Mount             {vm.mount_point}",
            f"Runtime ready     {str(vm.runtime_ready).lower()}",
            f"Capability        {vm.capability_status}",
            f"Source            {vm.source}",
            f"Trust             {vm.trust_status}",
            f"Evidence          {vm.evidence_card_id or 'none'}",
            f"  id              {vm.module_id or 'none'}",
            f"  mount           {vm.mount_point}",
            f"  face            {vm.mount_point}",
            f"  passport        {vm.passport_status}",
            f"  runtime_ready   {str(vm.runtime_ready).lower()}",
            f"  capability      {vm.capability_status}",
            "Evidence",
            f"  source          {vm.source}",
            f"  trust           {vm.trust_status}",
            f"  audit           {vm.audit_event_id or 'none'}",
            f"  card            {vm.evidence_card_id or 'none'}",
            "Modules",
            *module_lines,
        ]
    )


def body_structure_evidence_to_card_vm(card: EvidenceCard) -> EvidenceCardVM:
    state_key = "ok" if card.subject_status == "attached" else "blocked"
    mount = str(card.facts.get("mount_point") or card.facts.get("attempted_mount") or "missing")
    runtime_ready = str(card.runtime_ready or bool(card.facts.get("runtime_ready"))).lower()
    headline = (
        f"модуль {card.subject_id} установлен @ {mount}"
        if card.subject_status == "attached"
        else f"установка отклонена: {card.reason_code or 'код причины отсутствует'}"
    )
    reason_text = ", ".join(card.reason_codes)
    detail_lines = (
        f"карточка: {card.card_type}",
        f"операция: {card.operation}",
        f"гнездо: {mount}",
        f"грань: {mount}",
        f"состояние грани: {'занята' if card.subject_status == 'attached' else 'без изменений'}",
        f"паспорт: {card.facts.get('passport_status', 'missing')}",
        f"готов к работе: {runtime_ready}",
        f"способность: {card.facts.get('capability_status', 'missing')}",
        f"источник: {card.source_type}",
        f"доверие: {card.trust_status}",
        f"только чтение: {str(card.read_only).lower()}",
        f"аудит: {card.related_audit_event_id}",
        f"id карточки: {card.card_id}",
        f"режим: {BODY_STRUCTURE_MODE}",
        f"транспорт: {BODY_STRUCTURE_TRANSPORT}",
    )
    return EvidenceCardVM(
        subsystem="КОРПУС",
        state_key=state_key,
        headline=headline,
        reason_text=reason_text,
        detail_lines=detail_lines,
    )


def build_body_structure_evidence_card_vms(
    vm: BodyStructureConsoleViewModel | None = None,
) -> list[EvidenceCardVM]:
    vm = vm or get_body_structure_console_view_model()
    if vm.evidence_card is None:
        return [
            EvidenceCardVM(
                subsystem="КОРПУС",
                state_key="missing",
                headline="Улик по установке модуля пока нет. Нажмите B — проверка корпуса.",
                reason_text="BODY_STRUCTURE_WAITING",
                detail_lines=(
                    f"источник: {vm.source}",
                    f"режим: {vm.mode}",
                    f"транспорт: {vm.transport}",
                    f"выбранная грань: {vm.selected_face_id}",
                    f"подсказка: {vm.operator_hint}",
                ),
            )
        ]
    return [body_structure_evidence_to_card_vm(vm.evidence_card)]


# ---------------------------------------------------------------------------


def _find_audit_event(store: EventStore, event_id: str) -> SystemEvent | None:
    for event in store.snapshot():
        if event.event_id == event_id:
            return event
    return None


def _module_rows(body: BodyConfigSnapshot) -> tuple[BodyStructureModuleRow, ...]:
    rows: list[BodyStructureModuleRow] = []
    for module in body.modules:
        rows.append(
            BodyStructureModuleRow(
                module_id=str(module.get("module_id") or ""),
                mount_point=str(module.get("mount_point") or ""),
                status=str(module.get("status") or ""),
                passport_status=str(module.get("passport_status") or ""),
                capability_status=str(module.get("capability_status") or ""),
                runtime_ready=bool(module.get("runtime_ready", False)),
            )
        )
    return tuple(rows)
