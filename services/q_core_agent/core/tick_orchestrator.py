from typing import TYPE_CHECKING, Optional
import time
import os
import asyncio
from .agent_logger import logger
from .interfaces import IDataProvider

if TYPE_CHECKING:
    from .agent import QCoreAgent
    from ..state.store import AsyncStateStore
    from UP.config_models import QCoreAgentConfig

# StateStore imports
from ..state.conv import dto_to_proto


class TickOrchestrator:
    """
    Orchestrates the execution of a single agent tick, handling error recovery and structured logging.
    StateStore integration: координирует работу с новой архитектурой состояний.
    """

    def __init__(
        self,
        agent: "QCoreAgent",
        config: "QCoreAgentConfig",
        state_store: Optional["AsyncStateStore"] = None,
    ):
        self.agent = agent
        self.config = config
        self.state_store = state_store
        self.errors_count = 0
        self.use_state_store = (
            os.getenv("QIKI_USE_STATESTORE", "false").lower() == "true"
        )
        logger.info(
            f"TickOrchestrator initialized with StateStore: {self.state_store is not None}, enabled: {self.use_state_store}"
        )

    async def run_tick_async(self, data_provider: IDataProvider):
        """
        Новый асинхронный метод для работы с StateStore.
        """
        if not self.use_state_store or not self.state_store:
            # Fallback на синхронный метод
            self.run_tick(data_provider)
            return

        start_time = time.time()
        self.agent.tick_id += 1
        logger.info("--- Async Tick Start ---", extra={"tick_id": self.agent.tick_id})

        try:
            # Phase 1: Update Context (без FSM из провайдера)
            update_context_start = time.time()
            self.agent._update_context_without_fsm(data_provider)
            update_context_duration = time.time() - update_context_start

            # Phase 2: Handle BIOS
            handle_bios_start = time.time()
            self.agent._handle_bios()
            handle_bios_duration = time.time() - handle_bios_start

            # Phase 3: Handle FSM через StateStore
            handle_fsm_start = time.time()
            await self._handle_fsm_with_state_store()
            handle_fsm_duration = time.time() - handle_fsm_start

            # Phase 4: Evaluate Proposals
            evaluate_proposals_start = time.time()
            self.agent._evaluate_proposals()
            evaluate_proposals_duration = time.time() - evaluate_proposals_start

            # Phase 5: Make Decision
            make_decision_start = time.time()
            self.agent._make_decision()
            make_decision_duration = time.time() - make_decision_start

            tick_duration = time.time() - start_time
            logger.info(
                "Async Tick complete",
                extra={
                    "tick_id": self.agent.tick_id,
                    "bios_ok": self.agent.context.bios_status.all_systems_go
                    if self.agent.context.bios_status
                    else None,
                    "fsm_state": self.agent.context.fsm_state.current_state
                    if self.agent.context.fsm_state
                    else None,
                    "proposals_count": len(self.agent.context.proposals),
                    "tick_duration_ms": round(tick_duration * 1000, 2),
                    "errors_count": self.errors_count,
                    "phase_durations_ms": {
                        "update_context": round(update_context_duration * 1000, 2),
                        "handle_bios": round(handle_bios_duration * 1000, 2),
                        "handle_fsm": round(handle_fsm_duration * 1000, 2),
                        "evaluate_proposals": round(
                            evaluate_proposals_duration * 1000, 2
                        ),
                        "make_decision": round(make_decision_duration * 1000, 2),
                    },
                },
            )
        except Exception as e:
            self.errors_count += 1
            logger.error(f"Async Tick failed: {e}")
            self.agent._switch_to_safe_mode()
            await asyncio.sleep(self.config.recovery_delay)  # async pause

    async def _handle_fsm_with_state_store(self):
        """Обработка FSM с использованием StateStore"""
        try:
            # Получаем текущее состояние из StateStore
            current_dto = await self.state_store.get()

            if current_dto is None:
                # Инициализируем StateStore если пуст
                current_dto = await self.state_store.initialize_if_empty()
                logger.info("StateStore initialized with COLD_START")

            # Обрабатываем FSM переходы через новый метод
            updated_dto = await self.agent.fsm_handler.process_fsm_dto(current_dto)

            # Конвертируем в protobuf для контекста (для совместимости с логами)
            self.agent.context.fsm_state = dto_to_proto(updated_dto)

            logger.debug(
                f"FSM processed: v={updated_dto.version}, state={updated_dto.state.name}"
            )

        except Exception as e:
            logger.error(f"FSM StateStore processing failed: {e}")
            # Fallback на старый метод
            self.agent._handle_fsm()

    def run_tick(self, data_provider: IDataProvider):
        """
        Legacy синхронный метод для обратной совместимости.
        """
        start_time = time.time()
        self.agent.tick_id += 1
        logger.info(
            "--- Tick Start (Legacy) ---", extra={"tick_id": self.agent.tick_id}
        )

        try:
            # Phase 1: Update Context
            update_context_start = time.time()
            self.agent._update_context(data_provider)
            update_context_duration = time.time() - update_context_start

            # Phase 2: Handle BIOS
            handle_bios_start = time.time()
            self.agent._handle_bios()
            handle_bios_duration = time.time() - handle_bios_start

            # Phase 3: Handle FSM
            handle_fsm_start = time.time()
            self.agent._handle_fsm()
            handle_fsm_duration = time.time() - handle_fsm_start

            # Phase 4: Evaluate Proposals
            evaluate_proposals_start = time.time()
            self.agent._evaluate_proposals()
            evaluate_proposals_duration = time.time() - evaluate_proposals_start

            # Phase 5: Make Decision
            make_decision_start = time.time()
            self.agent._make_decision()
            make_decision_duration = time.time() - make_decision_start

            tick_duration = time.time() - start_time
            logger.info(
                "Tick complete (Legacy)",
                extra={
                    "tick_id": self.agent.tick_id,
                    "bios_ok": self.agent.context.bios_status.all_systems_go
                    if self.agent.context.bios_status
                    else None,
                    "fsm_state": self.agent.context.fsm_state.current_state
                    if self.agent.context.fsm_state
                    else None,
                    "proposals_count": len(self.agent.context.proposals),
                    "tick_duration_ms": round(tick_duration * 1000, 2),
                    "errors_count": self.errors_count,
                    "phase_durations_ms": {
                        "update_context": round(update_context_duration * 1000, 2),
                        "handle_bios": round(handle_bios_duration * 1000, 2),
                        "handle_fsm": round(handle_fsm_duration * 1000, 2),
                        "evaluate_proposals": round(
                            evaluate_proposals_duration * 1000, 2
                        ),
                        "make_decision": round(make_decision_duration * 1000, 2),
                    },
                },
            )
        except Exception as e:
            self.errors_count += 1
            logger.error(f"Tick failed (Legacy): {e}")
            self.agent._switch_to_safe_mode()
            time.sleep(self.config.recovery_delay)  # configurable pause
