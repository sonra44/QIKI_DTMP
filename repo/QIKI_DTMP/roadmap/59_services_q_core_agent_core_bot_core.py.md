# Анализ: services/q_core_agent/core/bot_core.py

## Вход и цель
- [Факт] Описать устройство класса `BotCore`, отвечающего за идентификацию и конфигурацию бота.

## Сбор контекста
- [Факт] Импортирует `json`, `os`, `hashlib`, типы из `typing`, а также protobuf-модули `sensor_raw_in_pb2` и `actuator_raw_out_pb2`.
- [Факт] Использует конфигурационный файл `bot_config.json` и файл идентификатора `.qiki_bot.id`.
- [Гипотеза] Предполагается наличие подкаталога `config` с корректным JSON.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/bot_core.py`.
- [Факт] Запускается в Python 3, базовый путь передаётся параметром `base_path`.

## Фактический разбор
- [Факт] Константы `BOT_ID_FILE` и `CONFIG_FILE` задают имена служебных файлов.
- [Факт] `__init__` загружает конфиг, инициализирует ID, создаёт структуры для сенсоров и актуаторов.
- [Факт] `_load_config` читает JSON из `<base_path>/config/bot_config.json`, валидирует формат, печатает предупреждение в режиме `minimal`.
- [Факт] `_initialize_bot_id` читает существующий ID или генерирует новый через `_generate_bot_id`.
- [Факт] Методы `get_id`, `get_property`, `register_sensor_callback`, `_process_incoming_sensor_data`, `get_latest_sensor_value`, `get_sensor_history`, `send_actuator_command` реализуют API доступа к состоянию.
- [Факт] `send_actuator_command` проверяет ID актуатора против `hardware_profile` и сохраняет последнюю команду.

## Роль в системе и связи
- [Факт] Служит ядром для работы с конфигурацией, сенсорами и актуаторами, предоставляя базовые операции другим компонентам.
- [Гипотеза] Используется `QCoreAgent` и другими сервисами для взаимодействия с физическим или симулированным роботом.

## Несоответствия и риски
- [Гипотеза] Использование `print` вместо логгера затрудняет наблюдаемость (Med).
- [Гипотеза] Отсутствует защита от одновременного доступа к `_runtime_sensor_snapshot` (Low).
- [Гипотеза] Метод `get_sensor_history` возвращает только последнее значение и может вводить в заблуждение (Low).

## Мини-патчи (safe-fix)
- [Патч] Заменить `print` на вызовы `logger` из `agent_logger`.
- [Патч] Возвращать `None` при отсутствии ID в `get_id` вместо `RuntimeError`.
- [Патч] Добавить блокировку или копирование словарей при чтении/записи сенсорных данных.

## Рефактор-скетч (по желанию)
```python
class BotCore:
    def __init__(self, base_path: str, log: logging.Logger = logger):
        self.log = log
        ...

    def send_actuator_command(self, command):
        if self._config.get("mode") == "minimal":
            self.log.info("Minimal mode: command ignored")
            return
        ...
```

## Примеры использования
```python
bot = BotCore(base_path="/opt/qiki")
bot.get_id()
bot.send_actuator_command(actuator_raw_out_pb2.ActuatorCommand(actuator_id="motor", command="start"))
```

## Тест-хуки/чек-лист
- [Факт] Валидная конфигурация — методы `get_id` и `get_property` возвращают значения.
- [Факт] Режим `minimal` — `send_actuator_command` ничего не делает и печатает предупреждение.
- [Факт] Неверный ID актуатора — ожидается `ValueError`.

## Вывод
- [Факт] `BotCore` управляет конфигурацией и взаимодействием с сенсорами/актуаторами.
- [Патч] Следует заменить вывод в stdout на централизованный логгер и усилить потокобезопасность.
