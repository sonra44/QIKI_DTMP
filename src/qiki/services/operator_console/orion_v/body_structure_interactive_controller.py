"""Interactive local controller for visible QIKI Body Structure telemetry.

This module is the operator-console bridge for a deliberately small interactive
loop: press an ORION action, run the real ``run_attach_pipeline`` body-structure
seed, record audit-backed evidence, and let F1/F2/F8 redraw from the resulting
state.

It is not flight telemetry, not PDU/thermal/bayonet bridge, and not module
capability activation. The transport is explicitly local/direct so the operator
can see the current runtime seed work without pretending NATS/gRPC integration
already exists.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from qiki.services.q_core_agent.core.body_structure import (
    BodyConfigSnapshot,
    ModuleAttachRequest,
    ModulePassport,
    run_attach_pipeline,
)
from qiki.services.q_core_agent.core.event_store import EventStore, SystemEvent
from qiki.services.operator_console.orion_v.evidence_card import (
    EvidenceCard,
    evidence_card_from_audit_event,
)
from qiki.services.operator_console.orion_v.body_structure_face_map import (
    DEFAULT_SELECTED_FACE_ID,
    next_face_id,
    previous_face_id,
    normalize_selected_face_id,
)

BODY_STRUCTURE_INTERACTIVE_SOURCE = "body_structure.runtime_seed"
BODY_STRUCTURE_INTERACTIVE_MODE = "interactive local self-check"
BODY_STRUCTURE_INTERACTIVE_TRANSPORT = "direct in-process adapter"
BODY_STRUCTURE_INTERACTIVE_TRUST = "audit_backed"
BODY_STRUCTURE_TEST_MODULE_ID = "test_sensor_module_001"
BODY_STRUCTURE_TEST_MODULE_CLASS = "sensor"
BODY_STRUCTURE_TEST_MOUNT = "F06"


@dataclass(frozen=True, slots=True)
class BodyStructureInteractiveSnapshot:
    """State consumed by the ORION body-structure view-model.

    ``decision`` / ``audit_event`` / ``evidence_card`` are empty until the user
    runs the self-check. ``before_*`` / ``after_*`` are kept explicit so F2 can
    show visible state transition rather than a static summary.
    """

    interaction_state: str
    last_action: str
    body: BodyConfigSnapshot
    before_modules_count: int
    after_modules_count: int
    before_mount_state: str
    after_mount_state: str
    selected_face_id: str
    can_run: bool
    can_reset: bool
    operator_hint: str
    decision: Any | None = None
    audit_event: SystemEvent | None = None
    evidence_card: EvidenceCard | None = None


class BodyStructureInteractiveController:
    """Small stateful controller for ORION's visible body-structure loop."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store = EventStore(backend="memory")
        self._body = BodyConfigSnapshot.skeleton()
        self._selected_face_id = DEFAULT_SELECTED_FACE_ID
        self._snapshot = self._waiting_snapshot(last_action="initial")

    def snapshot(self) -> BodyStructureInteractiveSnapshot:
        with self._lock:
            return self._snapshot

    def reset(self) -> BodyStructureInteractiveSnapshot:
        """Return the visible body-structure seed to the pre-action state.

        ADR-0019 §3: сброс — не молчаливый detach; событие фиксируется в новом
        store (старый in-memory store уничтожается вместе со своей историей).
        """
        with self._lock:
            detached = [str(m.get("module_id")) for m in self._body.modules]
            self._store = EventStore(backend="memory")
            self._store.append_new(
                subsystem="body_structure",
                event_type="body_structure_reset",
                payload={"detached_modules": detached, "source": "operator_reset"},
            )
            self._body = BodyConfigSnapshot.skeleton()
            self._selected_face_id = DEFAULT_SELECTED_FACE_ID
            self._snapshot = self._waiting_snapshot(last_action="reset")
            return self._snapshot


    def select_next_face(self) -> BodyStructureInteractiveSnapshot:
        """Move the operator selection to the next Face Map entry.

        This is navigation only. It does not change body_config, attach modules,
        create mount points, or move the self-check target away from F06.
        """
        with self._lock:
            self._selected_face_id = next_face_id(self._selected_face_id, self._body.face_ids)
            self._snapshot = self._navigation_snapshot(
                last_action="select_next_face",
                operator_hint=f"выбрана {self._selected_face_id}; N/P — смена грани",
            )
            return self._snapshot

    def select_previous_face(self) -> BodyStructureInteractiveSnapshot:
        """Move the operator selection to the previous Face Map entry.

        Navigation only: no body_config mutation, no dynamic mount creation, and
        no change to the fixed F06 self-check target.
        """
        with self._lock:
            self._selected_face_id = previous_face_id(self._selected_face_id, self._body.face_ids)
            self._snapshot = self._navigation_snapshot(
                last_action="select_previous_face",
                operator_hint=f"выбрана {self._selected_face_id}; N/P — смена грани",
            )
            return self._snapshot

    def _navigation_snapshot(
        self,
        *,
        last_action: str,
        operator_hint: str,
    ) -> BodyStructureInteractiveSnapshot:
        if self._snapshot.decision is None:
            return self._waiting_snapshot(last_action=last_action)
        return BodyStructureInteractiveSnapshot(
            interaction_state=self._snapshot.interaction_state,
            last_action=last_action,
            body=self._snapshot.body,
            before_modules_count=self._snapshot.before_modules_count,
            after_modules_count=self._snapshot.after_modules_count,
            before_mount_state=self._snapshot.before_mount_state,
            after_mount_state=self._snapshot.after_mount_state,
            selected_face_id=self._selected_face_id,
            can_run=self._snapshot.can_run,
            can_reset=self._snapshot.can_reset,
            operator_hint=operator_hint,
            decision=self._snapshot.decision,
            audit_event=self._snapshot.audit_event,
            evidence_card=self._snapshot.evidence_card,
        )

    def run_attach_self_check(self) -> BodyStructureInteractiveSnapshot:
        """Run one positive attach self-check through the real attach pipeline.

        If the test mount is already occupied, do not create a second rejection
        flow in this visible patch. The operator receives an explicit "already
        attached" state and can press R to reset. Rejection-path surfacing already
        exists in the runtime seed; this patch is about visible positive control.
        """
        with self._lock:
            before_body = self._body
            before_modules = len(before_body.modules)
            before_mount = self._mount_state(before_body)

            if before_mount != "free":
                self._snapshot = BodyStructureInteractiveSnapshot(
                    interaction_state="already_attached",
                    last_action="attach_self_check_skipped",
                    body=before_body,
                    before_modules_count=before_modules,
                    after_modules_count=before_modules,
                    before_mount_state=before_mount,
                    after_mount_state=before_mount,
                    selected_face_id=self._selected_face_id,
                    can_run=False,
                    can_reset=True,
                    operator_hint="модуль уже установлен; R — сброс",
                    decision=self._snapshot.decision,
                    audit_event=self._snapshot.audit_event,
                    evidence_card=self._snapshot.evidence_card,
                )
                return self._snapshot

            request = ModuleAttachRequest(
                request_id="orion-interactive-body-attach-self-check",
                module_id=BODY_STRUCTURE_TEST_MODULE_ID,
                mount_point=BODY_STRUCTURE_TEST_MOUNT,
                passport=ModulePassport(
                    module_id=BODY_STRUCTURE_TEST_MODULE_ID,
                    module_class=BODY_STRUCTURE_TEST_MODULE_CLASS,
                    mount_point=BODY_STRUCTURE_TEST_MOUNT,
                    provided_capabilities=("basic_sensor_read",),
                ),
            )
            decision, updated_body = run_attach_pipeline(before_body, request, store=self._store)
            audit_event = self._find_audit_event(decision.audit_event_id)
            evidence_card = evidence_card_from_audit_event(audit_event) if audit_event is not None else None
            self._body = updated_body
            self._snapshot = BodyStructureInteractiveSnapshot(
                interaction_state=decision.status,
                last_action="attach_self_check",
                body=updated_body,
                before_modules_count=before_modules,
                after_modules_count=len(updated_body.modules),
                before_mount_state=before_mount,
                after_mount_state=self._mount_state(updated_body),
                selected_face_id=self._selected_face_id,
                can_run=False,
                can_reset=True,
                operator_hint="самопроверка установки завершена; R — сброс",
                decision=decision,
                audit_event=audit_event,
                evidence_card=evidence_card,
            )
            return self._snapshot

    def attach_module(
        self,
        *,
        module_id: str,
        mount_point: str,
        passport: ModulePassport | None,
        request_id: str,
    ) -> BodyStructureInteractiveSnapshot:
        """P3 (ADR-0019 §3): установка модуля по ПЛОМБЕ решения.

        Без шорткатов: занятость гнезда, класс грани и паспорт решает конвейер
        (у каждого отказа — СВОЁ аудит-событие). can_run не запирается — 
        допустимость следующей установки решает конвейер, не снапшот.
        """
        with self._lock:
            before_body = self._body
            before_modules = len(before_body.modules)
            before_mount = str(before_body.face_occupancy.get(mount_point) or "unknown")
            request = ModuleAttachRequest(
                request_id=request_id,
                module_id=module_id,
                mount_point=mount_point,
                passport=passport,
            )
            decision, updated_body = run_attach_pipeline(before_body, request, store=self._store)
            audit_event = self._find_audit_event(decision.audit_event_id)
            evidence_card = evidence_card_from_audit_event(audit_event) if audit_event is not None else None
            self._body = updated_body
            self._snapshot = BodyStructureInteractiveSnapshot(
                interaction_state=decision.status,
                last_action="attach_module",
                body=updated_body,
                before_modules_count=before_modules,
                after_modules_count=len(updated_body.modules),
                before_mount_state=before_mount,
                after_mount_state=str(updated_body.face_occupancy.get(mount_point) or "unknown"),
                selected_face_id=self._selected_face_id,
                can_run=True,
                can_reset=True,
                operator_hint=f"установка {module_id} @ {mount_point}: {decision.status}",
                decision=decision,
                audit_event=audit_event,
                evidence_card=evidence_card,
            )
            return self._snapshot

    def _waiting_snapshot(self, *, last_action: str) -> BodyStructureInteractiveSnapshot:
        return BodyStructureInteractiveSnapshot(
            interaction_state="waiting",
            last_action=last_action,
            body=self._body,
            before_modules_count=len(self._body.modules),
            after_modules_count=len(self._body.modules),
            before_mount_state=self._mount_state(self._body),
            after_mount_state=self._mount_state(self._body),
            selected_face_id=normalize_selected_face_id(self._selected_face_id, self._body.face_ids),
            can_run=True,
            can_reset=False,
            operator_hint="B — запустить самопроверку установки",
        )

    def _mount_state(self, body: BodyConfigSnapshot) -> str:
        return str(body.face_occupancy.get(BODY_STRUCTURE_TEST_MOUNT) or "unknown")

    def _find_audit_event(self, event_id: str) -> SystemEvent | None:
        for event in self._store.snapshot():
            if event.event_id == event_id:
                return event
        return None


