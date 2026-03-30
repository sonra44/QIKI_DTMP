# Анализ /home/sonra44/QIKI_DTMP/services/q_core_agent/core/interfaces.py

## СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/interfaces.py

## Вход и цель
- [Факт] Файл определяет абстрактные интерфейсы и мок-реализации для агента.
- [Цель] Зафиксировать контракты, оценить риски и предложить улучшения.

## Сбор контекста
- [Факт] Используются protobuf-типы: `BiosStatusReport`, `FsmStateSnapshot`, `Proposal`, `SensorReading`, `ActuatorCommand`.
- [Факт] Реализованы классы `MockDataProvider` и `QSimDataProvider`.
- [Гипотеза] Интерфейсы используются во многих модулях для внедрения зависимостей.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/interfaces.py`.
- [Факт] Импортируется из `agent.py` и `main.py`.

## Фактический разбор
- [Факт] `IDataProvider` определяет методы получения BIOS, FSM, предложений и сенсорных данных.
- [Факт] `MockDataProvider` возвращает заранее подготовленные значения и печатает команды актуаторов.
- [Факт] `QSimDataProvider` обращается к объекту `QSimService` напрямую.
- [Факт] Также определены интерфейсы `IBiosHandler`, `IFSMHandler`, `IProposalEvaluator`, `IRuleEngine`, `INeuralEngine`.
- [Гипотеза] Отсутствуют интерфейсы для хранения состояния или логирования.

## Роль в системе и связи
- [Факт] Интерфейсы обеспечивают слабую связанность и возможность подмены реализаций.
- [Гипотеза] `MockDataProvider` служит для unit-тестов, а `QSimDataProvider` — для интеграции.

## Несоответствия и риски
- [Риск|Med] В `MockDataProvider.send_actuator_command` используется `print`, что затрудняет тестирование.
- [Риск|Low] Отсутствие аннотаций `@abstractmethod` в интерфейсах обработчиков может привести к неполному контракту.

## Мини-патчи (safe-fix)
- [Патч] Заменить `print` на `logger` или возвращаемое значение в `MockDataProvider`.
- [Патч] Добавить `@abstractmethod` для методов интерфейсов обработчиков, если планируется расширение.

## Рефактор-скетч
```python
class MockDataProvider(IDataProvider):
    def send_actuator_command(self, command: ActuatorCommand):
        logger.debug("Mock send %s", command.actuator_id.value)
        return self._mock_actuator_response
```

## Примеры использования
```python
from services.q_core_agent.core.interfaces import MockDataProvider, QSimDataProvider
from generated.bios_status_pb2 import BiosStatusReport
from generated.fsm_state_pb2 import FsmStateSnapshot

mock = MockDataProvider(BiosStatusReport(), FsmStateSnapshot(), [], SensorReading())
print(mock.get_bios_status())

# Использование QSimDataProvider
qsim = SomeQSimService()
provider = QSimDataProvider(qsim)
state = provider.get_fsm_state()

# Реализация собственного обработчика
class CustomBiosHandler(IBiosHandler):
    def process_bios_status(self, bios_status):
        return bios_status

# Проверка отправки команды
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import UUID
cmd = ActuatorCommand(actuator_id=UUID(value="motor"))
mock.send_actuator_command(cmd)
```

## Тест-хуки/чек-лист
- [ ] Убедиться, что `MockDataProvider` возвращает переданные данные без изменений.
- [ ] Проверить работу `QSimDataProvider` с настоящим экземпляром `QSimService`.
- [ ] Создать заглушку обработчика и проверить вызов `process_bios_status`.

## Вывод
1. [Факт] Файл задает основу для модульности агента.
2. [Факт] Содержит как интерфейсы, так и базовые реализации.
3. [Риск] `print` в моках осложняет автоматическое тестирование.
4. [Риск] Контракт обработчиков может быть неполным без `@abstractmethod`.
5. [Патч] Перевести вывод моков на логирование.
6. [Патч] Уточнить интерфейсы обработчиков.
7. [Гипотеза] Потребуется интерфейс для доступа к хранилищу состояния.
8. [Факт] Структура облегчает внедрение зависимостей.
9. [Гипотеза] Возможно объединение DataProvider'ов через фабрику.
10. [Цель] Повысить тестируемость и гибкость архитектуры.
