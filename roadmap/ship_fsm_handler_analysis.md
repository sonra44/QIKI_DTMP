## СПИСОК ФАЙЛОВ
- services/q_core_agent/core/ship_fsm_handler.py

### Вход и цель
Проанализировать `ship_fsm_handler.py`, описать логику конечного автомата корабля и указать потенциальные улучшения. Итог: обзор, риски, мини-патчи, примеры.

### Сбор контекста
- [Факт] Изучены `ship_fsm_handler.py`, `ship_core.py`, `ship_actuators.py`, тесты `test_ship_fsm.py`.
- [Гипотеза] Модуль предназначен для использования как часть агента управления кораблем без внешних зависимостей кроме protobuf.

### Локализация артефакта
`QIKI_DTMP/services/q_core_agent/core/ship_fsm_handler.py` — Python 3.12, импортирует сгенерированные protobuf-сообщения и внутренние интерфейсы.

### Фактический разбор
- Импорты: `enum`, `typing`, внутренние модули (`ShipCore`, `ShipActuatorController`, `logger`).
- Определения:
  - `ShipState` — Enum со стадиями: запуск, ожидание, полет, стыковка, авария.
  - `ShipContext` — обертка с проверками систем и навигации.
  - `ShipFSMHandler` реализует `IFSMHandler` и метод `process_fsm_state` с переходами между состояниями.
- Логика переходов учитывает состояние систем, режим двигателей и наличие цели стыковки.
- [Гипотеза] Реализация рассчитана на последовательную обработку циклом контроля; конкуренция не учитывается.

### Роль в системе и связи
Обеспечивает основную логику переходов корабля для FSM, опираясь на данные из `ShipCore` и команды `ShipActuatorController`.

### Несоответствия и риски
1. Логика стыковки не завершена (`TODO`) — переходы могут зациклиться (Med).
2. Количество `if/elif` усложняет расширение состояний (Low).
3. При ошибках зависимостей используются `ImportError` заглушки, что может скрыть реальные проблемы (Low).

### Мини-патчи (safe-fix)
- [Патч] Добавить обработку отсутствия цели стыковки с явным кодом возврата.
- [Патч] Перенести константы логирования в централизованный конфиг.
- [Патч] Документировать структуру `FSMState` для улучшения читаемости.

### Рефактор-скетч (по желанию)
```python
class ShipFSMHandler(IFSMHandler):
    transitions = {
        ShipState.SHIP_STARTUP: handle_startup,
        ShipState.SHIP_IDLE: handle_idle,
        # ...
    }
    def process_fsm_state(self, state):
        return self.transitions[state.current_state_name](state)
```

### Примеры использования
1. ```python
from core.ship_core import ShipCore
from core.ship_actuators import ShipActuatorController
from core.ship_fsm_handler import ShipFSMHandler
ship = ShipCore(base_path="./services/q_core_agent")
controller = ShipActuatorController(ship)
fsm = ShipFSMHandler(ship, controller)
```
2. ```python
from generated.fsm_state_pb2 import FSMState
state = FSMState()
state.current_state_name = "SHIP_STARTUP"
next_state = fsm.process_fsm_state(state)
```
3. ```python
summary = fsm.get_ship_state_summary()
print(summary['ready_for_flight'])
```
4. ```python
controller.set_main_drive_thrust(30.0)
state = fsm.process_fsm_state(state)
```
5. ```bash
python services/q_core_agent/core/ship_fsm_handler.py
```

### Тест-хуки / чек-лист
- `pytest services/q_core_agent/core/test_ship_fsm.py`.
- Проверка переходов при отключенных системах (`is_ship_systems_ok` возвращает False).
- Симуляция отсутствия стыковочной цели.

### Вывод
`ShipFSMHandler` реализует управляемый переход состояний корабля, опираясь на диагностику из `ShipCore`. Основные улучшения — завершить сценарий стыковки, упростить структуру переходов и укрепить обработку ошибок. Ближайшие действия: доработать ветку стыковки и добавить документацию по форматам состояний.