_CONTROLLER = BodyStructureInteractiveController()


def get_body_structure_interactive_controller() -> BodyStructureInteractiveController:
    return _CONTROLLER


def get_body_structure_interactive_snapshot() -> BodyStructureInteractiveSnapshot:
    return _CONTROLLER.snapshot()


def run_body_structure_interactive_self_check() -> BodyStructureInteractiveSnapshot:
    return _CONTROLLER.run_attach_self_check()


def reset_body_structure_interactive_state() -> BodyStructureInteractiveSnapshot:
    return _CONTROLLER.reset()


def select_next_body_structure_face() -> BodyStructureInteractiveSnapshot:
    return _CONTROLLER.select_next_face()


def select_previous_body_structure_face() -> BodyStructureInteractiveSnapshot:
    return _CONTROLLER.select_previous_face()


__all__ = [
    "BODY_STRUCTURE_INTERACTIVE_MODE",
    "BODY_STRUCTURE_INTERACTIVE_SOURCE",
    "BODY_STRUCTURE_INTERACTIVE_TRANSPORT",
    "BODY_STRUCTURE_INTERACTIVE_TRUST",
    "BODY_STRUCTURE_TEST_MODULE_CLASS",
    "BODY_STRUCTURE_TEST_MODULE_ID",
    "BODY_STRUCTURE_TEST_MOUNT",
    "BodyStructureInteractiveController",
    "BodyStructureInteractiveSnapshot",
    "get_body_structure_interactive_controller",
    "get_body_structure_interactive_snapshot",
    "reset_body_structure_interactive_state",
    "run_body_structure_interactive_self_check",
    "select_next_body_structure_face",
    "select_previous_body_structure_face",
]
