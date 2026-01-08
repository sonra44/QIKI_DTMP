import argparse
import time
import sys
import os
import signal
import asyncio
from pathlib import Path

from qiki.services.q_core_agent.core.agent_logger import setup_logging, logger
from qiki.services.q_core_agent.intent_bridge import start_intent_bridge_in_thread
from qiki.services.q_core_agent.core.agent import QCoreAgent
from qiki.services.q_core_agent.core.interfaces import (
    MockDataProvider,
    QSimDataProvider,
)
from qiki.services.q_core_agent.core.grpc_data_provider import GrpcDataProvider
from qiki.services.q_core_agent.core.tick_orchestrator import TickOrchestrator
from qiki.services.q_core_agent.state.store import create_initialized_store
from qiki.services.q_core_agent.state.conv import dto_to_protobuf_json
from qiki.shared.config_models import QCoreAgentConfig, QSimServiceConfig, load_config
import json

# Import QSimService for direct interaction in MVP
from qiki.services.q_sim_service.service import QSimService

from qiki.shared.models.core import (
    BiosStatus,
    DeviceStatus,
    FsmStateSnapshot as PydanticFsmStateSnapshot,
    Proposal,
    SensorData,
    ProposalTypeEnum,
    DeviceStatusEnum,
    FsmStateEnum,
    SensorTypeEnum,
)
from uuid import uuid4
from datetime import datetime, UTC


# --- Mock данные для MockDataProvider ---
# Создаём реалистичный BIOS статус для тестирования
def _create_mock_bios_status():
    """Создает реалистичный BIOS status report для mock режима"""
    bios_report = BiosStatus(
        bios_version="mock_v1.0",
        firmware_version="mock_v1.0",
        post_results=[],
        timestamp=datetime.now(UTC),
    )

    # Добавляем POST результаты для всех устройств из bot_config.json
    typical_devices = [
        ("motor_left", "Left Motor", DeviceStatusEnum.OK, "Motor left operational"),
        ("motor_right", "Right Motor", DeviceStatusEnum.OK, "Motor right operational"),
        ("system_controller", "System Controller", DeviceStatusEnum.OK, "System controller operational"),
        ("lidar_front", "Front LIDAR", DeviceStatusEnum.OK, "LIDAR sensor operational"),
        ("imu_main", "Main IMU", DeviceStatusEnum.OK, "IMU sensor operational"),
        ("sensor_imu", "IMU Sensor", DeviceStatusEnum.OK, "IMU sensor operational"),
        ("sensor_thermal", "Thermal Sensors", DeviceStatusEnum.OK, "Thermal sensors operational"),
        ("sensor_radiation", "Radiation Sensors", DeviceStatusEnum.OK, "Radiation sensors operational"),
        ("sensor_docking", "Docking Sensors", DeviceStatusEnum.OK, "Docking sensors operational"),
        ("sensor_proximity", "Proximity Sensors", DeviceStatusEnum.OK, "Proximity sensors operational"),
        ("sensor_solar", "Solar Sensor", DeviceStatusEnum.OK, "Solar sensor operational"),
        ("sensor_star_tracker", "Star Tracker", DeviceStatusEnum.OK, "Star tracker operational"),
        ("radar_360", "Radar 360", DeviceStatusEnum.OK, "Radar operational"),
        ("lidar", "Lidar", DeviceStatusEnum.OK, "Lidar operational"),
        ("spectrometer", "Spectrometer", DeviceStatusEnum.OK, "Spectrometer operational"),
        ("magnetometer", "Magnetometer", DeviceStatusEnum.OK, "Magnetometer operational"),
    ]

    for device_id, device_name, status, message in typical_devices:
        device_status = DeviceStatus(
            device_id=device_id,
            device_name=device_name,
            status=status,
            status_message=message,
        )
        bios_report.post_results.append(device_status)

    return bios_report


def _create_mock_fsm_state():
    """Создает начальное FSM состояние для mock режима"""
    fsm_state = PydanticFsmStateSnapshot(
        current_state=FsmStateEnum.BOOTING,  # Начинаем с BOOTING состояния
        previous_state=FsmStateEnum.OFFLINE,
        context_data={"mode": "mock", "initialized": "true"},
        snapshot_id=uuid4(),  # Use uuid4() to generate a valid UUID
        fsm_instance_id=uuid4(),  # Use uuid4() to generate a valid UUID
        source_module="mock_provider",
        attempt_count=1,
        ts_wall=time.time(),
    )

    return fsm_state


_MOCK_BIOS_STATUS = _create_mock_bios_status()
_MOCK_FSM_STATE = _create_mock_fsm_state()
_MOCK_PROPOSALS = [
    Proposal(
        proposal_id=uuid4(),  # Use uuid4() to generate a valid UUID
        source_module_id="Q_MIND_REFLEX",
        confidence=0.99,
        priority=0.8,
        type=ProposalTypeEnum.PLANNING,
        justification="Mock reflex proposal justification.",
    ),
    Proposal(
        proposal_id=uuid4(),  # Use uuid4() to generate a valid UUID
        source_module_id="Q_MIND_PLANNER",
        confidence=0.85,
        priority=0.6,
        type=ProposalTypeEnum.PLANNING,
        justification="Mock planner proposal justification.",
    ),
]
_MOCK_SENSOR_DATA = SensorData(
    sensor_id=str(uuid4()),
    sensor_type=SensorTypeEnum.OTHER,
    scalar_data=1.0,
    quality_score=1.0,
)

