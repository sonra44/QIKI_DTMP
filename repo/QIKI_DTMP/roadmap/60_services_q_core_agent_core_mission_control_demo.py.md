# Анализ: services/q_core_agent/core/mission_control_demo.py

## Вход и цель
- [Факт] Разобрать демонстрационный скрипт `MissionControlDemo`, имитирующий консоль NASA/военного кокпита.

## Сбор контекста
- [Факт] Импортирует `ShipCore`, `ShipActuatorController`, `ShipLogicController` и стандартные модули (`sys`, `os`, `time`, `datetime`).
- [Факт] Использует ANSI-терминал для визуализации и ввод команд через `input`.
- [Гипотеза] Скрипт предназначен исключительно для демонстраций и не входит в продакшн.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/mission_control_demo.py`.
- [Факт] Запускается как скрипт (`#!/usr/bin/env python3`).

## Фактический разбор
- [Факт] Класс `MissionControlDemo` инициализирует `ShipCore`, `ShipActuatorController`, `ShipLogicController` и хранит стартовое время миссии.
- [Факт] Методы: `get_mission_time`, `get_telemetry`, `format_bar`, `get_alert_level`, `render_interface`, `execute_demo_command`, `interactive_demo`, `simulate_mission_scenario`, `main`.
- [Факт] `execute_demo_command` разбирает текстовые команды (`thrust`, `rcs`, `sensor`, `power`, `status`).
- [Факт] `interactive_demo` запускает цикл ввода/вывода до команды `exit`.

## Роль в системе и связи
- [Факт] Предоставляет интерфейс для тестирования логики корабля и визуализации телеметрии.
- [Гипотеза] Используется разработчиками для демонстрации возможностей QIKI.

## Несоответствия и риски
- [Гипотеза] Отсутствует обработка некорректного формата команд — возможны неочевидные ошибки (Med).
- [Гипотеза] Зависит от файлов и классов `ship_core`, `ship_actuators`, `test_ship_fsm`, которые могут измениться (Low).

## Мини-патчи (safe-fix)
- [Патч] Добавить проверку количества аргументов в `execute_demo_command` и вывод справки при ошибке.
- [Патч] Логировать исключения вместо простого `print`.

## Рефактор-скетч (по желанию)
```python
def execute_demo_command(self, command: str):
    try:
        parts = command.split()
        if not parts:
            return
        cmd, *args = parts
        handler = {
            "thrust": self._cmd_thrust,
            "rcs": self._cmd_rcs,
        }.get(cmd)
        if handler:
            handler(*args)
        else:
            self.log.warning("Unknown command: %s", cmd)
    except Exception:
        self.log.exception("Command failed")
```

## Примеры использования
```bash
python services/q_core_agent/core/mission_control_demo.py
# далее выбирать режим и вводить команды
```

## Тест-хуки/чек-лист
- [Факт] Команда `thrust 50` — ожидается изменение тяги без ошибок.
- [Факт] Неверная команда должна выводить предупреждение и не прерывать цикл.

## Вывод
- [Факт] Скрипт демонстрирует полный интерфейс миссии и служит обучающим примером.
- [Патч] Рекомендуется усилить проверку аргументов команд и заменить `print` на логирование.
