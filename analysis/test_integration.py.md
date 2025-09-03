# Анализ файла test_integration.py

## Вход и цель
- **Файл**: test_integration.py
- **Итог**: Обзор интеграционных тестов для StateStore архитектуры

## Сбор контекста
- **Исходник**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/tests/test_integration.py
- **Связанные файлы**:
  - services/q_core_agent/state/store.py (тестируемый компонент)
  - services/q_core_agent/state/types.py (DTO типы)
  - services/q_core_agent/state/conv.py (конвертеры)
  - services/q_core_agent/state/tests/test_types.py (unit тесты типов)
  - services/q_core_agent/state/tests/test_store.py (unit тесты хранилища)
  - services/q_core_agent/state/tests/test_conv.py (unit тесты конвертеров)
  - services/q_core_agent/state/tests/test_stress.py (стресс-тесты)

**[Факт]**: Файл содержит интеграционные тесты для проверки взаимодействия между компонентами StateStore архитектуры.

## Локализация артефакта
- **Точный путь**: /home/sonra44/QIKI_DTMP/services/q_core_agent/state/tests/test_integration.py
- **Окружение**: Python 3.x, pytest, asyncio

## Фактический разбор
### Ключевые классы тестов:
- **TestFSMHandlerStateStoreIntegration**: Интеграционные тесты FSMHandler + StateStore
  - `test_basic_fsm_processing_with_store()`: Тест базовой обработки FSM с записью в StateStore
  - `test_fsm_state_sequence()`: Тест последовательности переходов FSM
  - `test_version_monotonicity()`: Тест монотонности версий при множественных изменениях
  - `test_no_state_change_keeps_version()`: Тест что отсутствие изменений не увеличивает версию
  - `test_fsm_handler_without_state_store()`: Тест FSMHandler без StateStore (fallback режим)

- **TestStateStoreSubscriberIntegration**: Интеграционные тесты подписчиков StateStore
  - `test_subscriber_receives_fsm_updates()`: Тест что подписчики получают обновления от FSM
  - `test_multiple_subscribers_fsm_updates()`: Тест множественных подписчиков при FSM обновлениях
  - `test_subscriber_stream_consistency()`: Тест согласованности потока обновлений у подписчика

- **TestConversionIntegration**: Интеграционные тесты конвертации с реальными данными
  - `test_dto_protobuf_roundtrip_with_real_fsm_data()`: Тест roundtrip конвертации с реальными FSM данными
  - `test_json_conversion_with_fsm_history()`: Тест JSON конвертации с историей FSM переходов

- **TestConcurrentIntegration**: Интеграционные тесты конкурентного доступа между компонентами
  - `test_concurrent_fsm_processing()`: Тест конкурентной обработки FSM от нескольких handlers
  - `test_concurrent_subscribers_and_fsm()`: Тест конкурентных подписчиков во время FSM обработки

- **TestErrorHandlingIntegration**: Интеграционные тесты обработки ошибок
  - `test_state_store_failure_recovery()`: Тест восстановления при сбоях StateStore
  - `test_conversion_error_handling()`: Тест обработки ошибок конвертации в интеграции
  - `test_subscriber_error_isolation()`: Тест изоляции ошибок подписчиков

- **TestFeatureFlagIntegration**: Интеграционные тесты с feature флагами
  - `test_state_store_enable_disable()`: Тест включения/выключения StateStore через переменную окружения
  - `test_graceful_degradation()`: Тест плавной деградации при проблемах с StateStore

**[Факт]**: Тесты охватывают ключевые аспекты интеграции между компонентами StateStore архитектуры.

## Роль в системе и связи
- **Как участвует в потоке**: Проверяет корректность взаимодействия между компонентами StateStore, FSMHandler и конвертерами
- **Кто вызывает**: pytest при запуске тестов, CI/CD системы
- **Что от него ждут**: Выявление проблем интеграции между компонентами архитектуры
- **Чем он рискует**: Сложность отладки при сбоях, возможные ложные срабатывания из-за внешних зависимостей

