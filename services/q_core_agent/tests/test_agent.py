
import pytest
from unittest.mock import Mock

import os
import json
import tempfile

from ..core.agent import QCoreAgent, AgentContext
from ..core.bot_core import BotCore
from ..core.interfaces import IDataProvider, IProposalEvaluator, IRuleEngine, INeuralEngine
from ..core.fsm_handler import FSMHandler
from ..core.proposal_evaluator import ProposalEvaluator
from ..core.tick_orchestrator import TickOrchestrator
from ..core.rule_engine import RuleEngine
from ..core.neural_engine import NeuralEngine
from generated.bios_status_pb2 import BiosStatusReport
from generated.fsm_state_pb2 import FsmStateSnapshot, FSMStateEnum
from generated.proposal_pb2 import Proposal

@pytest.fixture
def mock_data_provider():
    # Создаём реалистичный BIOS статус (может быть False)
    mock_bios = BiosStatusReport()  # По умолчанию all_systems_go=False
    mock_fsm = FsmStateSnapshot()
    mock_proposals = [
        Proposal(source_module_id="test", confidence=0.9)
    ]

    provider = Mock(spec=IDataProvider)
    provider.get_bios_status.return_value = mock_bios
    provider.get_fsm_state.return_value = mock_fsm
    provider.get_proposals.return_value = mock_proposals
    return provider

def test_qcoreagent_initialization():
    config = {"test_key": "test_value"}
    agent = QCoreAgent(config)
    assert agent.config == config
    assert isinstance(agent.context, AgentContext)
    assert agent.tick_id == 0

def test_qcoreagent_run_tick_updates_context(mock_data_provider):
    config = {"test_key": "test_value"}
    agent = QCoreAgent(config)

    agent.run_tick(mock_data_provider)

    assert agent.tick_id == 1
    
    # BIOS status is processed by BIOS handler, so it's a new object
    assert agent.context.bios_status is not None
    assert isinstance(agent.context.bios_status, BiosStatusReport)
    
    # FSM state is processed by FSM handler, so it's a new object  
    assert agent.context.fsm_state is not None
    assert isinstance(agent.context.fsm_state, FsmStateSnapshot)
    
    # Proposals are evaluated, so they may be filtered/modified
    assert agent.context.proposals is not None
    assert isinstance(agent.context.proposals, list)

    mock_data_provider.get_bios_status.assert_called_once()
    mock_data_provider.get_fsm_state.assert_called_once()
    mock_data_provider.get_proposals.assert_called_once()

def test_qcoreagent_handle_bios_error_safe_mode(mock_data_provider):
    config = {"test_key": "test_value"}
    agent = QCoreAgent(config)

    # Simulate an error in BIOS handling
    agent._handle_bios = Mock(side_effect=Exception("BIOS error"))
    agent._switch_to_safe_mode = Mock()

    agent.run_tick(mock_data_provider)

    agent._handle_bios.assert_called_once()
    agent._switch_to_safe_mode.assert_called_once()

def test_qcoreagent_handle_fsm_error_safe_mode(mock_data_provider):
    config = {"test_key": "test_value"}
    agent = QCoreAgent(config)

    # Simulate an error in FSM handling
    agent._handle_fsm = Mock(side_effect=Exception("FSM error"))
    agent._switch_to_safe_mode = Mock()

    agent.run_tick(mock_data_provider)

    agent._handle_fsm.assert_called_once()
    agent._switch_to_safe_mode.assert_called_once()

def test_qcoreagent_evaluate_proposals_error_safe_mode(mock_data_provider):
    config = {"test_key": "test_value"}
    agent = QCoreAgent(config)

    # Simulate an error in proposal evaluation
    agent._evaluate_proposals = Mock(side_effect=Exception("Proposals error"))
    agent._switch_to_safe_mode = Mock()

    agent.run_tick(mock_data_provider)

    agent._evaluate_proposals.assert_called_once()
    agent._switch_to_safe_mode.assert_called_once()

def test_bot_id_generated(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a dummy config directory and file
        config_dir = os.path.join(tmpdir, "config")
        os.makedirs(config_dir)
        dummy_config_content = {"mode": "full"}
        with open(os.path.join(config_dir, "bot_config.json"), "w") as f:
            json.dump(dummy_config_content, f)

        monkeypatch.setenv("QIKI_BOT_INIT_TIMESTAMP", "20250724123456")
        bot = BotCore(base_path=tmpdir)
        
        assert bot.get_id().startswith("QIKI-20250724")
        assert len(bot.get_id()) == len("QIKI-YYYYMMDD-XXXXXXXX")

        # Verify ID persistence
        bot2 = BotCore(base_path=tmpdir)
        assert bot.get_id() == bot2.get_id()

def test_fsm_handler_initial_state_transition():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=True)  # Specific test case needs healthy BIOS
    
    fsm_handler = FSMHandler(context)
    initial_state = FsmStateSnapshot(current_state=FSMStateEnum.BOOTING)
    
    new_state = fsm_handler.process_fsm_state(initial_state)
    
    assert new_state.current_state == FSMStateEnum.IDLE
    assert len(new_state.history) == 1
    assert new_state.history[0].from_state == FSMStateEnum.BOOTING
    assert new_state.history[0].to_state == FSMStateEnum.IDLE
    assert new_state.history[0].trigger_event == "BOOT_COMPLETE"

