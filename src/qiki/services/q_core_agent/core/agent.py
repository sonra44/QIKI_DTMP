from typing import Optional, Dict, Any, TYPE_CHECKING, List
import time
from qiki.services.q_core_agent.core.agent_logger import logger
from qiki.services.q_core_agent.core.interfaces import (
    IDataProvider,
    IBiosHandler,
    IFSMHandler,
    IProposalEvaluator,
    IRuleEngine,
    INeuralEngine,
)
from qiki.services.q_core_agent.core.bot_core import BotCore

# Импортируем сгенерированные Protobuf классы
from qiki.shared.models.core import (
    BiosStatus,
    FsmStateSnapshot as PydanticFsmStateSnapshot,
    Proposal,
    SensorData,
)

import os
from qiki.services.q_core_agent.core.bios_handler import BiosHandler
from qiki.services.q_core_agent.core.fsm_handler import FSMHandler
from qiki.services.q_core_agent.core.proposal_evaluator import ProposalEvaluator
from qiki.services.q_core_agent.core.tick_orchestrator import TickOrchestrator
from qiki.services.q_core_agent.core.rule_engine import RuleEngine
from qiki.services.q_core_agent.core.neural_engine import NeuralEngine
from qiki.services.q_core_agent.core.guard_table import GuardEvaluationResult, load_guard_table
from qiki.services.q_core_agent.core.world_model import WorldModel

if TYPE_CHECKING:
    from qiki.shared.config_models import QCoreAgentConfig


_SHIP_STATE_CONTEXT_KEY = "ship_state_name"
_SAFE_MODE_STATE_NAME = "SAFE_MODE"
_SAFE_MODE_REASON_KEY = "safe_mode_reason"
_SAFE_MODE_REQUEST_REASON_KEY = "safe_mode_request_reason"
_SAFE_MODE_BIOS_OK_KEY = "safe_bios_ok"
_SAFE_MODE_SENSORS_OK_KEY = "safe_sensors_ok"
_SAFE_MODE_PROVIDER_OK_KEY = "safe_provider_ok"
_LAST_ACTUATION_COMMAND_ID_KEY = "last_actuation_command_id"
_LAST_ACTUATION_STATUS_KEY = "last_actuation_status"
_LAST_ACTUATION_TIMESTAMP_KEY = "last_actuation_timestamp"
_LAST_ACTUATION_REASON_KEY = "last_actuation_reason"
_LAST_ACTUATION_IS_FALLBACK_KEY = "last_actuation_is_fallback"


class AgentContext:
    def __init__(
        self,
        bios_status: Optional[BiosStatus] = None,
        fsm_state: Optional[PydanticFsmStateSnapshot] = None,
        proposals: Optional[list[Proposal]] = None,
    ):
        self.bios_status = bios_status
        self.fsm_state = fsm_state
        self.proposals = proposals if proposals is not None else []
        self.latest_sensor_data: Optional[SensorData] = None
        self.last_actuation: Dict[str, Any] = {}
        self.guard_events: List[GuardEvaluationResult] = []
        self.world_snapshot: Dict[str, Any] = {}

    def update_from_provider(self, data_provider: IDataProvider):
        self.bios_status = data_provider.get_bios_status()
        if self.fsm_state is None:
            fsm_result = data_provider.get_fsm_state_result()
            if not fsm_result.ok:
                if fsm_result.is_fallback and fsm_result.value is not None:
                    self.fsm_state = fsm_result.value
                    logger.warning(f"FSM interface fallback used: {fsm_result.reason}")
                else:
                    raise RuntimeError(f"FSM interface returned no truth data: {fsm_result.reason}")
            elif fsm_result.value is None:
                raise RuntimeError("FSM interface returned ok=True but value=None")
            else:
                self.fsm_state = fsm_result.value
        self.proposals = data_provider.get_proposals()
        logger.debug("AgentContext updated from data provider.")

    def update_from_provider_without_fsm(self, data_provider: IDataProvider):
        """Обновляет контекст без FSM состояния (при StateStore режиме)"""
        self.bios_status = data_provider.get_bios_status()
        # НЕ обновляем self.fsm_state - оно берётся из StateStore
        self.proposals = data_provider.get_proposals()
        logger.debug("AgentContext updated from data provider (without FSM).")

    def is_bios_ok(self) -> bool:
        return self.bios_status is not None and self.bios_status.all_systems_go

    def has_valid_proposals(self) -> bool:
        return bool(self.proposals)


