СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control_ultimate.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/rule_engine.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_actuators.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_bios_handler.py

# `/home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_actuators.py`

## Вход и цель
- [Факт] Модуль управления исполнительными механизмами (`ShipActuatorController`).
- [Гипотеза] Итог — обзор методов управления, безопасные патчи.

## Сбор контекста
- [Факт] Импортирует `ShipCore` и Protobuf `ActuatorCommand`.
- [Факт] Определяет enum `ThrusterAxis`, `PropulsionMode`, dataclass `ThrustVector`, `PowerAllocation`.
- [Гипотеза] Используется в миссион контроле и автопилоте.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/ship_actuators.py`.
- [Гипотеза] Требует наличия `ShipCore` с методом `send_actuator_command`.

## Фактический разбор
- [Факт] Методы: `set_main_drive_thrust`, `fire_rcs_thruster`, `execute_maneuver`, `emergency_stop`, `set_power_allocation`, `activate_sensor`, `deactivate_sensor`, `get_propulsion_status`, `get_control_summary`.
- [Факт] Использует `ActuatorCommand` с полями `command_type`, `unit`, `ack_required`.
- [Гипотеза] Исключения ведут к `False` без детальной информации.

## Роль в системе и связи
- [Факт] Интерфейс высокого уровня между миссион-контролем и низкоуровневыми актуаторами.
- [Гипотеза] Неправильные параметры могут вызвать некорректное состояние пропульсии.

## Несоответствия и риски
- [Гипотеза] Отсутствует проверка связи с `ShipCore` перед отправкой — Priority: High.
- [Факт] `emergency_stop` не гарантирует подтверждения — Priority: Med.
- [Гипотеза] Некорректные значения `duration_sec` могут не валидироваться — Priority: Med.

## Мини-патчи
- [Патч] Проверять `self.ship_core` на `None` перед отправкой команд.
- [Патч] В методах приводить `duration_sec` к целому таймауту ≥0.
- [Патч] Логировать возвращаемые значения `False` с причиной.

## Рефактор-скетч
```python
class ActuatorController:
    def send(self, id, value, unit):
        cmd = ActuatorCommand(actuator_id=UUID(value=id),
                              float_value=value, unit=unit)
        self.ship_core.send_actuator_command(cmd)
```

## Примеры использования
```python
# 1. Установка тяги основного двигателя
controller.set_main_drive_thrust(75.0)

# 2. Импульс RCS вперёд
controller.fire_rcs_thruster(ThrusterAxis.FORWARD, 20.0, 0.5)

# 3. Сложный манёвр
vector = ThrustVector(x=5.0, y=0.0, z=-2.0)
controller.execute_maneuver(vector, 3.0)

# 4. Распределение питания
alloc = PowerAllocation(life_support=10, propulsion=20, sensors=4)
controller.set_power_allocation(alloc)

# 5. Получение статуса
print(controller.get_control_summary())
```

## Тест-хуки/чек-лист
- Вызов `set_main_drive_thrust` с >100 → ограничение до 100.
- Ошибка связи с `ship_core` → возвращает `False` и логирует.
- `execute_maneuver` корректно формирует вектор команд.
- `emergency_stop` отправляет команду `SET_VELOCITY` с 0 %.
- `activate_sensor`/`deactivate_sensor` изменяют состояние без конфликта.

## Вывод
1. [Факт] Контроллер объединяет управление двигателями и сенсорами.
2. [Гипотеза] Нет централизованной проверки входных данных.
3. [Факт] Используются enums для читаемости.
4. [Гипотеза] Возможны гонки при параллельных командах.
5. [Патч] Добавить блокировки или очередь команд.
6. [Факт] Методы возвращают bool без расшифровки ошибок.
7. [Патч] Вернуть объект результата с кодом.
8. [Гипотеза] Отсутствуют юнит-тесты на `PowerAllocation`.
9. [Факт] Зависит от внешних Proto-классов.
10. [Гипотеза] Для модульности можно изолировать отправку команд в отдельный слой.

СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control_ultimate.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/qiki_mission_control.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/rule_engine.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_actuators.py
- /home/sonra44/QIKI_DTMP/services/q_core_agent/core/ship_bios_handler.py
