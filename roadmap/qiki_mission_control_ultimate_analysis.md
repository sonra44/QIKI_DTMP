СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control_ultimate.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/rule_engine.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_actuators.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_bios_handler.py

# `/home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control_ultimate.py`

## Вход и цель
- [Факт] Модуль с интерфейсом `QIKIMissionControlUltimate` — полноценный терминал на `prompt_toolkit`.
- [Гипотеза] Итог — обзор поведения, поиск рисков, патч-скетч и примеры.

## Сбор контекста
- [Факт] Исходник использует `prompt_toolkit`; при отсутствии пытается установить библиотеку через `pip`.
- [Факт] Рядом в репо лежат `ship_core.py`, `ship_actuators.py`, `test_ship_fsm.py`.
- [Гипотеза] Тесты запускаются вручную, автоматической сборки нет.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/qiki_mission_control_ultimate.py`.
- [Факт] Окружение: Python 3.12+, Unix/Linux терминал, возможно Termux.
- [Гипотеза] Запуск как `python qiki_mission_control_ultimate.py`.

## Фактический разбор
- [Факт] Импорты: `prompt_toolkit`, `ShipCore`, `ShipActuatorController`, `ShipLogicController`.
- [Факт] Класс `QIKIMissionControlUltimate`: методы `log`, `_background_simulation`, `_update_live_telemetry`, UI-конструкторы (`_create_header_window`, `_create_layout`), `run_simple_mode`, `run`.
- [Факт] Хранит `mission_data`, `live_telemetry`, журнал событий.
- [Гипотеза] Поток `_background_simulation` симулирует параметры раз в несколько секунд.
- [Факт] Автопилот реализован через `ShipLogicController`.

## Роль в системе и связи
- [Факт] Служит фронтендом для управления кораблём.
- [Гипотеза] Вызывается оператором; отдаёт команды в `ShipActuatorController` и получает телеметрию из `ShipCore`.
- [Гипотеза] Риски: длительный UI-цикл блокирует другие процессы.

## Несоответствия и риски
- [Факт] Auto-pip внутри кода (установка `prompt_toolkit`) — Priority: High.
- [Гипотеза] Журнал событий ограничен 20 записями, возможна потеря важных данных — Priority: Med.
- [Гипотеза] Нет обработки исключений при запуске фонового потока — Priority: Med.

## Мини-патчи (safe-fix)
- [Патч] Удалить автоматическую установку `pip`, заменить на сообщение об ошибке.
- [Патч] Добавить параметр размера журнала и вынести в конфиг.
- [Патч] Обернуть запуск фонового потока в try/except с логированием.

## Рефактор-скетч (по желанию)
```python
# skeleton
class MissionControlUI:
    def __init__(self, core, actuators, logic, ui_factory):
        self.core = core
        self.actuators = actuators
        self.logic = logic
        self.ui = ui_factory()

    def run(self):
        while True:
            self.ui.render(self.core.telemetry())
```

## Примеры использования
```python
# 1. Запуск в упрощённом режиме
from qiki_mission_control_ultimate import QIKIMissionControlUltimate
mc = QIKIMissionControlUltimate()
mc.run_simple_mode()

# 2. Логирование события
mc.log("TEST", "Проверка")

# 3. Переключение автопилота
mc.autopilot_enabled = True

# 4. Получение времени миссии
print(mc._get_mission_time())

# 5. Завершение работы
mc.running = False
```

## Тест-хуки/чек-лист
- Проверить запуск без `prompt_toolkit` → корректная ошибка.
- Эмуляция обновления телеметрии: данные не выходят за границы.
- Фоновые потоки завершаются при `running=False`.
- В журнал добавляется не более N записей.
- Автопилот меняет `ship_state` при логическом цикле.

## Вывод
1. [Факт] Код создаёт профессиональный терминал.
2. [Гипотеза] Потоки могут привести к гонкам данных.
3. [Факт] Автопилот интегрирован, но не изолирован от UI.
4. [Гипотеза] Авто-pip затрудняет развёртывание.
5. [Факт] Живые данные симулируются случайно.
6. [Гипотеза] Нет логирования ошибок в UI.
7. [Патч] Ввести конфиги для параметров симуляции.
8. [Патч] Добавить тесты на перезапуск UI.
9. [Гипотеза] Возможно разделить модель и представление.
10. [Факт] Основные функции работают, но требуют отделения зависимостей.

СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control_ultimate.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/rule_engine.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_actuators.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_bios_handler.py