_MOCK_DATA_PROVIDER = MockDataProvider(
    mock_bios_status=_MOCK_BIOS_STATUS,
    mock_fsm_state=_MOCK_FSM_STATE,
    mock_proposals=_MOCK_PROPOSALS,
    mock_sensor_data=_MOCK_SENSOR_DATA,
)


async def run_with_statestore(
    agent, orchestrator, data_provider, config: QCoreAgentConfig
):
    """Async версия основного цикла с StateStore"""
    try:
        while True:
            await orchestrator.run_tick_async(data_provider)

            # Логирование из StateStore вместо agent.context
            state_store = orchestrator.state_store
            current_state = await state_store.get()

            logger.info("--- Input Messages (StateStore Mode) ---")
            logger.info(f"BIOS: {data_provider.get_bios_status().model_dump_json()}")
            logger.info(f"FSM: {json.dumps(dto_to_protobuf_json(current_state))}")
            logger.info(
                f"Proposals: {[p.model_dump_json() for p in data_provider.get_proposals()]}"
            )
            logger.info(f"Sensor: {data_provider.get_sensor_data().model_dump_json()}")

            await asyncio.sleep(config.tick_interval)
    except KeyboardInterrupt:
        logger.info("StateStore run stopped by user.")


def main():
    parser = argparse.ArgumentParser(description="Q-Core Agent Main Control.")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode.")
    parser.add_argument(
        "--grpc", action="store_true", help="Run with gRPC connection to Q-Sim Service."
    )
    args = parser.parse_args()

    # Настройка логирования
    log_config_path = os.path.join(os.path.dirname(__file__), "config", "logging.yaml")
    setup_logging(default_path=log_config_path)

    # Обработка сигналов завершения
    def handle_shutdown(signum, frame):
        logger.info("Shutdown signal received. Cleaning up...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Загрузка конфигурации
    config_path = Path(__file__).parent / "config.yaml"
    config = load_config(config_path, QCoreAgentConfig)
    logger.info(f"Loaded config: {config.model_dump_json(indent=2)}")

    if (os.getenv("QCORE_ENABLE_INTENT_BRIDGE", "true") or "true").strip().lower() in {"1", "true", "yes", "y"}:
        try:
            start_intent_bridge_in_thread(os.getenv("NATS_URL"))
            logger.info("Intent bridge enabled (Stage C, no OpenAI).")
        except Exception as exc:
            logger.error("Failed to start intent bridge: %s", exc)

    # Проверка StateStore флага
    use_statestore = os.environ.get("QIKI_USE_STATESTORE", "false").lower() == "true"

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
                    logger.info(
                        f"BIOS: {data_provider.get_bios_status().model_dump_json()}"
                    )
                    logger.info(f"FSM: {agent.context.fsm_state.model_dump_json()}")
                    logger.info(
                        f"Proposals: {[p.model_dump_json() for p in data_provider.get_proposals()]}"
                    )
                    logger.info(
                        f"Sensor: {data_provider.get_sensor_data().model_dump_json()}"
                    )
                    time.sleep(config.tick_interval)
            except KeyboardInterrupt:
                logger.info("Mock run stopped by user.")
    elif args.grpc:
        logger.info("Running in GRPC mode (connecting to Q-Sim Service via gRPC).")
        data_provider = GrpcDataProvider(config.grpc_server_address)

        if use_statestore:
            # Async режим с StateStore
            asyncio.run(run_with_statestore(agent, orchestrator, data_provider, config))
        else:
            # Legacy sync режим
            try:
                while True:
                    orchestrator.run_tick(data_provider)
                    logger.info("--- Input Messages (gRPC) ---")
                    logger.info(
                        f"BIOS: {data_provider.get_bios_status().model_dump_json()}"
                    )
                    logger.info(f"FSM: {agent.context.fsm_state.model_dump_json()}")
                    logger.info(
                        f"Proposals: {[p.model_dump_json() for p in data_provider.get_proposals()]}"
                    )
                    logger.info(
                        f"Sensor: {data_provider.get_sensor_data().model_dump_json()}"
                    )
                    time.sleep(config.tick_interval)
            except KeyboardInterrupt:
                logger.info("gRPC run stopped by user.")
    else:
        logger.info("Running in LEGACY mode (direct Q-Sim Service instance).")
        # Initialize QSimService (for MVP, direct instance)
        project_src = Path(__file__).resolve().parents[3]
        qsim_config_path = project_src / "qiki" / "services" / "q_sim_service" / "config.yaml"
        qsim_config = load_config(qsim_config_path, QSimServiceConfig)
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
                    logger.info(
                        f"BIOS: {data_provider.get_bios_status().model_dump_json()}"
                    )
                    logger.info(f"FSM: {agent.context.fsm_state.model_dump_json()}")
                    logger.info(
                        f"Proposals: {[p.model_dump_json() for p in data_provider.get_proposals()]}"
                    )
                    logger.info(
                        f"Sensor: {data_provider.get_sensor_data().model_dump_json()}"
                    )
                    time.sleep(config.tick_interval)
            except KeyboardInterrupt:
                logger.info("Legacy run stopped by user.")


if __name__ == "__main__":
    main()
