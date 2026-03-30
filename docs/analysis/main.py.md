# Анализ файла main.py

## Вход и цель
- **Файл**: main.py
- **Итог**: Обзор точки входа в приложение Q-Core Agent

## Сбор контекста
- **Исходник**: /home/sonra44/QIKI_DTMP/services/q_core_agent/main.py
- **Связанные файлы**:
  - agent.py (основной агент)
  - agent_logger.py (настройка логирования)
  - interfaces.py (интерфейсы компонентов)
  - grpc_data_provider.py (gRPC провайдер данных)
  - tick_orchestrator.py (оркестратор тиков)
  - config.yaml (конфигурация агента)
  - config/logging.yaml (настройки логирования)
  - state/store.py (хранилище состояний)
  - state/types.py (типы состояний)
  - state/conv.py (конвертеры)
  - services/q_sim_service/main.py (сервис симуляции)

**[Факт]**: Файл является точкой входа в приложение Q-Core Agent и координирует работу всех компонентов.

## Локализация артефакта
- **Точный путь**: /home/sonra44/QIKI_DTMP/services/q_core_agent/main.py
- **Окружение**: Python 3.x, gRPC, asyncio, yaml, protobuf

## Фактический разбор
### Ключевые функции и классы:
- **main()**: Основная точка входа в приложение
  - Парсит аргументы командной строки
  - Настраивает логирование
  - Обрабатывает сигналы завершения
  - Загружает конфигурацию
  - Создает агент и оркестратор
  - Запускает цикл обработки в зависимости от режима
  
- **run_with_statestore()**: Асинхронный цикл обработки с использованием StateStore
- **load_config()**: Загрузка конфигурации из YAML файла
- **_create_mock_bios_status()**: Создание мок данных BIOS для тестирования
- **_create_mock_fsm_state()**: Создание мок FSM состояния для тестирования

### Режимы работы:
1. **Mock режим** (--mock): Использует MockDataProvider с предопределенными данными
2. **GRPC режим** (--grpc): Использует GrpcDataProvider для взаимодействия с Q-Sim Service
3. **Legacy режим** (по умолчанию): Использует QSimDataProvider с прямым доступом к экземпляру QSimService

**[Факт]**: Приложение поддерживает три режима работы и может использовать StateStore для управления состоянием FSM.

## Роль в системе и связи
- **Как участвует в потоке**: Точка входа, инициализирующая и запускающая Q-Core Agent
- **Кто вызывает**: Запускается как основное приложение командой python main.py
- **Что от него ждут**: Корректная инициализация всех компонентов и запуск цикла обработки
- **Чем он рискует**: Сбои при инициализации могут привести к неработоспособности всего агента

**[Факт]**: main.py координирует работу между различными компонентами системы и обеспечивает гибкость через несколько режимов работы.

## Несоответствия и риски
1. **Высокий риск**: В Legacy режиме создается экземпляр QSimService, который может быть несовместим с асинхронной архитектурой
2. **Средний риск**: Отсутствует обработка ошибок при создании провайдеров данных
3. **Низкий риск**: Мок данные в Mock режиме могут не отражать реальное поведение системы
4. **Низкий риск**: Нет явной обработки ситуации, когда StateStore не может быть инициализирован

**[Гипотеза]**: Может потребоваться унификация всех режимов работы под асинхронную архитектуру.

## Мини-патчи (safe-fix)
**[Патч]**: Добавить обработку ошибок при создании провайдеров данных:
```python
try:
    if args.mock:
        logger.info("Running in MOCK mode.")
        data_provider = _MOCK_DATA_PROVIDER
    elif args.grpc:
        logger.info("Running in GRPC mode (connecting to Q-Sim Service via gRPC).")
        grpc_address = config.get('grpc_server_address', 'localhost:50051')
        data_provider = GrpcDataProvider(grpc_address)
    else:
        logger.info("Running in LEGACY mode (direct Q-Sim Service instance).")
        # Initialize QSimService (for MVP, direct instance)
        qsim_config_path = os.path.join(ROOT_DIR, 'services', 'q_sim_service', 'config.yaml')
        qsim_config = load_config(qsim_config_path)  # Reuse load_config for qsim
        qsim_service = QSimService(qsim_config)
        data_provider = QSimDataProvider(qsim_service)
except Exception as e:
    logger.error(f"Failed to initialize data provider: {e}")
    sys.exit(1)
```

