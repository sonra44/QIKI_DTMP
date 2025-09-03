import argparse
import time
import sys
import os
import yaml
import signal
import asyncio

# Добавляем корневую директорию проекта в sys.path
# Это позволит нам импортировать сгенерированные protobuf файлы
# и другие модули из нашего проекта.
# Важно: путь должен быть абсолютным
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(ROOT_DIR)

from services.q_core_agent.core.agent_logger import setup_logging, logger
from services.q_core_agent.core.agent import QCoreAgent
from services.q_core_agent.core.interfaces import IDataProvider, MockDataProvider, QSimDataProvider
from services.q_core_agent.core.grpc_data_provider import GrpcDataProvider
from services.q_core_agent.core.tick_orchestrator import TickOrchestrator
from services.q_core_agent.state.store import create_initialized_store

# Import QSimService for direct interaction in MVP
from services.q_sim_service.main import QSimService

from generated.bios_status_pb2 import BiosStatusReport
from generated.fsm_state_pb2 import FsmStateSnapshot
from generated.proposal_pb2 import Proposal
from generated.sensor_raw_in_pb2 import SensorReading
from generated.common_types_pb2 import UUID
from generated.actuator_raw_out_pb2 import ActuatorCommand
from google.protobuf.json_format import MessageToDict
from services.q_core_agent.state.conv import dto_to_proto

# --- Mock данные для MockDataProvider ---
# Создаём реалистичный BIOS статус для тестирования
def _create_mock_bios_status():
    """Создает реалистичный BIOS status report для mock режима"""
    from generated.bios_status_pb2 import DeviceStatus
    from google.protobuf.timestamp_pb2 import Timestamp
    
    bios_report = BiosStatusReport(
        firmware_version="mock_v1.0",
        all_systems_go=True,  # Ключевое исправление!
        health_score=0.95
    )
    
    # Добавляем POST результаты для всех устройств из bot_config.json
    typical_devices = [
        ("motor_left", DeviceStatus.Status.OK, "Motor left operational"),
        ("motor_right", DeviceStatus.Status.OK, "Motor right operational"), 
        ("lidar_front", DeviceStatus.Status.OK, "LIDAR sensor operational"),
        ("imu_main", DeviceStatus.Status.OK, "IMU sensor operational"),
        ("system_controller", DeviceStatus.Status.OK, "System controller operational")
    ]
    
    for device_id, status, message in typical_devices:
        device_status = DeviceStatus(
            device_id=UUID(value=device_id),
            status=status,
            error_message=message,
            status_code=DeviceStatus.StatusCode.STATUS_CODE_UNSPECIFIED
        )
        bios_report.post_results.append(device_status)
    
    # Добавляем timestamp
    timestamp = Timestamp()
    timestamp.GetCurrentTime()
    bios_report.timestamp.CopyFrom(timestamp)
    bios_report.last_checked.CopyFrom(timestamp)
    bios_report.uptime_sec = 42  # Mock uptime
    
    return bios_report

def _create_mock_fsm_state():
    """Создает начальное FSM состояние для mock режима"""
    from generated.fsm_state_pb2 import FSMStateEnum
    from google.protobuf.timestamp_pb2 import Timestamp
    
    fsm_state = FsmStateSnapshot(
        snapshot_id=UUID(value="mock_fsm_001"),
        current_state=FSMStateEnum.BOOTING,  # Начинаем с BOOTING состояния
        fsm_instance_id=UUID(value="main_fsm"),
        source_module="mock_provider",
        attempt_count=1
    )
    
    # Добавляем timestamp
    timestamp = Timestamp()
    timestamp.GetCurrentTime()
    fsm_state.timestamp.CopyFrom(timestamp)
    
    # Добавляем context_data
    fsm_state.context_data["mode"] = "mock"
    fsm_state.context_data["initialized"] = "true"
    
    return fsm_state

_MOCK_BIOS_STATUS = _create_mock_bios_status()
_MOCK_FSM_STATE = _create_mock_fsm_state()
_MOCK_PROPOSALS = [
    Proposal(
        proposal_id=UUID(value="mock_reflex_proposal"),
        source_module_id="Q_MIND_REFLEX",
        confidence=0.99,
        priority=0.8,
        type=Proposal.ProposalType.PLANNING
    ),
    Proposal(
        proposal_id=UUID(value="mock_planner_proposal"),
        source_module_id="Q_MIND_PLANNER", 
        confidence=0.85,
        priority=0.6,
        type=Proposal.ProposalType.PLANNING
    )
]
_MOCK_SENSOR_DATA = SensorReading(sensor_id=UUID(value="mock_sensor"), scalar_data=1.0)

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

