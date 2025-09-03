СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control_ultimate.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/rule_engine.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_actuators.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_bios_handler.py

# `/home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control.py`

## Вход и цель
- [Факт] Модуль `QIKIMissionControl` — рабочий терминал без внешних зависимостей.
- [Гипотеза] Итог — обзор и рекомендации по безопасному использованию.

## Сбор контекста
- [Факт] Использует ручной ASCII-интерфейс через `termios` и `select`.
- [Гипотеза] В соседних файлах — `ship_actuators.py`, `test_ship_fsm.py`.
- [Факт] Содержит поток `_background_processes` для телеметрии.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/qiki_mission_control.py`.
- [Гипотеза] Запуск: `python qiki_mission_control.py` в обычном терминале.
- [Факт] Требует Python 3.10+.

## Фактический разбор
- [Факт] Импорты: `ShipCore`, `ShipActuatorController`, `ShipLogicController`.
- [Факт] Методы: `log`, `_background_processes`, `_update_live_parameters`, `display_status`, `execute_command`, `run_interactive`.
- [Факт] Хранит `navigation_data`, `sensor_data`, `mission_data`.
- [Гипотеза] Команды пользователя парсятся строково без проверки типов.

## Роль в системе и связи
- [Факт] Консольное управление кораблём; используется в тестах и демонстрации.
- [Гипотеза] Служит базовым CLI-интерфейсом для других модулей.

## Несоответствия и риски
- [Гипотеза] Отсутствие проверки пользовательских команд — Priority: High.
- [Факт] Поток обновления параметров не останавливается корректно — Priority: Med.
- [Гипотеза] Возможен переполнение `log_messages` при долгой сессии — Priority: Low.

## Мини-патчи (safe-fix)
- [Патч] Добавить в `execute_command` проверку допустимых команд.
- [Патч] В `run_interactive` закрывать поток через `join()`.
- [Патч] Ограничить `log_messages` по размеру.

## Рефактор-скетч
```python
def main():
    with MissionControl() as mc:
        while mc.running:
            cmd = input("> ")
            mc.execute_command(cmd)
```

## Примеры использования
```python
# 1. Старт терминала
from qiki_mission_control import QIKIMissionControl
mc = QIKIMissionControl()
mc.display_status()

# 2. Выполнение команды
mc.execute_command("thrust 25")

# 3. Получение телеметрии
telemetry = mc._get_telemetry()
print(telemetry["reactor_output"])

# 4. Запуск интерактивного режима
mc.run_interactive()

# 5. Завершение работы
mc.running = False
```

## Тест-хуки/чек-лист
- Проверка обработки неизвестных команд.
- Лимит `log_messages` ≤100.
- Фоновый поток завершается после `running=False`.
- Команда `thrust` вызывает `ShipActuatorController.set_main_drive_thrust`.
- Интерфейс корректно выводит строки без артефактов в `termios`.

## Вывод
1. [Факт] Модуль предоставляет CLI-управление без зависимостей.
2. [Гипотеза] Параметры миссии могут устаревать без синхронизации.
3. [Факт] Логирование ограничено только в памяти.
4. [Гипотеза] Командный синтаксис не стандартизирован.
5. [Патч] Ввести словарь разрешённых команд.
6. [Факт] Поток обновляет телеметрию каждые 3 сек.
7. [Гипотеза] Не хватает тестов для состояния `autopilot`.
8. [Патч] Разделить ввод/вывод и ядро логики.
9. [Гипотеза] Возможно внедрить очереди событий.
10. [Факт] Базовый CLI работает, но требует проверки ввода.

СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control_ultimate.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/rule_engine.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_actuators.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_bios_handler.py