class QCoreAgent:
    def __init__(self, config: "QCoreAgentConfig"):
        self.config = config
        self.context = AgentContext()
        self.tick_id = 0

        # Initialize BotCore (assuming base_path is the q_core_agent directory)
        q_core_agent_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.bot_core = BotCore(base_path=q_core_agent_root)

        self.guard_table = load_guard_table()
        self.world_model = WorldModel(self.guard_table)

        # Initialize handlers
        self.bios_handler: IBiosHandler = BiosHandler(self.bot_core)
        self.fsm_handler: IFSMHandler = FSMHandler(self.context, world_model=self.world_model)
        self.proposal_evaluator: IProposalEvaluator = ProposalEvaluator(config)
        self.rule_engine: IRuleEngine = RuleEngine(self.context, config)
        self.neural_engine: INeuralEngine = NeuralEngine(self.context, config)

        # Initialize TickOrchestrator
        self.orchestrator = TickOrchestrator(self, config)

        logger.info("QCoreAgent initialized.")

    def _update_context(self, data_provider: IDataProvider):
        try:
            self.context.update_from_provider(data_provider)
        except Exception:
            self._set_fsm_context_flag(_SAFE_MODE_PROVIDER_OK_KEY, False)
            self._switch_to_safe_mode(reason="PROVIDER_UNAVAILABLE")
            raise
        self._set_fsm_context_flag(_SAFE_MODE_PROVIDER_OK_KEY, True)
        self._ingest_sensor_data(data_provider)

    def _update_context_without_fsm(self, data_provider: IDataProvider):
        """Обновляет контекст без FSM (для StateStore режима)"""
        self.context.update_from_provider_without_fsm(data_provider)
        self._set_fsm_context_flag(_SAFE_MODE_PROVIDER_OK_KEY, True)
        self._ingest_sensor_data(data_provider)

    def _ingest_sensor_data(self, data_provider: IDataProvider) -> None:
        try:
            sensor_data = data_provider.get_sensor_data()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to fetch sensor data: {exc}")
            self._set_fsm_context_flag(_SAFE_MODE_SENSORS_OK_KEY, False)
            self._switch_to_safe_mode(reason="SENSORS_UNAVAILABLE")
            return

        if sensor_data is None:
            self._set_fsm_context_flag(_SAFE_MODE_SENSORS_OK_KEY, False)
            return

        self._set_fsm_context_flag(_SAFE_MODE_SENSORS_OK_KEY, True)
        self.context.latest_sensor_data = sensor_data
        try:
            self.bot_core.ingest_sensor_data(sensor_data)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"BotCore sensor ingest failed: {exc}")

        self.world_model.ingest_sensor_data(sensor_data)
        self.context.guard_events = self.world_model.guard_results()
        self.context.world_snapshot = self.world_model.snapshot()

    def run_tick(self, data_provider: IDataProvider):
        self.orchestrator.run_tick(data_provider)

    def _handle_bios(self):
        try:
            # Prefer explicit result contract when BIOS handler supports it.
            if hasattr(self.bios_handler, "process_bios_status_result"):
                bios_result = self.bios_handler.process_bios_status_result(self.context.bios_status)
                if not bios_result.ok or bios_result.report is None:
                    logger.error(f"BIOS handler returned no data: {bios_result.reason}")
                    self._set_fsm_context_flag(_SAFE_MODE_BIOS_OK_KEY, False)
                    reason = "BIOS_INVALID" if str(bios_result.reason).upper().endswith("INVALID") else "BIOS_UNAVAILABLE"
                    self._switch_to_safe_mode(reason=reason)
                    return
                self.context.bios_status = bios_result.report
                self._set_fsm_context_flag(_SAFE_MODE_BIOS_OK_KEY, bool(getattr(bios_result.report, "all_systems_go", False)))
                if bios_result.is_fallback:
                    logger.warning(f"BIOS handler returned fallback report: {bios_result.reason}")
            else:
                self.context.bios_status = self.bios_handler.process_bios_status(self.context.bios_status)
                self._set_fsm_context_flag(
                    _SAFE_MODE_BIOS_OK_KEY, bool(getattr(self.context.bios_status, "all_systems_go", False))
                )
            logger.debug(f"Handling BIOS status: {self.context.bios_status}")
        except Exception as e:
            logger.error(f"BIOS handler failed: {e}")
            self._set_fsm_context_flag(_SAFE_MODE_BIOS_OK_KEY, False)
            self._switch_to_safe_mode(reason="BIOS_UNAVAILABLE")

    def _handle_fsm(self):
        try:
            self.context.fsm_state = self.fsm_handler.process_fsm_state(self.context.fsm_state)
            logger.debug(f"Handling FSM state: {self.context.fsm_state}")
        except Exception as e:
            logger.error(f"FSM handler failed: {e}")
            self._switch_to_safe_mode(reason="UNKNOWN")

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
            self._switch_to_safe_mode(reason="UNKNOWN")

    def _make_decision(self, data_provider: Optional[IDataProvider] = None):
        logger.debug("Making final decision and generating actuator commands...")
        if self._is_fsm_in_safe_mode():
            logger.warning("SAFE_MODE active: blocking active actuator commands")
            return
        if not self.context.proposals:
            logger.debug("No accepted proposals to make a decision from.")
            return

        # For MVP, take actions from the first accepted proposal
        chosen_proposal = self.context.proposals[0]
        logger.info(
            f"Decision: Acting on proposal {chosen_proposal.proposal_id} from {chosen_proposal.source_module_id}"
        )

        for action in chosen_proposal.proposed_actions:
            command_id = str(getattr(getattr(action, "command_id", None), "value", "") or "")
            try:
                self.bot_core.send_actuator_command(action)
                if data_provider is not None:
                    data_provider.send_actuator_command(action)
                self._record_last_actuation(
                    status="accepted",
                    reason="COMMAND_ACCEPTED_NO_EXECUTION_ACK",
                    command_id=command_id,
                    is_fallback=False,
                )
                logger.info(f"Sent actuator command: {action.actuator_id} - {action.command_type.name}")
            except TimeoutError as e:
                self._record_last_actuation(status="timeout", reason=str(e), command_id=command_id, is_fallback=False)
                self._switch_to_safe_mode(reason="ACTUATOR_UNAVAILABLE")
                logger.error(f"Actuator timeout for command {action.actuator_id}: {e}")
            except ConnectionError as e:
                self._record_last_actuation(status="unavailable", reason=str(e), command_id=command_id, is_fallback=False)
                self._switch_to_safe_mode(reason="ACTUATOR_UNAVAILABLE")
                logger.error(f"Actuator unavailable for command {action.actuator_id}: {e}")
            except ValueError as e:
                self._record_last_actuation(status="rejected", reason=str(e), command_id=command_id, is_fallback=False)
                logger.error(f"Failed to send actuator command {action.actuator_id}: {e}")
            except Exception as e:
                self._record_last_actuation(status="failed", reason=str(e), command_id=command_id, is_fallback=False)
                self._switch_to_safe_mode(reason="ACTUATOR_UNAVAILABLE")
                logger.error(f"Unexpected error sending command {action.actuator_id}: {e}")

    def _switch_to_safe_mode(self, reason: str = "UNKNOWN"):
        safe_reason = str(reason or "UNKNOWN").strip().upper() or "UNKNOWN"
        logger.warning(f"Switched to SAFE MODE due to: {safe_reason}")
        fsm_state = self.context.fsm_state
        if fsm_state is None or not hasattr(fsm_state, "context_data"):
            return
        try:
            fsm_state.context_data[_SAFE_MODE_REQUEST_REASON_KEY] = safe_reason
            fsm_state.context_data[_SAFE_MODE_REASON_KEY] = safe_reason
        except Exception:
            return
        try:
            self.context.fsm_state = self.fsm_handler.process_fsm_state(fsm_state)
        except Exception as exc:
            logger.debug(f"SAFE_MODE transition request failed: {exc}")

    def _record_last_actuation(
        self,
        *,
        status: str,
        reason: str,
        command_id: str,
        is_fallback: bool = False,
    ) -> None:
        payload = {
            "command_id": str(command_id or ""),
            "status": str(status or "").lower(),
            "timestamp": float(time.time()),
            "reason": str(reason or ""),
            "is_fallback": bool(is_fallback),
        }
        self.context.last_actuation = payload
        fsm_state = self.context.fsm_state
        if fsm_state is None or not hasattr(fsm_state, "context_data"):
            return
        try:
            fsm_state.context_data[_LAST_ACTUATION_COMMAND_ID_KEY] = payload["command_id"]
            fsm_state.context_data[_LAST_ACTUATION_STATUS_KEY] = payload["status"]
            fsm_state.context_data[_LAST_ACTUATION_TIMESTAMP_KEY] = f"{payload['timestamp']:.6f}"
            fsm_state.context_data[_LAST_ACTUATION_REASON_KEY] = payload["reason"]
            fsm_state.context_data[_LAST_ACTUATION_IS_FALLBACK_KEY] = "1" if payload["is_fallback"] else "0"
        except Exception:
            logger.debug("Failed to update last actuation context", exc_info=True)

    def _set_fsm_context_flag(self, key: str, value: bool) -> None:
        fsm_state = self.context.fsm_state
        if fsm_state is None or not hasattr(fsm_state, "context_data"):
            return
        try:
            fsm_state.context_data[key] = "1" if value else "0"
        except Exception:
            logger.debug("Failed to update FSM context flag", exc_info=True)

    def _is_fsm_in_safe_mode(self) -> bool:
        fsm_state = self.context.fsm_state
        if fsm_state is None or not hasattr(fsm_state, "context_data"):
            return False
        try:
            return str(fsm_state.context_data.get(_SHIP_STATE_CONTEXT_KEY, "")) == _SAFE_MODE_STATE_NAME
        except Exception:
            return False

    def get_health_snapshot(self) -> Dict[str, Any]:
        """Returns a dictionary with key health metrics of the agent."""
        return {
            "tick_id": self.tick_id,
            "bios_ok": self.context.is_bios_ok(),
            "fsm_state": self.context.fsm_state.current_state.name if self.context.fsm_state else None,
            "proposals_count": len(self.context.proposals),
        }