async def run_with_statestore(agent, orchestrator, data_provider, config):
    """Async версия основного цикла с StateStore"""
    try:
        while True:
            await orchestrator.run_tick_async(data_provider)
            
            # Логирование из StateStore вместо agent.context
            state_store = orchestrator.state_store
            current_state = await state_store.get()
            
            logger.info("--- Input Messages (StateStore Mode) ---")
            logger.info(f"BIOS: {MessageToDict(data_provider.get_bios_status())}")
            logger.info(f"FSM: {MessageToDict(dto_to_proto(current_state))}")
            logger.info(f"Proposals: {[MessageToDict(p) for p in data_provider.get_proposals()]}")
            logger.info(f"Sensor: {MessageToDict(data_provider.get_sensor_data())}")
            
            await asyncio.sleep(config.get('tick_interval', 5))
    except KeyboardInterrupt:
        logger.info("StateStore run stopped by user.")

def main():
    parser = argparse.ArgumentParser(description="Q-Core Agent Main Control.")
    parser.add_argument('--mock', action='store_true', help='Run in mock mode.')
    parser.add_argument('--grpc', action='store_true', help='Run with gRPC connection to Q-Sim Service.')
    args = parser.parse_args()

    # Настройка логирования
    log_config_path = os.path.join(os.path.dirname(__file__), 'config', 'logging.yaml')
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
    
    # Проверка StateStore флага
    use_statestore = os.environ.get('QIKI_USE_STATESTORE', 'false').lower() == 'true'
    
    agent = QCoreAgent(config)
    
    # Создание StateStore если включён
    state_store = None
    if use_statestore:
        logger.info("QIKI_USE_STATESTORE=true - включён StateStore режим")
        state_store = create_initialized_store()
    
    orchestrator = TickOrchestrator(agent, config, state_store=state_store)

    if args.mock:
        logger.info("Running in MOCK mode.")
        data_provider = _MOCK_DATA_PROVIDER
        
        if use_statestore:
            # Async режим с StateStore
            asyncio.run(run_with_statestore(agent, orchestrator, data_provider, config))
        else:
            # Legacy sync режим
            try:
                while True:
                    orchestrator.run_tick(data_provider)
                    logger.info("--- Input Messages (Mock) ---")
                    logger.info(f"BIOS: {MessageToDict(data_provider.get_bios_status())}")
                    logger.info(f"FSM: {MessageToDict(agent.context.fsm_state)}")
                    logger.info(f"Proposals: {[MessageToDict(p) for p in data_provider.get_proposals()]}")
                    logger.info(f"Sensor: {MessageToDict(data_provider.get_sensor_data())}")
                    time.sleep(config.get('tick_interval', 5))
            except KeyboardInterrupt:
                logger.info("Mock run stopped by user.")
    elif args.grpc:
        logger.info("Running in GRPC mode (connecting to Q-Sim Service via gRPC).")
        grpc_address = config.get('grpc_server_address', 'localhost:50051')
        data_provider = GrpcDataProvider(grpc_address)
        
        if use_statestore:
            # Async режим с StateStore
            asyncio.run(run_with_statestore(agent, orchestrator, data_provider, config))
        else:
            # Legacy sync режим
            try:
                while True:
                    orchestrator.run_tick(data_provider)
                    logger.info("--- Input Messages (gRPC) ---")
                    logger.info(f"BIOS: {MessageToDict(data_provider.get_bios_status())}")
                    logger.info(f"FSM: {MessageToDict(agent.context.fsm_state)}")
                    logger.info(f"Proposals: {[MessageToDict(p) for p in data_provider.get_proposals()]}")
                    logger.info(f"Sensor: {MessageToDict(data_provider.get_sensor_data())}")
                    time.sleep(config.get('tick_interval', 5))
            except KeyboardInterrupt:
                logger.info("gRPC run stopped by user.")
    else:
        logger.info("Running in LEGACY mode (direct Q-Sim Service instance).")
        # Initialize QSimService (for MVP, direct instance)
        qsim_config_path = os.path.join(ROOT_DIR, 'services', 'q_sim_service', 'config.yaml')
        qsim_config = load_config(qsim_config_path) # Reuse load_config for qsim
        qsim_service = QSimService(qsim_config)
        
        # Start QSimService in a separate thread/process if needed for async operation
        # For MVP, we'll assume it's running or its methods are directly callable.

        data_provider = QSimDataProvider(qsim_service)
        
        if use_statestore:
            # Async режим с StateStore
            asyncio.run(run_with_statestore(agent, orchestrator, data_provider, config))
        else:
            # Legacy sync режим
            try:
                while True:
                    orchestrator.run_tick(data_provider)
                    logger.info("--- Input Messages (Legacy) ---")
                    logger.info(f"BIOS: {MessageToDict(data_provider.get_bios_status())}")
                    logger.info(f"FSM: {MessageToDict(agent.context.fsm_state)}")
                    logger.info(f"Proposals: {[MessageToDict(p) for p in data_provider.get_proposals()]}")
                    logger.info(f"Sensor: {MessageToDict(data_provider.get_sensor_data())}")
                    time.sleep(config.get('tick_interval', 5))
            except KeyboardInterrupt:
                logger.info("Legacy run stopped by user.")

if __name__ == "__main__":
    main()