## Рефактор-скетч (по желанию)
```python
import argparse
import asyncio
import signal
import sys
from typing import Optional

from services.q_core_agent.core.agent import QCoreAgent
from services.q_core_agent.core.agent_logger import setup_logging, logger
from services.q_core_agent.core.grpc_data_provider import GrpcDataProvider
from services.q_core_agent.core.interfaces import IDataProvider, MockDataProvider
from services.q_core_agent.core.tick_orchestrator import TickOrchestrator
from services.q_core_agent.state.store import create_initialized_store
from services.q_sim_service.main import QSimService

class QCoreAgentRunner:
    def __init__(self):
        self.agent: Optional[QCoreAgent] = None
        self.orchestrator: Optional[TickOrchestrator] = None
        self.data_provider: Optional[IDataProvider] = None
        self.config: Optional[dict] = None
        
    async def initialize(self, args):
        """Инициализация всех компонентов"""
        # Настройка логирования
        log_config_path = os.path.join(os.path.dirname(__file__), 'config', 'logging.yaml')
        setup_logging(default_path=log_config_path)
        
        # Загрузка конфигурации
        self.config = self.load_config()
        logger.info(f"Loaded config: {self.config}")
        
        # Создание агента
        self.agent = QCoreAgent(self.config)
        
        # Создание StateStore если включён
        state_store = None
        use_statestore = os.environ.get('QIKI_USE_STATESTORE', 'false').lower() == 'true'
        if use_statestore:
            logger.info("QIKI_USE_STATESTORE=true - включён StateStore режим")
            state_store = create_initialized_store()
        
        # Создание оркестратора
        self.orchestrator = TickOrchestrator(self.agent, self.config, state_store=state_store)
        
        # Создание провайдера данных
        await self._create_data_provider(args)
        
    async def _create_data_provider(self, args):
        """Создание провайдера данных в зависимости от режима"""
        try:
            if args.mock:
                logger.info("Running in MOCK mode.")
                self.data_provider = self._create_mock_provider()
            elif args.grpc:
                logger.info("Running in GRPC mode.")
                grpc_address = self.config.get('grpc_server_address', 'localhost:50051')
                self.data_provider = GrpcDataProvider(grpc_address)
            else:
                logger.info("Running in LEGACY mode.")
                self.data_provider = await self._create_legacy_provider()
        except Exception as e:
            logger.error(f"Failed to create data provider: {e}")
            raise
            
    def _create_mock_provider(self) -> MockDataProvider:
        """Создание мок провайдера"""
        # ... код создания мок провайдера
        return _MOCK_DATA_PROVIDER

    async def _create_legacy_provider(self) -> QSimDataProvider:
        """Создание legacy провайдера"""
        qsim_config_path = os.path.join(ROOT_DIR, 'services', 'q_sim_service', 'config.yaml')
        qsim_config = self.load_config(qsim_config_path)
        qsim_service = QSimService(qsim_config)
        return QSimDataProvider(qsim_service)
        
    async def run(self):
        """Запуск основного цикла"""
        use_statestore = os.environ.get('QIKI_USE_STATESTORE', 'false').lower() == 'true'
        
        if use_statestore:
            await self._run_with_statestore()
        else:
            await self._run_legacy_mode()
            
    async def _run_with_statestore(self):
        """Асинхронный режим с StateStore"""
        try:
            while True:
                await self.orchestrator.run_tick_async(self.data_provider)
                await asyncio.sleep(self.config.get('tick_interval', 5))
        except KeyboardInterrupt:
            logger.info("StateStore run stopped by user.")
            
    async def _run_legacy_mode(self):
        """Легаси режим"""
        try:
            while True:
                self.orchestrator.run_tick(self.data_provider)
                await asyncio.sleep(self.config.get('tick_interval', 5))
        except KeyboardInterrupt:
            logger.info("Legacy run stopped by user.")

async def main_async():
    parser = argparse.ArgumentParser(description="Q-Core Agent Main Control.")
    parser.add_argument('--mock', action='store_true', help='Run in mock mode.')
    parser.add_argument('--grpc', action='store_true', help='Run with gRPC connection to Q-Sim Service.')
    args = parser.parse_args()
    
    runner = QCoreAgentRunner()
    await runner.initialize(args)
    await runner.run()

def main():
    # Обработка сигналов завершения
    def handle_shutdown(signum, frame):
        logger.info("Shutdown signal received. Cleaning up...")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Запуск асинхронного кода
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
```

## Примеры использования
```bash
# Запуск в мок режиме
python main.py --mock

# Запуск с gRPC подключением
python main.py --grpc

# Запуск в легаси режиме (по умолчанию)
python main.py

# Запуск с StateStore
QIKI_USE_STATESTORE=true python main.py --mock
```

```python
# Пример использования в коде
import argparse
import sys
import os

# Добавляем корневую директорию в путь
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(ROOT_DIR)

from services.q_core_agent.main import main

if __name__ == "__main__":
    # Можно вызвать main напрямую
    main()
```

## Тест-хуки/чек-лист
- [ ] Проверить запуск в каждом из трех режимов (--mock, --grpc, default)
- [ ] Проверить корректную инициализацию логирования
- [ ] Проверить обработку сигналов завершения (SIGINT, SIGTERM)
- [ ] Проверить загрузку конфигурации
- [ ] Проверить работу с StateStore при установленной переменной окружения
- [ ] Проверить корректное создание провайдеров данных
- [ ] Проверить работу основного цикла обработки

## Вывод
- **Текущее состояние**: Файл реализует точку входа с поддержкой трех режимов работы и интеграцией со StateStore
- **Что починить сразу**: Добавить обработку ошибок при создании провайдеров данных
- **Что отложить**: Унификация всех режимов работы под асинхронную архитектуру

**[Факт]**: Анализ завершен на основе содержимого файла и его роли в системе.