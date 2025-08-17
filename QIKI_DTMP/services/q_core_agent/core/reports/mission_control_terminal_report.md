# mission_control_terminal.py — обзор

## Вход и цель
- [Факт] анализ модуля `mission_control_terminal.py` с целью составить обзор и выявить задачи

## Сбор контекста
- [Факт] исходник содержит интерфейс терминала на `prompt_toolkit`
- [Факт] рядом используются модули `ship_core`, `ship_actuators`, `test_ship_fsm`
- [Гипотеза] предполагается интеграция с реальным космическим симулятором

## Локализация артефакта
- [Факт] путь: `services/q_core_agent/core/mission_control_terminal.py`
- [Гипотеза] запускается как скрипт `python mission_control_terminal.py`

## Фактический разбор
- [Факт] класс `MissionControlTerminal` управляет логикой интерфейса
- [Факт] запускает поток `_background_update` для телеметрии
- [Факт] методы `_update_telemetry`, `_check_system_alerts` следят за состоянием
- [Факт] интерфейс строится функциями `_create_header`, `_create_telemetry_panel`, `_create_propulsion_panel`
- [Гипотеза] отсутствие явного `asyncio` цикла может вызвать блокировки

## Роль в системе и связи
- [Факт] терминал обращается к `ShipCore` и контроллерам актюаторов
- [Гипотеза] используется операторами для мониторинга и управления

## Несоответствия и риски
- [Факт] поток фоновых обновлений не имеет безопасного завершения (Med)
- [Гипотеза] прямой вызов `os.system("pip install...")` (Low)

## Мини-патчи (safe-fix)
- [Патч] добавить флаг остановки и `join()` при завершении
- [Патч] заменить `os.system` на `subprocess.run` с обработкой ошибок

## Рефактор-скетч
```python
class MissionControlTerminal:
    def __init__(self, ship_core):
        self.ship_core = ship_core
        self.running = True
        self.thread = Thread(target=self._update, daemon=True)
```

## Примеры использования
```python
from mission_control_terminal import MissionControlTerminal
term = MissionControlTerminal()
```

## Тест-хуки/чек-лист
- [Факт] unit-тест: проверка смены `alert_level`
- [Гипотеза] интеграционный тест: запуск и остановка фонового потока

## Вывод
- [Факт] модуль предоставляет богатый терминал, но требует аккуратного завершения потоков
- [Патч] рекомендуется добавить управление ресурсами и исключить установку пакетов в рантайме

## Стиль и маркировка
- [Факт] — по исходнику
- [Гипотеза] — по косвенным признакам
- [Патч] — предложенные изменения
