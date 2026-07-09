from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from qiki.services.q_core_agent.core.interfaces import IFSMHandler
from qiki.services.q_core_agent.core.agent_logger import logger
from qiki.services.q_core_agent.core.guard_table import GuardEvaluationResult

if TYPE_CHECKING:
    from qiki.services.q_core_agent.core.agent import AgentContext
    from qiki.services.q_core_agent.core.world_model import WorldModel

from qiki.services.q_core_agent.state.types import (
    FsmState,
    TransitionStatus,
    create_transition,
    next_snapshot,
    FsmSnapshotDTO,
)

from qiki.shared.models.core import (
    FsmStateSnapshot as PydanticFsmStateSnapshot,
    FsmTransition as PydanticFsmTransition,
    FsmStateEnum,
)

# Аудит 2026-07-09 (0.6): значения agent-домена и shared-домена НЕ совпадают
# (ERROR_STATE(4) vs PAUSED(4), SHUTDOWN(5) vs ERROR(5)) — IntEnum-коэрция по
# значению превращала аварию в паузу. Только явный маппинг.
_AGENT_TO_SHARED_STATE: dict[FsmState, FsmStateEnum] = {
    FsmState.UNSPECIFIED: FsmStateEnum.OFFLINE,
    FsmState.BOOTING: FsmStateEnum.BOOTING,
    FsmState.IDLE: FsmStateEnum.IDLE,
    FsmState.ACTIVE: FsmStateEnum.RUNNING,
    FsmState.ERROR_STATE: FsmStateEnum.ERROR,
    FsmState.SHUTDOWN: FsmStateEnum.TERMINATING,
}
# PAUSED отсутствует в agent-домене намеренно: пауза — операторское состояние,
# стандартные правила агента её не трогают.
_SHARED_TO_AGENT_STATE: dict[FsmStateEnum, FsmState] = {
    FsmStateEnum.OFFLINE: FsmState.UNSPECIFIED,
    FsmStateEnum.BOOTING: FsmState.BOOTING,
    FsmStateEnum.IDLE: FsmState.IDLE,
    FsmStateEnum.RUNNING: FsmState.ACTIVE,
    FsmStateEnum.ERROR: FsmState.ERROR_STATE,
    FsmStateEnum.TERMINATING: FsmState.SHUTDOWN,
}


class FSMHandler(IFSMHandler):
    def __init__(self, context: "AgentContext", world_model: Optional["WorldModel"] = None):
        self.context = context
        self.world_model = world_model
        logger.info("FSMHandler initialized.")

    async def process_fsm_dto(self, current_fsm_state_dto: FsmSnapshotDTO) -> FsmSnapshotDTO:
        """
        Обработка FSM перехода напрямую с использованием DTO.
        """
        logger.debug(
            "FSMHandler: Processing FSM state: %s",
            current_fsm_state_dto.state.name,
        )

        guard_event = self._select_guard_event()
        if guard_event:
            next_state, trigger_event = self._apply_guard_event(guard_event, current_fsm_state_dto.state)
        else:
            next_state, trigger_event = self._apply_standard_rules(current_fsm_state_dto.state)

        transition_dto = create_transition(
            from_state=current_fsm_state_dto.state,
            to_state=next_state,
            trigger=trigger_event,
            status=TransitionStatus.SUCCESS,
        )

        new_snapshot_dto = next_snapshot(current_fsm_state_dto, next_state, trigger_event, transition_dto)

        logger.debug(
            "FSM transitioned from %s to %s (Trigger: %s)",
            current_fsm_state_dto.state.name,
            new_snapshot_dto.state.name,
            trigger_event,
        )

        return new_snapshot_dto

    def process_fsm_state(self, current_fsm_state: PydanticFsmStateSnapshot) -> PydanticFsmStateSnapshot:
        try:
            state = current_fsm_state
            if state is None:
                state = PydanticFsmStateSnapshot(
                    current_state=FsmStateEnum.BOOTING,
                    previous_state=FsmStateEnum.OFFLINE,
                )

            # 0.6: правила работают ТОЛЬКО в agent-домене; вход/выход — через
            # явный маппинг. PAUSED не мапится — операторскую паузу правила
            # не трогают (раньше PAUSED(4)==ERROR_STATE(4) «лечился» в IDLE).
            agent_state = _SHARED_TO_AGENT_STATE.get(state.current_state)
            if agent_state is None:
                return state

            guard_event = self._select_guard_event()
            if guard_event:
                next_agent_state, event = self._apply_guard_event(guard_event, agent_state)
            else:
                next_agent_state, event = self._apply_standard_rules(agent_state)
            next_state = _AGENT_TO_SHARED_STATE[FsmState(next_agent_state)]

            if next_state != state.current_state:
                transition = PydanticFsmTransition(
                    event_name=event,
                    from_state=state.current_state,
                    to_state=next_state,
                )
                state.history.append(transition)
                state.last_transition = transition
                state.previous_state = state.current_state
                state.current_state = next_state

            return state
        except Exception as exc:  # noqa: BLE001
            logger.error(f"FSMHandler.process_fsm_state failed: {exc}")
            raise

    def _apply_standard_rules(self, current_state: FsmState | FsmStateEnum) -> tuple[FsmState | FsmStateEnum, str]:
        if current_state == FsmState.BOOTING and self.context.is_bios_ok():
            return FsmState.IDLE, "BOOT_COMPLETE"

        if current_state == FsmState.BOOTING and not self.context.is_bios_ok():
            return FsmState.ERROR_STATE, "BIOS_ERROR"

        if current_state == FsmState.IDLE and self.context.has_valid_proposals():
            return FsmState.ACTIVE, "PROPOSALS_RECEIVED"

        if current_state == FsmState.ACTIVE and not self.context.has_valid_proposals():
            return FsmState.IDLE, "NO_PROPOSALS"

        if current_state == FsmState.ERROR_STATE and self.context.is_bios_ok():
            return FsmState.IDLE, "ERROR_CLEARED"

        return current_state, "NO_CHANGE"

    def _select_guard_event(self) -> Optional[GuardEvaluationResult]:
        if self.context.guard_events:
            return max(
                self.context.guard_events,
                key=lambda event: event.severity_weight,
            )
        if self.world_model:
            return self.world_model.most_critical_guard()
        return None

    def _apply_guard_event(
        self,
        guard_event: GuardEvaluationResult,
        current_state: FsmState | FsmStateEnum,
    ) -> tuple[FsmState | FsmStateEnum, str]:
        logger.warning(
            "Guard event detected: rule=%s severity=%s track=%s range=%.2fm",
            guard_event.rule_id,
            guard_event.severity,
            guard_event.track_id,
            guard_event.range_m,
        )

        if guard_event.severity == "critical":
            return FsmState.ERROR_STATE, guard_event.fsm_event

        if guard_event.severity == "warning" and current_state == FsmState.IDLE:
            return FsmState.ACTIVE, guard_event.fsm_event

        return current_state, guard_event.fsm_event
