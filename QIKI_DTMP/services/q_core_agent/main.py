import argparse
import time
import sys
import os
import yaml
import signal

# Добавляем корневую директорию проекта в sys.path
# Это позволит нам импортировать сгенерированные protobuf файлы
# и другие модули из нашего проекта.
# Важно: путь должен быть абсолютным
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(ROOT_DIR)

from core.agent_logger import setup_logging, logger
from core.agent import QCoreAgent
from core.interfaces import IDataProvider, MockDataProvider, QSimDataProvider
from core.tick_orchestrator import TickOrchestrator

# Import QSimService for direct interaction in MVP
from QIKI_DTMP.services.q_sim_service.main import QSimService

from generated.bios_status_pb2 import BIOSStatus
from generated.fsm_state_pb2 import FSMState
from generated.proposal_pb2 import Proposal
from generated.sensor_raw_in_pb2 import SensorReading
from generated.actuator_raw_out_pb2 import ActuatorCommand
from google.protobuf.json_format import MessageToDict

# --- Mock данные для MockDataProvider ---
_MOCK_BIOS_STATUS = BIOSStatus(is_ok=True, last_error_code=0)
_MOCK_FSM_STATE = FSMState(current_state="IDLE", timestamp=0)
_MOCK_PROPOSALS = [
    Proposal(source="Q_MIND_REFLEX", action="AVOID_OBSTACLE", confidence=0.99),
    Proposal(source="Q_MIND_PLANNER", action="MOVE_TO_TARGET", confidence=0.85)
]
_MOCK_SENSOR_DATA = SensorReading(sensor_id="mock_sensor", scalar_data=1.0)

_MOCK_DATA_PROVIDER = MockDataProvider(
    mock_bios_status=_MOCK_BIOS_STATUS,
    mock_fsm_state=_MOCK_FSM_STATE,
    mock_proposals=_MOCK_PROPOSALS,
    mock_sensor_data=_MOCK_SENSOR_DATA
)

def load_config(path='config.yaml'):
    config_path = os.path.join(os.path.dirname(__file__), path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
            
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Q-Core Agent Main Control.")
    parser.add_argument('--mock', action='store_true', help='Run in mock mode.')
    args = parser.parse_args()

    # Настройка логирования
    log_config_path = os.path.join(os.path.dirname(__file__), 'core', 'logging.yaml')
    setup_logging(default_path=log_config_path)

    # Обработка сигналов завершения
    def handle_shutdown(signum, frame):
        logger.info("Shutdown signal received. Cleaning up...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Загрузка конфигурации
    config = load_config()
    logger.info(f"Loaded config: {config}")
    
    agent = QCoreAgent(config)
    orchestrator = TickOrchestrator(agent, config)

    if args.mock:
        logger.info("Running in MOCK mode.")
        data_provider = _MOCK_DATA_PROVIDER
        try:
            while True:
                orchestrator.run_tick(data_provider)
                logger.info("--- Input Messages (Mock) ---")
                logger.info(f"BIOS: {MessageToDict(data_provider.get_bios_status())}")
                logger.info(f"FSM: {MessageToDict(data_provider.get_fsm_state())}")
                logger.info(f"Proposals: {[MessageToDict(p) for p in data_provider.get_proposals()]}")
                logger.info(f"Sensor: {MessageToDict(data_provider.get_sensor_data())}")
                time.sleep(config.get('tick_interval', 5))
        except KeyboardInterrupt:
            logger.info("Mock run stopped by user.")
    else:
        logger.info("Running in REAL mode (interacting with Q-Sim Service).")
        # Initialize QSimService (for MVP, direct instance)
        qsim_config_path = os.path.join(ROOT_DIR, 'services', 'q_sim_service', 'config.yaml')
        qsim_config = load_config(qsim_config_path) # Reuse load_config for qsim
        qsim_service = QSimService(qsim_config)
        
        # Start QSimService in a separate thread/process if needed for async operation
        # For MVP, we'll assume it's running or its methods are directly callable.

        data_provider = QSimDataProvider(qsim_service)
        try:
            while True:
                orchestrator.run_tick(data_provider)
                logger.info("--- Input Messages (Q-Sim) ---")
                logger.info(f"BIOS: {MessageToDict(data_provider.get_bios_status())}")
                logger.info(f"FSM: {MessageToDict(data_provider.get_fsm_state())}")
                logger.info(f"Proposals: {[MessageToDict(p) for p in data_provider.get_proposals()]}")
                logger.info(f"Sensor: {MessageToDict(data_provider.get_sensor_data())}")
                time.sleep(config.get('tick_interval', 5))
        except KeyboardInterrupt:
            logger.info("Real run stopped by user.")

if __name__ == "__main__":
    main()