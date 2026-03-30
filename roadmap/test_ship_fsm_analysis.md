## СПИСОК ФАЙЛОВ
- services/q_core_agent/core/test_ship_fsm.py

### Вход и цель
Проанализировать `test_ship_fsm.py`, описать тестовую логику FSM и дать рекомендации по улучшению. Итог: обзор, риски, патчи, примеры.

### Сбор контекста
- [Факт] Файл определяет упрощенный `ShipLogicController` с собственным циклом состояний.
- [Факт] Тест выполняет до восьми логических циклов с симуляцией действий.
- [Гипотеза] Используется как интеграционный тест для проверки переходов без protobuf.

### Локализация артефакта
`QIKI_DTMP/services/q_core_agent/core/test_ship_fsm.py` — самостоятельный скрипт/тест, не требует генерации protobuf для запуска.

### Фактический разбор
- Импорты: `ShipCore`, `ShipActuatorController`, `PropulsionMode`, `ThrusterAxis`.
- Класс `ShipLogicController` реализует методы проверки систем и навигации, управляет `current_state` и выполняет переходы.
- Тест `test_ship_logic_controller` инициализирует корабль, запускает цикл и выводит результаты.
- Возвращает `bool`, что вызывает предупреждение pytest, аналогично предыдущему тесту.

### Роль в системе и связи
Служит эмуляцией FSM для быстрого проговора сценариев полета. Позволяет проверить реакции `ShipActuatorController` и `ShipCore` без настоящего protobuf состояния.

### Несоответствия и риски
1. Нет утверждений — результат теста определяется возвратом значения (Med).
2. Избыточные `print` усложняют автоматизированный анализ (Low).
3. Логика теста зависит от внешних файлов конфигурации (Low).

### Мини-патчи (safe-fix)
- [Патч] Использовать `assert result['state_changed']` или другие проверки вместо возврата.
- [Патч] Структурировать вывод через логгер.
- [Патч] Вынести симуляции (включение двигателя, RCS) в отдельные функции для повторного использования.

### Рефактор-скетч (по желанию)
```python
def test_ship_logic_controller():
    controller = ShipLogicController(ship, actuator)
    for _ in range(5):
        res = controller.process_logic_cycle()
        assert res['current_state'] in VALID_STATES
```

### Примеры использования
1. ```bash
pytest services/q_core_agent/core/test_ship_fsm.py -q
```
2. ```bash
python services/q_core_agent/core/test_ship_fsm.py
```
3. ```python
controller = ShipLogicController(ship, actuator_controller)
res = controller.process_logic_cycle()
```
4. ```python
controller.actuator_controller.set_main_drive_thrust(50.0)
```
5. ```bash
python -m pdb services/q_core_agent/core/test_ship_fsm.py
```

### Тест-хуки / чек-лист
- Проверка переходов при разных режимах двигателей.
- Проверка реакции на отключение критичных систем.
- Валидировать, что цикл завершает работу при стабилизации состояний.

### Вывод
`test_ship_fsm.py` реализует демонстрационный тест FSM, но полагается на вывод вместо строгих проверок. Для повышения надежности необходимо заменить возвраты на `assert` и структурировать симуляции. После изменений тест сможет служить автоматизированным регресс-тестом для логики FSM.
