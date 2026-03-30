# Анализ файла grpc_data_provider.py

## Вход и цель
- **Файл**: grpc_data_provider.py
- **Итог**: Обзор реализации провайдера данных через gRPC для взаимодействия с Q-Sim Service

## Сбор контекста
- **Исходник**: /home/sonra44/QIKI_DTMP/services/q_core_agent/core/grpc_data_provider.py
- **Связанные файлы**:
  - interfaces.py (интерфейс IDataProvider)
  - agent_logger.py (логирование)
  - generated/q_sim_api_pb2_grpc.py (gRPC клиент и сервер)
  - protos/q_sim_api.proto (определение gRPC сервиса)
  - generated/sensor_raw_in_pb2.py (данные сенсоров)
  - generated/actuator_raw_out_pb2.py (команды актуаторов)

**[Факт]**: Файл реализует провайдер данных через gRPC для взаимодействия с Q-Sim Service.

## Локализация артефакта
- **Точный путь**: /home/sonra44/QIKI_DTMP/services/q_core_agent/core/grpc_data_provider.py
- **Окружение**: Python 3.x, gRPC, сгенерированные protobuf классы

## Фактический разбор
### Ключевые классы и функции:
- **GrpcDataProvider**: Реализация IDataProvider для gRPC
  - `__init__()`: Инициализирует gRPC клиент с адресом сервера
  - `_connect()`: Устанавливает соединение с gRPC сервером
  - `get_bios_status()`: Генерирует мок статус BIOS (Q-Sim не управляет BIOS)
  - `get_fsm_state()`: Возвращает состояние FSM (пустышка при StateStore режиме)
  - `get_proposals()`: Возвращает пустой список предложений (Q-Sim не генерирует предложения)
  - `get_sensor_data()`: Запрашивает данные сенсоров через gRPC
  - `send_actuator_command()`: Отправляет команды актуаторам через gRPC
  - `__del__()`: Закрывает gRPC соединение

**[Факт]**: Класс реализует все методы интерфейса IDataProvider для работы через gRPC.

## Роль в системе и связи
- **Как участвует в потоке**: Предоставляет данные для QCoreAgent через gRPC соединение с Q-Sim Service
- **Кто вызывает**: QCoreAgent использует его как источник данных
- **Что от него ждут**: Корректное получение данных от симулятора и отправка команд актуаторам
- **Чем он рискует**: Потеря соединения с gRPC сервером, таймауты при запросах

**[Факт]**: GrpcDataProvider заменяет прямой доступ к экземпляру QSimService на сетевое взаимодействие через gRPC.

## Несоответствия и риски
1. **Высокий риск**: При потере соединения с gRPC сервером агент может перестать функционировать
2. **Средний риск**: Метод `get_bios_status()` генерирует мок данные вместо реальных данных от BIOS
3. **Средний риск**: Метод `get_fsm_state()` возвращает пустое состояние вместо реального FSM состояния
4. **Низкий риск**: Метод `get_proposals()` всегда возвращает пустой список, так как Q-Sim не генерирует предложения

**[Гипотеза]**: Может потребоваться реализация механизма повторного подключения при разрыве gRPC соединения.

## Мини-патчи (safe-fix)
**[Патч]**: Добавить повторные попытки подключения при сбое:
```python
import time

def _connect(self):
    """Устанавливает gRPC соединение с симулятором с повторными попытками"""
    max_retries = 3
    retry_delay = 5.0
    
    for attempt in range(max_retries):
        try:
            self.channel = grpc.insecure_channel(self.server_address)
            self.stub = QSimAPIStub(self.channel)
            
            # Проверяем соединение
            response = self.stub.HealthCheck(Empty(), timeout=5.0)
            logger.info(f"Connected to Q-Sim Service at {self.server_address}: {response.message}")
            return
            
        except grpc.RpcError as e:
            logger.warning(f"Failed to connect to Q-Sim Service at {self.server_address} (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to connect to Q-Sim Service after {max_retries} attempts")
                raise ConnectionError(f"Cannot connect to Q-Sim Service: {e}")
```

## Рефактор-скетч (по желанию)
```python
class GrpcDataProvider(IDataProvider):
    def __init__(self, grpc_server_address="localhost:50051", max_retries=3, retry_delay=5.0):
        self.server_address = grpc_server_address
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.channel = None
        self.stub = None
        self._connect()
    
    def _reconnect_if_needed(self):
        """Проверяет соединение и переподключается при необходимости"""
        try:
            # Проверяем соединение
            response = self.stub.HealthCheck(Empty(), timeout=2.0)
            return True
        except grpc.RpcError:
            logger.warning("gRPC connection lost. Attempting to reconnect...")
            self._connect()
            return False
    
    def get_sensor_data(self) -> SensorReading:
        """Запрашивает данные сенсоров через gRPC с повторными попытками"""
        for attempt in range(self.max_retries):
            try:
                if not self._reconnect_if_needed():
                    continue
                    
                response = self.stub.GetSensorData(Empty(), timeout=10.0)
                logger.debug(f"Received sensor data via gRPC: {response.sensor_id.value}")
                return response
            except grpc.RpcError as e:
                logger.error(f"Failed to get sensor data via gRPC (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    
        # Возвращаем пустое показание при ошибке
        return SensorReading(
            sensor_id=UUID(value="error_sensor"),
            scalar_data=0.0
        )
```

## Примеры использования
```python
# Создание gRPC провайдера данных
grpc_provider = GrpcDataProvider("localhost:50051")

# Получение данных сенсоров
sensor_data = grpc_provider.get_sensor_data()
print(f"Sensor ID: {sensor_data.sensor_id.value}")
print(f"Sensor Value: {sensor_data.scalar_data}")

# Отправка команды актуатору
from generated.actuator_raw_out_pb2 import ActuatorCommand
from generated.common_types_pb2 import UUID
from google.protobuf.timestamp_pb2 import Timestamp

timestamp = Timestamp()
timestamp.GetCurrentTime()

command = ActuatorCommand(
    actuator_id=UUID(value="motor_left"),
    timestamp=timestamp,
    command_type=ActuatorCommand.CommandType.SET_VELOCITY_PERCENT,
    value=75.0
)

grpc_provider.send_actuator_command(command)
```

## Тест-хуки/чек-лист
- [ ] Проверить установку gRPC соединения при инициализации
- [ ] Проверить обработку ошибок при недоступности gRPC сервера
- [ ] Проверить получение данных сенсоров через gRPC
- [ ] Проверить отправку команд актуаторам через gRPC
- [ ] Проверить корректность мок данных BIOS
- [ ] Проверить поведение в StateStore режиме

## Вывод
- **Текущее состояние**: Файл реализует провайдер данных через gRPC с базовой функциональностью
- **Что починить сразу**: Добавить механизм повторных попыток подключения и запросов при сбоях
- **Что отложить**: Реализация полноценного получения данных BIOS и FSM от Q-Sim Service

**[Факт]**: Анализ завершен на основе содержимого файла и связанных компонентов.