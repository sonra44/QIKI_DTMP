
from typing import Any, Dict
import time
from .agent_logger import logger
from .interfaces import IDataProvider
from .agent import QCoreAgent # Import QCoreAgent for type hinting

class TickOrchestrator:
    """
    Orchestrates the execution of a single agent tick, handling error recovery and structured logging.
    """
    def __init__(self, agent: QCoreAgent, config: Dict[str, Any]):
        self.agent = agent
        self.config = config
        self.errors_count = 0
        logger.info("TickOrchestrator initialized.")

    def run_tick(self, data_provider: IDataProvider):
        start_time = time.time()
        self.agent.tick_id += 1
        logger.info("--- Tick Start ---", extra={
            "tick_id": self.agent.tick_id
        })
        
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
            logger.info("Tick complete", extra={
                "tick_id": self.agent.tick_id,
                "bios_ok": self.agent.context.bios_status.is_ok if self.agent.context.bios_status else None,
                "fsm_state": self.agent.context.fsm_state.current_state if self.agent.context.fsm_state else None,
                "proposals_count": len(self.agent.context.proposals),
                "tick_duration_ms": round(tick_duration * 1000, 2),
                "errors_count": self.errors_count,
                "phase_durations_ms": {
                    "update_context": round(update_context_duration * 1000, 2),
                    "handle_bios": round(handle_bios_duration * 1000, 2),
                    "handle_fsm": round(handle_fsm_duration * 1000, 2),
                    "evaluate_proposals": round(evaluate_proposals_duration * 1000, 2),
                    "make_decision": round(make_decision_duration * 1000, 2)
                }
            })
        except Exception as e:
            self.errors_count += 1
            logger.error(f"Tick failed: {e}")
            self.agent._switch_to_safe_mode()
            time.sleep(self.config.get("recovery_delay", 2)) # configurable pause
