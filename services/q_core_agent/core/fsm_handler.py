from typing import TYPE_CHECKING, Optional
from .interfaces import IFSMHandler
from .agent_logger import logger

if TYPE_CHECKING:
    from .agent import AgentContext
    from ..state.store import AsyncStateStore

# StateStore imports
from ..state.types import (
    FsmSnapshotDTO,
    FsmState,
    TransitionStatus,
    create_transition,
    next_snapshot,
)

# Legacy protobuf imports (только для совместимости)
from generated.fsm_state_pb2 import FsmStateSnapshot, StateTransition, FSMStateEnum


class FSMHandler(IFSMHandler):
    """
    Handles the Finite State Machine (FSM) logic for the Q-Core Agent.
    This handler is responsible for processing the current FSM state,
    evaluating conditions, and determining the next state.

    StateStore integration: единственный писатель FSM состояний.
    """

    def __init__(
        self, context: "AgentContext", state_store: Optional["AsyncStateStore"] = None
    ):
        self.context = context
        self.state_store = state_store
        logger.info(
            f"FSMHandler initialized with StateStore: {state_store is not None}"
        )

    async def process_fsm_dto(self, current_dto: FsmSnapshotDTO) -> FsmSnapshotDTO:
        """
        Новый метод для работы с DTO и StateStore.
        Обрабатывает переходы FSM и записывает результат в StateStore.
        """
        logger.debug(f"Processing FSM DTO state: {current_dto.state.name}")

        # Получаем условия для переходов
        bios_ok = self.context.is_bios_ok()
        has_proposals = self.context.has_valid_proposals()

        # Определяем новое состояние и причину перехода
        new_state, trigger_event = self._compute_transition_dto(
            current_dto.state, bios_ok, has_proposals
        )

        # Создаём переход если состояние изменилось
        transition = None
        if new_state != current_dto.state:
            logger.info(
                f"FSM Transition: {current_dto.state.name} -> {new_state.name} (Trigger: {trigger_event})"
            )
            transition = create_transition(
                from_state=current_dto.state,
                to_state=new_state,
                trigger=trigger_event,
                status=TransitionStatus.SUCCESS,
            )

        # Создаём новый снапшот
        new_dto = next_snapshot(
            current=current_dto,
            new_state=new_state,
            reason=trigger_event if transition else current_dto.reason,
            transition=transition,
        )

        # Записываем в StateStore если доступен
        if self.state_store:
            try:
                stored_dto = await self.state_store.set(new_dto)
                logger.debug(
                    f"FSM state stored: version={stored_dto.version}, state={stored_dto.state.name}"
                )
                return stored_dto
            except Exception as e:
                logger.error(f"Failed to store FSM state: {e}")
                # Продолжаем работать без StateStore

        logger.debug(f"FSM new DTO state: {new_dto.state.name}")
        return new_dto

    def _compute_transition_dto(
        self, current_state: FsmState, bios_ok: bool, has_proposals: bool
    ) -> tuple[FsmState, str]:
        """Вычисляет следующее состояние на основе текущего и условий"""
        if current_state == FsmState.BOOTING:
            if bios_ok:
                return FsmState.IDLE, "BOOT_COMPLETE"
            else:
                return FsmState.ERROR_STATE, "BIOS_ERROR"
        elif current_state == FsmState.IDLE:
            if not bios_ok:
                return FsmState.ERROR_STATE, "BIOS_ERROR"
            elif has_proposals:
                return FsmState.ACTIVE, "PROPOSALS_RECEIVED"
        elif current_state == FsmState.ACTIVE:
            if not bios_ok:
                return FsmState.ERROR_STATE, "BIOS_ERROR"
            elif not has_proposals:
                return FsmState.IDLE, "NO_PROPOSALS"
        elif current_state == FsmState.ERROR_STATE:
            if bios_ok and not has_proposals:
                return FsmState.IDLE, "ERROR_CLEARED"

        # Нет изменения состояния
        return current_state, "NO_CHANGE"

    def process_fsm_state(
        self, current_fsm_state: FsmStateSnapshot
    ) -> FsmStateSnapshot:
        """
        Legacy метод для обратной совместимости.
        Использует старую protobuf логику.
        """
        logger.debug(
            f"Processing FSM state (legacy): {current_fsm_state.current_state}"
        )

        next_state = FsmStateSnapshot()
        next_state.CopyFrom(current_fsm_state)  # Start with a copy of the current state

        # State transition logic
        current_state = current_fsm_state.current_state
        bios_ok = self.context.is_bios_ok()
        has_proposals = self.context.has_valid_proposals()

        new_state_name = current_state
        trigger_event = ""

        if current_state == FSMStateEnum.BOOTING:
            if bios_ok:
                new_state_name = FSMStateEnum.IDLE
                trigger_event = "BOOT_COMPLETE"
            else:
                new_state_name = FSMStateEnum.ERROR_STATE
                trigger_event = "BIOS_ERROR"
        elif current_state == FSMStateEnum.IDLE:
            if not bios_ok:
                new_state_name = FSMStateEnum.ERROR_STATE
                trigger_event = "BIOS_ERROR"
            elif has_proposals:
                new_state_name = FSMStateEnum.ACTIVE
                trigger_event = "PROPOSALS_RECEIVED"
        elif current_state == FSMStateEnum.ACTIVE:
            if not bios_ok:
                new_state_name = FSMStateEnum.ERROR_STATE
                trigger_event = "BIOS_ERROR"
            elif not has_proposals:
                new_state_name = FSMStateEnum.IDLE
                trigger_event = "NO_PROPOSALS"
        elif current_state == FSMStateEnum.ERROR_STATE:
            if bios_ok and not has_proposals:
                new_state_name = FSMStateEnum.IDLE
                trigger_event = "ERROR_CLEARED"

        if new_state_name != current_state:
            logger.info(
                f"FSM Transition (legacy): {current_state} -> {new_state_name} (Trigger: {trigger_event})"
            )
            new_transition = StateTransition(
                from_state=current_state,
                to_state=new_state_name,
                trigger_event=trigger_event,
            )
            new_transition.timestamp.GetCurrentTime()
            next_state.current_state = new_state_name
            next_state.history.append(new_transition)

        # Update timestamp for the new state snapshot
        next_state.timestamp.GetCurrentTime()

        logger.debug(f"FSM new state (legacy): {next_state.current_state}")
        return next_state
