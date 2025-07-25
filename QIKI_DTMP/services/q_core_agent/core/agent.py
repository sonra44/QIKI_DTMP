import time
from typing import Optional, Dict, Any
from .agent_logger import logger
from .interfaces import IDataProvider, IBiosHandler, IFSMHandler, IProposalEvaluator, IRuleEngine, INeuralEngine
from .bot_core import BotCore

# Импортируем сгенерированные Protobuf классы
from generated.bios_status_pb2 import BIOSStatus
from generated.fsm_state_pb2 import FSMState
from generated.proposal_pb2 import Proposal

import os
from .bios_handler import BiosHandler
from .fsm_handler import FSMHandler
from .proposal_evaluator import ProposalEvaluator
from .tick_orchestrator import TickOrchestrator
from .rule_engine import RuleEngine
from .neural_engine import NeuralEngine

class AgentContext:
    def __init__(self, bios_status: Optional[BIOSStatus] = None, fsm_state: Optional[FSMState] = None, proposals: Optional[list[Proposal]] = None):
        self.bios_status = bios_status
        self.fsm_state = fsm_state
        self.proposals = proposals if proposals is not None else []

    def update_from_provider(self, data_provider: IDataProvider):
        self.bios_status = data_provider.get_bios_status()
        self.fsm_state = data_provider.get_fsm_state()
        self.proposals = data_provider.get_proposals()
        logger.debug("AgentContext updated from data provider.")

    def is_bios_ok(self) -> bool:
        return self.bios_status is not None and self.bios_status.all_systems_go

    def has_valid_proposals(self) -> bool:
        return bool(self.proposals)


class QCoreAgent:
    def __init__(self, config: dict):
        self.config = config
        self.context = AgentContext()
        self.tick_id = 0
        
        # Initialize BotCore (assuming base_path is the q_core_agent directory)
        q_core_agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.bot_core = BotCore(base_path=q_core_agent_root)
        
        # Initialize handlers
        self.bios_handler: IBiosHandler = BiosHandler(self.bot_core)
        self.fsm_handler: IFSMHandler = FSMHandler(self.context)
        self.proposal_evaluator: IProposalEvaluator = ProposalEvaluator(config)
        self.rule_engine: IRuleEngine = RuleEngine(self.context, config)
        self.neural_engine: INeuralEngine = NeuralEngine(self.context, config)

        # Initialize TickOrchestrator
        self.orchestrator = TickOrchestrator(self, config)

        logger.info("QCoreAgent initialized.")

    def _update_context(self, data_provider: IDataProvider):
        self.context.update_from_provider(data_provider)

    def run_tick(self, data_provider: IDataProvider):
        self.orchestrator.run_tick(data_provider)

    def _handle_bios(self):
        try:
            # Process BIOS status using the handler
            self.context.bios_status = self.bios_handler.process_bios_status(self.context.bios_status)
            logger.debug(f"Handling BIOS status: {self.context.bios_status}")
        except Exception as e:
            logger.error(f"BIOS handler failed: {e}")
            self._switch_to_safe_mode()

    def _handle_fsm(self):
        try:
            self.context.fsm_state = self.fsm_handler.process_fsm_state(self.context.fsm_state)
            logger.debug(f"Handling FSM state: {self.context.fsm_state}")
        except Exception as e:
            logger.error(f"FSM handler failed: {e}")
            self._switch_to_safe_mode()

    def _evaluate_proposals(self):
        try:
            # Generate proposals from Rule Engine and Neural Engine
            rule_proposals = self.rule_engine.generate_proposals(self.context)
            neural_proposals = self.neural_engine.generate_proposals(self.context)
            
            all_proposals = rule_proposals + neural_proposals

            self.context.proposals = self.proposal_evaluator.evaluate_proposals(all_proposals)
            logger.debug(f"Evaluating {len(self.context.proposals)} proposals.")
        except Exception as e:
            logger.error(f"Proposal evaluator failed: {e}")
            self._switch_to_safe_mode()

    def _make_decision(self):
        logger.debug("Making final decision and generating actuator commands...")
        if not self.context.proposals:
            logger.debug("No accepted proposals to make a decision from.")
            return

        # For MVP, take actions from the first accepted proposal
        chosen_proposal = self.context.proposals[0]
        logger.info(f"Decision: Acting on proposal {chosen_proposal.proposal_id.value} from {chosen_proposal.source_module_id}")

        for action in chosen_proposal.proposed_actions:
            try:
                self.bot_core.send_actuator_command(action)
                logger.info(f"Sent actuator command: {action.actuator_id.value} - {action.command_type}")
            except ValueError as e:
                logger.error(f"Failed to send actuator command {action.actuator_id.value}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending command {action.actuator_id.value}: {e}")

    def _switch_to_safe_mode(self):
        logger.warning("Switched to SAFE MODE due to an error.")

    def get_health_snapshot(self) -> Dict[str, Any]:
        """Returns a dictionary with key health metrics of the agent."""
        return {
            "tick_id": self.tick_id,
            "bios_ok": self.context.is_bios_ok(),
            "fsm_state": self.context.fsm_state.current_state if self.context.fsm_state else None,
            "proposals_count": len(self.context.proposals)
        }