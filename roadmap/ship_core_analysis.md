## СПИСОК ФАЙЛОВ
- services/q_core_agent/core/ship_core.py

### Вход и цель
Описать модуль `ship_core.py`, фиксируя назначение и текущую реализацию. Итог: обзор, список рисков, идеи безопасных правок и примеры использования.

### Сбор контекста
- [Факт] Изучен `ship_core.py` и соседние файлы `ship_actuators.py`, `ship_fsm_handler.py`, тесты `test_ship_diagnostics.py`, `test_ship_fsm.py`.
- [Гипотеза] Модуль применяется как центральная точка доступа к статическим и динамическим данным корабля для прочих сервисов.

### Локализация артефакта
`QIKI_DTMP/services/q_core_agent/core/ship_core.py` — Python 3.12, запускается как библиотека или напрямую из ядра агента.

### Фактический разбор
- Импорты: `json`, `os`, `hashlib`, dataclasses и protobuf-модули `sensor_raw_in_pb2`, `actuator_raw_out_pb2`.
- Классы-датаклассы: `HullStatus`, `PowerSystemStatus`, `PropulsionStatus`, `SensorStatus`, `LifeSupportStatus`, `ComputingStatus` — описывают состояния подсистем.
- Класс `ShipCore`:
  - Инициализация: загрузка конфигурации из `config/ship_config.json`, генерация ID и регистрация колбэков.
  - Методы получения статуса (`get_hull_status`, `get_power_status`, ...), работы с сенсорами и актуаторами.
  - Проверка `mode == "minimal"` отключает реальные действия с оборудованием.
- [Гипотеза] Конфиг JSON считается доверенным; отсутствует схема валидации.

### Роль в системе и связи
`ShipCore` служит базовым уровнем для FSM, диагностик и контроллеров актуаторов. Вызывается из `ShipFSMHandler` и тестовых скриптов, предоставляя агрегированную информацию о корабле.

### Несоответствия и риски
1. Отсутствие валидации структуры конфигурации — потенциал для `KeyError` (Med).
2. Прямой `print` вместо структурированного лога в некоторых местах (Low).
3. В `send_actuator_command` список систем собирается каждый вызов — накладные расходы (Low).

### Мини-патчи (safe-fix)
- [Патч] Добавить проверку наличия ключевых секций в конфиге перед использованием.
- [Патч] Заменить `print` на `logger` для единообразия логирования.
- [Патч] Кэшировать перечень доступных систем при инициализации.

### Рефактор-скетч (по желанию)
```python
class ShipCore:
    def __init__(self, base_path: str):
        self.base_path = base_path
        self._config = self._load_config()
        self._ship_id = self._init_ship_id()
        self._systems = self._collect_system_ids()
```

### Примеры использования
1. ```python
from core.ship_core import ShipCore
ship = ShipCore(base_path="./services/q_core_agent")
print(ship.get_id())
```
2. ```python
status = ship.get_power_status()
print(status.reactor_output_mw)
```
3. ```python
for sensor_id, reading in ship.current_sensor_snapshot.items():
    print(sensor_id, reading)
```
4. ```python
from generated import actuator_raw_out_pb2
cmd = actuator_raw_out_pb2.ActuatorCommand(actuator_id="thruster_a", command_type="START")
ship.send_actuator_command(cmd)
```
5. ```bash
python services/q_core_agent/core/ship_core.py
```

### Тест-хуки / чек-лист
- Запуск `pytest services/q_core_agent/core/test_ship_diagnostics.py`.
- Запуск `pytest services/q_core_agent/core/test_ship_fsm.py`.
- Проверка загрузки конфигурации при отсутствии файла.

### Вывод
`ShipCore` задаёт центральный API для состояния корабля и работы с сенсорами/актуаторами. Критично ввести валидацию конфигурации и единое логирование. В ближайших правках стоит добавить проверки ключей и заменить `print` на `logger`. Дальше — оптимизация сбора систем и усиление обработки ошибок.
