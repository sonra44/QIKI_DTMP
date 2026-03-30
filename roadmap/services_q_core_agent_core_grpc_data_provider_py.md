# Анализ /home/sonra44/QIKI_DTMP/services/q_core_agent/core/grpc_data_provider.py

## СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/grpc_data_provider.py

## Вход и цель
- [Факт] Модуль реализует `GrpcDataProvider` для обмена с Q-Sim через gRPC.
- [Цель] Описать взаимодействие, выявить риски и предложить улучшения.

## Сбор контекста
- [Факт] Использует `grpc`, `QSimAPIStub` и protobuf-сообщения (`BiosStatusReport`, `SensorReading` и др.).
- [Факт] Наследует интерфейс `IDataProvider` из `interfaces.py`.
- [Гипотеза] Предназначен для работы в режимах mock и legacy через аргументы CLI.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/grpc_data_provider.py`.
- [Факт] Создается в `main.py` при запуске с флагом `--grpc`.

## Фактический разбор
- [Факт] Метод `_connect` устанавливает канал и выполняет `HealthCheck`.
- [Факт] `get_bios_status` возвращает мок-данные BIOS.
- [Факт] `get_fsm_state` учитывает переменную окружения `QIKI_USE_STATESTORE`.
- [Факт] `get_sensor_data` и `send_actuator_command` вызывают gRPC методы.
- [Гипотеза] Нет повторных попыток подключения при сбое.

## Роль в системе и связи
- [Факт] Обеспечивает сетевой слой между агентом и симулятором.
- [Гипотеза] Может заменять `QSimDataProvider` для удаленного доступа.

## Несоответствия и риски
- [Риск|Med] При ошибке подключения `_connect` выбрасывает исключение без ретраев.
- [Риск|Low] В `get_sensor_data` возвращается фиктивное показание при ошибке без уведомления вызывающей стороны.

## Мини-патчи (safe-fix)
- [Патч] Добавить экспоненциальный бэкофф и несколько попыток подключения.
- [Патч] В `get_sensor_data` возвращать `None` и логировать уровень `warning`.

## Рефактор-скетч
```python
class GrpcDataProvider(IDataProvider):
    def _connect(self, retries=3):
        for attempt in range(retries):
            try:
                self.channel = grpc.insecure_channel(self.server_address)
                self.stub = QSimAPIStub(self.channel)
                self.stub.HealthCheck(Empty(), timeout=5.0)
                return
            except grpc.RpcError as e:
                time.sleep(2 ** attempt)
        raise ConnectionError("Cannot connect to Q-Sim Service")
```

## Примеры использования
```python
from services.q_core_agent.core.grpc_data_provider import GrpcDataProvider

provider = GrpcDataProvider("localhost:50051")
status = provider.get_bios_status()
print(status.firmware_version)

# Получение показаний сенсора
reading = provider.get_sensor_data()
print(reading.sensor_id.value)

# Отправка команды актуатору
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import UUID
cmd = ActuatorCommand(actuator_id=UUID(value="motor"))
provider.send_actuator_command(cmd)

# Закрытие канала при уничтожении
del provider
```

## Тест-хуки/чек-лист
- [ ] Смоделировать недоступность сервера и ожидать `ConnectionError`.
- [ ] Проверить, что `get_sensor_data` обрабатывает `grpc.RpcError` и возвращает заглушку.
- [ ] Убедиться, что канал закрывается при удалении объекта (использовать `gc.collect()`).

## Вывод
1. [Факт] Модуль предоставляет gRPC-доступ к Q-Sim.
2. [Факт] Обрабатывает основные типы данных (BIOS, FSM, сенсоры, актуаторы).
3. [Риск] Отсутствуют механизмы ретрая подключения.
4. [Риск] Ошибки сенсоров маскируются фиктивными данными.
5. [Патч] Реализовать повторные попытки и бэкофф.
6. [Патч] Возвращать `None` для неверных сенсорных данных.
7. [Гипотеза] Требуется конфигурируемый таймаут.
8. [Факт] Код готов для базового использования.
9. [Гипотеза] Возможна интеграция с пулом каналов gRPC.
10. [Цель] Повысить надежность сетевого взаимодействия.