def test_fsm_handler_booting_to_error_on_bios_fail():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=False) # Simulate BIOS failure
    
    fsm_handler = FSMHandler(context)
    initial_state = FsmStateSnapshot(current_state=FSMStateEnum.BOOTING)
    
    new_state = fsm_handler.process_fsm_state(initial_state)
    
    assert new_state.current_state == FSMStateEnum.ERROR_STATE
    assert len(new_state.history) == 1
    assert new_state.history[0].from_state == FSMStateEnum.BOOTING
    assert new_state.history[0].to_state == FSMStateEnum.ERROR_STATE
    assert new_state.history[0].trigger_event == "BIOS_ERROR"

def test_fsm_handler_idle_to_active_on_proposals():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=True)  # Specific test case needs healthy BIOS
    context.proposals.append(Proposal(source_module_id="test")) # Simulate a proposal
    
    fsm_handler = FSMHandler(context)
    initial_state = FsmStateSnapshot(current_state=FSMStateEnum.IDLE)
    
    new_state = fsm_handler.process_fsm_state(initial_state)
    
    assert new_state.current_state == FSMStateEnum.ACTIVE
    assert len(new_state.history) == 1
    assert new_state.history[0].from_state == FSMStateEnum.IDLE
    assert new_state.history[0].to_state == FSMStateEnum.ACTIVE
    assert new_state.history[0].trigger_event == "PROPOSALS_RECEIVED"

def test_fsm_handler_active_to_idle_on_no_proposals():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=True)  # Specific test case needs healthy BIOS
    context.proposals = [] # No proposals
    
    fsm_handler = FSMHandler(context)
    initial_state = FsmStateSnapshot(current_state=FSMStateEnum.ACTIVE)
    
    new_state = fsm_handler.process_fsm_state(initial_state)
    
    assert new_state.current_state == FSMStateEnum.IDLE
    assert len(new_state.history) == 1
    assert new_state.history[0].from_state == FSMStateEnum.ACTIVE
    assert new_state.history[0].to_state == FSMStateEnum.IDLE
    assert new_state.history[0].trigger_event == "NO_PROPOSALS"

def test_fsm_handler_error_to_idle_on_recovery():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=True)  # Specific test case needs healthy BIOS
    context.proposals = [] # No proposals
    
    fsm_handler = FSMHandler(context)
    initial_state = FsmStateSnapshot(current_state=FSMStateEnum.ERROR_STATE)
    
    new_state = fsm_handler.process_fsm_state(initial_state)
    
    assert new_state.current_state == FSMStateEnum.IDLE
    assert len(new_state.history) == 1
    assert new_state.history[0].from_state == FSMStateEnum.ERROR_STATE
    assert new_state.history[0].to_state == FSMStateEnum.IDLE
    assert new_state.history[0].trigger_event == "ERROR_CLEARED"


# Tests for ProposalEvaluator
def test_proposal_evaluator_no_proposals():
    evaluator = ProposalEvaluator({})
    accepted = evaluator.evaluate_proposals([])
    assert len(accepted) == 0

def test_proposal_evaluator_low_confidence_proposals():
    evaluator = ProposalEvaluator({})
    proposals = [
        Proposal(source_module_id="test", confidence=0.4),
        Proposal(source_module_id="test", confidence=0.5)
    ]
    accepted = evaluator.evaluate_proposals(proposals)
    assert len(accepted) == 0

def test_proposal_evaluator_high_confidence_proposals():
    evaluator = ProposalEvaluator({})
    proposals = [
        Proposal(source_module_id="test1", confidence=0.7, type=Proposal.ProposalType.PLANNING, priority=0.5),
        Proposal(source_module_id="test2", confidence=0.9, type=Proposal.ProposalType.PLANNING, priority=0.8)
    ]
    accepted = evaluator.evaluate_proposals(proposals)
    assert len(accepted) == 1
    assert accepted[0].source_module_id == "test2" # Higher priority/confidence

def test_proposal_evaluator_priority_selection():
    evaluator = ProposalEvaluator({})
    proposals = [
        Proposal(source_module_id="low_prio", confidence=0.9, type=Proposal.ProposalType.PLANNING, priority=0.1),
        Proposal(source_module_id="high_prio", confidence=0.7, type=Proposal.ProposalType.SAFETY, priority=0.9)
    ]
    accepted = evaluator.evaluate_proposals(proposals)
    assert len(accepted) == 1
    assert accepted[0].source_module_id == "high_prio" # SAFETY type has lower enum value but higher logical priority

