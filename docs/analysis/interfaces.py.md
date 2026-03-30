# Анализ файла interfaces.py

## Вход и цель
- **Файл**: interfaces.py
- **Итог**: Обзор интерфейсов компонентов Q-Core Agent

## Сбор контекста
- **Исходник**: /home/sonra44/QIKI_DTMP/services/q_core_agent/core/interfaces.py
- **Связанные файлы**:
  - agent.py (использует интерфейсы)
  - grpc_data_provider.py (реализует IDataProvider)
  - bios_handler.py (реализует IBiosHandler)
  - fsm_handler.py (реализует IFSMHandler)
  - proposal_evaluator.py (реализует IProposalEvaluator)
  - rule_engine.py (реализует IRuleEngine)
  - neural_engine.py (реализует INeuralEngine)
  - generated/*.pb2.py (protobuf классы)

**[Факт]**: Файл определяет абстрактные интерфейсы для всех ключевых компонентов Q-Core Agent.

## Локализация артефакта
- **Точный путь**: /home/sonra44/QIKI_DTMP/services/q_core_agent/core/interfaces.py
- **Окружение**: Python 3.x, abc (Abstract Base Classes), protobuf сгенерированные классы

## Фактический разбор
### Ключевые интерфейсы:
- **IDataProvider**: Интерфейс для предоставления данных агенту
  - `get_bios_status()` - возвращает статус BIOS
  - `get_fsm_state()` - возвращает состояние FSM
  - `get_proposals()` - возвращает список предложений
  - `get_sensor_data()` - возвращает данные сенсоров
  - `send_actuator_command()` - отправляет команду актуатору

- **IBiosHandler**: Интерфейс для обработки статуса BIOS
  - `process_bios_status()` - обрабатывает входящий статус BIOS и возвращает обновленный статус

- **IFSMHandler**: Интерфейс для обработки состояния конечного автомата
  - `process_fsm_state()` - обрабатывает текущее состояние FSM и возвращает следующее состояние

- **IProposalEvaluator**: Интерфейс для оценки и выбора предложений
  - `evaluate_proposals()` - оценивает список предложений и возвращает отфильтрованный/приоритизированный список

- **IRuleEngine**: Интерфейс для движка правил
  - `generate_proposals()` - генерирует список предложений на основе текущего контекста

- **INeuralEngine**: Интерфейс для нейронного движка
  - `generate_proposals()` - генерирует список предложений на основе ML моделей

### Реализации интерфейсов:
- **MockDataProvider**: Мок реализация IDataProvider для тестирования
- **QSimDataProvider**: Реализация IDataProvider для взаимодействия с Q-Sim Service

**[Факт]**: Все интерфейсы наследуются от ABC (Abstract Base Class) и содержат абстрактные методы.

## Роль в системе и связи
- **Как участвует в потоке**: Определяет контракты взаимодействия между компонентами агента
- **Кто вызывает**: QCoreAgent использует реализации этих интерфейсов
- **Что от него ждут**: Четкие контракты для всех компонентов системы
- **Чем он рискует**: Изменения в интерфейсах могут потребовать изменений во всех реализациях

**[Факт]**: Интерфейсы обеспечивают гибкость системы, позволяя подменять реализации без изменения основной логики агента.

## Несоответствия и риски
1. **Средний риск**: Метод `get_fsm_state()` в MockDataProvider и QSimDataProvider возвращает заглушку при StateStore режиме, что может скрывать проблемы
2. **Низкий риск**: Нет явного разделения на read-only и read-write интерфейсы, что может усложнить тестирование
3. **Низкий риск**: Нет явной типизации для контекста в IRuleEngine и INeuralEngine

**[Гипотеза]**: Может потребоваться разделение IDataProvider на отдельные интерфейсы для чтения и записи данных.

## Мини-патчи (safe-fix)
**[Патч]**: Добавить явную типизацию для контекста в IRuleEngine и INeuralEngine:
```python
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import AgentContext

class IRuleEngine(ABC):
    """
    Abstract interface for the Rule Engine, responsible for generating proposals based on predefined rules.
    """
    @abstractmethod
    def generate_proposals(self, context: "AgentContext") -> List[Proposal]:
        """Generates a list of proposals based on the current agent context."""
        pass

class INeuralEngine(ABC):
    """
    Abstract interface for the Neural Engine, responsible for generating proposals based on ML models.
    """
    @abstractmethod
    def generate_proposals(self, context: "AgentContext") -> List[Proposal]:
        """Generates a list of proposals based on the current agent context using ML models."""
        pass
```

## Рефактор-скетч (по желанию)
```python
from abc import ABC, abstractmethod
from typing import List, Protocol
from generated.bios_status_pb2 import BiosStatusReport
from generated.fsm_state_pb2 import FsmStateSnapshot
from generated.proposal_pb2 import Proposal
from generated.sensor_raw_in_pb2 import SensorReading
from generated.actuator_raw_out_pb2 import ActuatorCommand

# Read-only интерфейсы
class IDataReader(Protocol):
    def get_bios_status(self) -> BiosStatusReport: ...
    def get_fsm_state(self) -> FsmStateSnapshot: ...
    def get_proposals(self) -> List[Proposal]: ...
    def get_sensor_data(self) -> SensorReading: ...

# Write-only интерфейсы
class IDataWriter(Protocol):
    def send_actuator_command(self, command: ActuatorCommand): ...

# Полный интерфейс
class IDataProvider(IDataReader, IDataWriter, ABC):
    pass

# Типизированные интерфейсы
class IRuleEngine(ABC):
    @abstractmethod
    def generate_proposals(self, context: "AgentContext") -> List[Proposal]:
        pass

class INeuralEngine(ABC):
    @abstractmethod
    def generate_proposals(self, context: "AgentContext") -> List[Proposal]:
        pass
```

## Примеры использования
```python
# Пример реализации интерфейса
from services.q_core_agent.core.interfaces import IDataProvider
from generated.bios_status_pb2 import BiosStatusReport
from generated.fsm_state_pb2 import FsmStateSnapshot
from generated.proposal_pb2 import Proposal
from generated.sensor_raw_in_pb2 import SensorReading
from generated.actuator_raw_out_pb2 import ActuatorCommand

class CustomDataProvider(IDataProvider):
    def __init__(self, custom_data_source):
        self.data_source = custom_data_source
    
    def get_bios_status(self) -> BiosStatusReport:
        # Реализация получения статуса BIOS
        return self.data_source.fetch_bios_status()
    
    def get_fsm_state(self) -> FsmStateSnapshot:
        # Реализация получения состояния FSM
        return self.data_source.fetch_fsm_state()
    
    def get_proposals(self) -> List[Proposal]:
        # Реализация получения предложений
        return self.data_source.fetch_proposals()
    
    def get_sensor_data(self) -> SensorReading:
        # Реализация получения данных сенсоров
        return self.data_source.fetch_sensor_data()
    
    def send_actuator_command(self, command: ActuatorCommand):
        # Реализация отправки команды актуатору
        self.data_source.execute_actuator_command(command)
```

## Тест-хуки/чек-лист
- [ ] Проверить, что все абстрактные методы определены в интерфейсах
- [ ] Проверить, что все реализации интерфейсов корректно реализуют все методы
- [ ] Проверить совместимость MockDataProvider с основной логикой агента
- [ ] Проверить совместимость QSimDataProvider с gRPC сервисом
- [ ] Проверить, что изменения в интерфейсах не ломают существующие реализации

## Вывод
- **Текущее состояние**: Файл определяет четкие интерфейсы для всех компонентов агента
- **Что починить сразу**: Добавить явную типизацию для контекста в IRuleEngine и INeuralEngine
- **Что отложить**: Разделение IDataProvider на отдельные интерфейсы для чтения и записи

**[Факт]**: Анализ завершен на основе содержимого файла и его роли в системе.