**[Факт]**: Тесты обеспечивают надежность интеграции между компонентами StateStore архитектуры.

## Несоответствия и риски
1. **Средний риск**: Некоторые тесты используют моки вместо реальных компонентов, что может скрывать проблемы интеграции
2. **Низкий риск**: Отсутствует тестирование интеграции с реальными protobuf сообщениями из других сервисов
3. **Низкий риск**: Нет явной проверки обратной совместимости при изменениях формата DTO
4. **Низкий риск**: Нет тестов для проверки поведения при миграции данных между версиями

**[Гипотеза]**: Может потребоваться добавить тесты для проверки интеграции с реальными компонентами системы вместо моков.

## Мини-патчи (safe-fix)
**[Патч]**: Добавить тест для проверки интеграции с реальными protobuf сообщениями:
```python
@pytest.mark.asyncio
async def test_integration_with_real_protobuf_messages(self, state_store):
    """Тест интеграции с реальными protobuf сообщениями"""
    # Создаем реальный protobuf снапшот
    from generated.fsm_state_pb2 import FsmStateSnapshot, FSMStateEnum
    from generated.common_types_pb2 import UUID
    from google.protobuf.timestamp_pb2 import Timestamp
    
    proto_snapshot = FsmStateSnapshot()
    proto_snapshot.current_state = FSMStateEnum.IDLE
    proto_snapshot.snapshot_id.CopyFrom(UUID(value="test_integration"))
    
    timestamp = Timestamp()
    timestamp.GetCurrentTime()
    proto_snapshot.timestamp.CopyFrom(timestamp)
    
    # Конвертируем в DTO
    dto = proto_to_dto(proto_snapshot)
    
    # Сохраняем в StateStore
    await state_store.set(dto)
    
    # Получаем обратно
    retrieved_dto = await state_store.get()
    
    # Конвертируем обратно в protobuf
    converted_proto = dto_to_proto(retrieved_dto)
    
    # Проверяем что данные сохранились корректно
    assert converted_proto.current_state == FSMStateEnum.IDLE
    assert converted_proto.snapshot_id.value == "test_integration"
```