def test_proposal_evaluator_same_priority_different_confidence():
    evaluator = ProposalEvaluator({})
    proposals = [
        Proposal(source_module_id="conf_07", confidence=0.7, type=Proposal.ProposalType.PLANNING, priority=0.5),
        Proposal(source_module_id="conf_08", confidence=0.8, type=Proposal.ProposalType.PLANNING, priority=0.5)
    ]
    accepted = evaluator.evaluate_proposals(proposals)
    assert len(accepted) == 1
    assert accepted[0].source_module_id == "conf_08" # Higher confidence selected


# Tests for RuleEngine
def test_rule_engine_generates_safe_mode_proposal_on_bios_error():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=False) # Simulate BIOS error
    
    rule_engine = RuleEngine(context, {})
    proposals = rule_engine.generate_proposals(context)
    
    assert len(proposals) == 1
    assert proposals[0].source_module_id == "rule_engine"
    assert proposals[0].type == Proposal.ProposalType.SAFETY
    assert abs(proposals[0].priority - 0.99) < 0.001  # Float precision tolerance
    assert proposals[0].confidence == 1.0
    assert proposals[0].justification == "BIOS reported critical errors. Entering safe mode."
    assert len(proposals[0].proposed_actions) == 1
    # Import the protobuf enum for proper comparison
    from generated.actuator_raw_out_pb2 import ActuatorCommand
    assert proposals[0].proposed_actions[0].command_type == ActuatorCommand.CommandType.SET_MODE
    # RuleEngine uses ERROR_STATE for SAFE_MODE (value 4)
    from generated.fsm_state_pb2 import FSMStateEnum
    assert proposals[0].proposed_actions[0].int_value == FSMStateEnum.ERROR_STATE

def test_rule_engine_no_proposal_on_bios_ok():
    context = AgentContext()
    context.bios_status = BiosStatusReport(all_systems_go=True)  # Specific test case needs healthy BIOS # BIOS is OK
    
    rule_engine = RuleEngine(context, {})
    proposals = rule_engine.generate_proposals(context)
    
    assert len(proposals) == 0


# Tests for NeuralEngine
def test_neural_engine_generates_mock_proposal_when_enabled():
    context = AgentContext()
    config = {"mock_neural_proposals_enabled": True}
    neural_engine = NeuralEngine(context, config)
    proposals = neural_engine.generate_proposals(context)
    
    assert len(proposals) == 1
    assert proposals[0].source_module_id == "neural_engine_mock"
    assert proposals[0].type == Proposal.ProposalType.PLANNING
    assert proposals[0].confidence == pytest.approx(0.7)

def test_neural_engine_generates_no_proposal_when_disabled():
    context = AgentContext()
    config = {"mock_neural_proposals_enabled": False}
    neural_engine = NeuralEngine(context, config)
    proposals = neural_engine.generate_proposals(context)
    
    assert len(proposals) == 0


# Tests for TickOrchestrator
def test_tick_orchestrator_runs_agent_methods(mock_data_provider):
    mock_agent = Mock(spec=QCoreAgent)
    mock_agent.tick_id = 0
    mock_agent.context = AgentContext()
    mock_agent.config = {"recovery_delay": 0}
    mock_agent._switch_to_safe_mode = Mock()

    orchestrator = TickOrchestrator(mock_agent, mock_agent.config)
    orchestrator.run_tick(mock_data_provider)

    mock_agent._update_context.assert_called_once_with(mock_data_provider)
    mock_agent._handle_bios.assert_called_once()
    mock_agent._handle_fsm.assert_called_once()
    mock_agent._evaluate_proposals.assert_called_once()
    mock_agent._make_decision.assert_called_once()
    assert mock_agent.tick_id == 1

def test_tick_orchestrator_handles_exception_and_recovers(mock_data_provider):
    mock_agent = Mock(spec=QCoreAgent)
    mock_agent.tick_id = 0
    mock_agent.context = AgentContext()
    mock_agent.config = {"recovery_delay": 0.01} # Small delay for test
    mock_agent._switch_to_safe_mode = Mock()

    # Simulate an exception during _handle_bios
    mock_agent._handle_bios.side_effect = Exception("Simulated BIOS error")

    orchestrator = TickOrchestrator(mock_agent, mock_agent.config)
    orchestrator.run_tick(mock_data_provider)

    mock_agent._handle_bios.assert_called_once()
    mock_agent._switch_to_safe_mode.assert_called_once()
    # Verify that other methods after the error were not called
    mock_agent._handle_fsm.assert_not_called()
    mock_agent._evaluate_proposals.assert_not_called()
    mock_agent._make_decision.assert_not_called()
    assert mock_agent.tick_id == 1

