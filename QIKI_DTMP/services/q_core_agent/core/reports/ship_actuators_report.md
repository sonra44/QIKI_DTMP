# Отчет: ship_actuators.py

## Вход и цель
- [Факт] Анализ модуля `ship_actuators.py`; цель — описать управление исполнительными системами и предложить улучшения.

## Сбор контекста
- [Факт] Модуль зависит от `ShipCore`, protobuf-классов и перечислений `ThrusterAxis`, `PropulsionMode`.
- [Гипотеза] Используется как слой между логикой и низкоуровневыми командами актюаторов.

## Локализация артефакта
- [Факт] Путь: `QIKI_DTMP/services/q_core_agent/core/ship_actuators.py`.
- [Факт] Использование: импорт `ShipActuatorController`, вызов методов `set_main_drive_thrust`, `fire_rcs_thruster` и т.д.

## Фактический разбор
- [Факт] Определены enum `ThrusterAxis` и `PropulsionMode` для направления и режима тяги.
- [Факт] Класс `ShipActuatorController` отправляет команды через `ShipCore.send_actuator_command`.
- [Факт] Метод `set_main_drive_thrust` нормализует процент тяги и обновляет `current_mode`.
- [Гипотеза] В `fire_rcs_thruster` не реализованы оси UP/DOWN и проверка диапазона `duration_sec`.

## Роль в системе и связи
- [Факт] Служит интерфейсом для высокоуровневого управления двигателями и распределением мощности.
- [Гипотеза] Может использоваться как точка интеграции с автопилотом и ручным управлением.

## Несоответствия и риски
- [Гипотеза][Med] Неполный `thruster_map` может привести к неправильным командам по осям Z.
- [Гипотеза][Low] Отсутствие валидации входных данных для `duration_sec` и `thrust_percent`.

## Мини-патчи (safe-fix)
- [Патч] Дополнить `thruster_map` направлениями `UP` и `DOWN`.
- [Патч] Добавить проверку `0 < duration_sec <= 5` для RCS.

## Рефактор-скетч (по желанию)
```python
class ShipActuatorController:
    def set_main_drive_thrust(self, percent: float) -> bool:
        cmd = build_command("ion_drive_array", percent)
        return self._send(cmd)
```

## Примеры использования
- [Факт]
```python
controller = ShipActuatorController(core)
controller.set_main_drive_thrust(50)
```
- [Гипотеза]
```python
controller.fire_rcs_thruster(ThrusterAxis.PORT, 20, duration_sec=2)
```

## Тест-хуки/чек-лист
- [Факт] Проверить, что `set_main_drive_thrust(120)` ограничивается 100%.
- [Гипотеза] Тест на корректное сопоставление `ThrusterAxis.UP` с идентификатором актюатора.

## Вывод
- [Факт] Модуль предоставляет базовые средства управления тяговыми системами.
- [Патч] Первостепенно требуется расширить карту двигателей и добавить валидацию входных параметров; рефакторинг API можно провести позже.