## Рефактор-скетч (по желанию)
```python
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import os

from ..store import AsyncStateStore, create_initialized_store
from ..types import FsmSnapshotDTO, FsmState, TransitionStatus, initial_snapshot, next_snapshot
from ..conv import dto_to_proto, proto_to_dto, dto_to_json_dict

# Базовый класс для интеграционных тестов
class BaseIntegrationTest:
    """Базовый класс для интеграционных тестов"""
    
    @pytest.fixture
    def mock_context(self):
        """Мок контекста агента"""
        return MockAgentContext()
        
    @pytest.fixture
    def state_store(self):
        """StateStore с начальным состоянием"""
        return create_initialized_store()
        
    @pytest.fixture
    def fsm_handler(self, mock_context, state_store):
        """FSMHandler с StateStore"""
        return MockFSMHandler(mock_context, state_store)


class FSMHandlerStateStoreIntegrationTest(BaseIntegrationTest):
    """Интеграционные тесты FSMHandler + StateStore"""
    
    @pytest.mark.asyncio
    async def test_fsm_processing_integration(self, fsm_handler, state_store, mock_context):
        """Комплексный тест интеграции FSMHandler и StateStore"""
        # Проверяем начальное состояние
        initial = await state_store.get()
        assert initial.state == FsmState.BOOTING
        
        # Выполняем переход BOOTING -> IDLE
        mock_context.bios_ok = True
        result = await fsm_handler.process_fsm_dto(initial)
        
        # Проверяем результат обработки
        assert result.state == FsmState.IDLE
        assert result.reason == "BOOT_COMPLETE"
        assert result.version == 1
        
        # Проверяем что состояние записалось в StateStore
        stored = await state_store.get()
        assert stored == result
        assert stored.state == FsmState.IDLE


class StateStoreSubscriberIntegrationTest(BaseIntegrationTest):
    """Интеграционные тесты подписчиков StateStore"""
    
    @pytest.mark.asyncio
    async def test_subscriber_integration(self, fsm_handler, state_store):
        """Тест интеграции подписчиков с обновлениями"""
        # Подписываемся на изменения
        queue = await state_store.subscribe("integration_test_subscriber")
        
        # Должно быть начальное состояние
        initial_update = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert initial_update.state == FsmState.BOOTING
        
        # Выполняем FSM переход
        current = await state_store.get()
        await fsm_handler.process_fsm_dto(current)
        
        # Подписчик должен получить обновление
        update = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert update.state == FsmState.IDLE
        assert update.reason == "BOOT_COMPLETE"


# Группировка тестов
class TestIntegrationSuite:
    """Основной набор интеграционных тестов"""
    
    # Тесты FSMHandler + StateStore
    test_fsm_integration = FSMHandlerStateStoreIntegrationTest()
    
    # Тесты подписчиков
    test_subscriber_integration = StateStoreSubscriberIntegrationTest()
    
    # Тесты конвертации
    # test_conversion_integration = ConversionIntegrationTest()
    
    # Тесты конкурентного доступа
    # test_concurrent_integration = ConcurrentIntegrationTest()
    
    # Тесты обработки ошибок
    # test_error_handling_integration = ErrorHandlingIntegrationTest()
    
    # Тесты feature флагов
    # test_feature_flag_integration = FeatureFlagIntegrationTest()


# Конфигурация pytest
pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio
]


if __name__ == "__main__":
    # Запуск интеграционных тестов
    pytest.main([__file__, "-v", "-s", "--tb=short"])
```

## Примеры использования
```python
# Запуск всех интеграционных тестов
pytest services/q_core_agent/state/tests/test_integration.py -v -s

# Запуск конкретного теста
pytest services/q_core_agent/state/tests/test_integration.py::TestFSMHandlerStateStoreIntegration::test_basic_fsm_processing_with_store -v

# Запуск с меткой
pytest services/q_core_agent/state/tests/test_integration.py -v -m integration

# Запуск в режиме дебага
pytest services/q_core_agent/state/tests/test_integration.py -v -s --tb=long
```

```python
# Пример использования в CI/CD
import subprocess
import sys

def run_integration_tests():
    """Запустить интеграционные тесты в CI/CD"""
    try:
        result = subprocess.run([
            "python3", "-m", "pytest",
            "services/q_core_agent/state/tests/test_integration.py",
            "-v", "--tb=short"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("Все интеграционные тесты пройдены успешно")
            return True
        else:
            print(f"Интеграционные тесты провалены:\n{result.stdout}\n{result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("Интеграционные тесты превысили лимит времени")
        return False
    except Exception as e:
        print(f"Ошибка запуска интеграционных тестов: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
```

## Тест-хуки/чек-лист
- [ ] Проверить корректность интеграции FSMHandler с StateStore
- [ ] Проверить что подписчики получают обновления от FSM
- [ ] Проверить корректность конвертации между DTO и protobuf
- [ ] Проверить поведение при конкурентном доступе
- [ ] Проверить обработку ошибок в интеграции
- [ ] Проверить работу с feature флагами
- [ ] Проверить последовательность переходов FSM
- [ ] Проверить монотонность версий состояний
- [ ] Проверить согласованность потока обновлений у подписчиков

## Вывод
- **Текущее состояние**: Файл содержит комплексные интеграционные тесты, покрывающие ключевые аспекты взаимодействия между компонентами StateStore
- **Что починить сразу**: Добавить тесты для проверки интеграции с реальными protobuf сообщениями
- **Что отложить**: Реализацию тестов для проверки обратной совместимости при изменениях формата DTO

**[Факт]**: Анализ завершен на основе содержимого файла и его роли в системе тестирования.