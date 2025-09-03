СПИСОК ФАЙЛОВ
56. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/__init__.py
57. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/agent_logger.py
58. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/bios_handler.py
59. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/bot_core.py
60. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/mission_control_demo.py

## Вход и цель
- [Факт] Анализ класса `BotCore`.
- [Цель] Описать функциональность ядра бота и предложить улучшения.

## Сбор контекста
- [Факт] Использует JSON-конфиг `bot_config.json` и файл `.qiki_bot.id`.
- [Факт] Применяет модули `sensor_raw_in_pb2`, `actuator_raw_out_pb2`.
- [Гипотеза] Конфиг хранится в `base_path/config`.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/bot_core.py`.
- [Факт] Инициализируется в сервисах, требующих доступ к сенсорам и актуаторам.

## Фактический разбор
- [Факт] `_load_config` читает JSON, поддерживает режим `minimal`.
- [Факт] `_initialize_bot_id` создаёт или читает идентификатор бота.
- [Факт] `_process_incoming_sensor_data` обновляет снимок и вызывает колбэки.
- [Факт] `send_actuator_command` валидирует `actuator_id` и сохраняет команду.
- [Гипотеза] История сенсоров пока не реализована (`get_sensor_history`).

## Роль в системе и связи
- [Факт] Центральная точка доступа к конфигурации и I/O бота.
- [Гипотеза] Используется `BiosHandler`, `ShipCore` и другие компоненты.

## Несоответствия и риски
- [Факт][Med] Нет обработки ошибок при записи `.qiki_bot.id`.
- [Факт][Low] При `minimal` режиме функции возвращают `None`/пустые списки без логирования.
- [Гипотеза][Low] Отсутствует потокобезопасность при работе с колбэками.

## Мини-патчи (safe-fix)
- [Патч] Добавить логирование при работе в `minimal` режиме.
- [Патч] Оборачивать запись файлов в `try/except`.

## Рефактор-скетч
```python
class BotCore:
    BOT_ID_FILE = ".qiki_bot.id"
    CONFIG_FILE = "bot_config.json"

    def __init__(self, base_path: str):
        self.base_path = base_path
        self._config = {}
        self._sensor_callbacks = []
        self._load_config()
        self._initialize_bot_id()
```

## Примеры использования
```python
# 1. Создание экземпляра
from services.q_core_agent.core.bot_core import BotCore
bot = BotCore('/path/to/q_core_agent')

# 2. Получение идентификатора
print(bot.get_id())

# 3. Регистрация колбэка сенсора
from generated.sensor_raw_in_pb2 import SensorReading
bot.register_sensor_callback(lambda s: print(s.sensor_id))
bot._process_incoming_sensor_data(SensorReading(sensor_id='imu', value=1))

# 4. Отправка команды актуатору
from generated.actuator_raw_out_pb2 import ActuatorCommand
cmd = ActuatorCommand(actuator_id='motor_left', command='set_velocity_percent', value=50)
bot.send_actuator_command(cmd)

# 5. Получение последнего значения сенсора
bot.get_latest_sensor_value('imu')
```

## Тест-хуки/чек-лист
- Проверить генерацию нового ID при отсутствии файла.
- Убедиться, что неверный `actuator_id` вызывает `ValueError`.
- Проверить работу колбэков и обновление снимка сенсоров.

## Вывод
1. `BotCore` управляет конфигурацией и коммуникацией с устройствами.
2. Поддерживает режим `minimal` для тестов.
3. Риск средней степени: отсутствие обработки ошибок записи файлов.
4. Рекомендуется добавить логирование и защиту от гонок.
5. Набор колбэков расширяет возможности интеграции.
6. История сенсоров пока упрощена, нуждается в реализации.
7. Код хорошо структурирован и документирован.
8. Тесты должны покрывать генерацию ID и взаимодействие с актуаторами.
9. Возможна интеграция с внешними сервисами через gRPC.
10. Архитектура пригодна для дальнейшего развития.

СПИСОК ФАЙЛОВ
56. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/__init__.py
57. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/agent_logger.py
58. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/bios_handler.py
59. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/bot_core.py
60. [ ] /home/sonra44/QIKI_DTMP/services/q_core_agent/core/mission_control_demo.py
