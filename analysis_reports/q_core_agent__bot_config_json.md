# Анализ файла `services/q_core_agent/config/bot_config.json`

## Вход и цель
- [Факт] JSON с описанием бота и его аппаратного профиля.
- [Факт] Цель: проанализировать структуру и выявить риски.

## Сбор контекста
- [Факт] Файл загружается `BotCore` при запуске.
- [Факт] Отсутствие файла вызывает `FileNotFoundError`.
- [Гипотеза] Используется как для симуляции, так и для реального железа.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/config/bot_config.json`.
- [Факт] Читается через `json.load` в Python 3.x.

## Фактический разбор
- [Факт] `schema_version: "1.0"`.
- [Факт] `bot_id: "QIKI-DEFAULT-001"`, `bot_type: "default_bot"`, `mode: "full"`.
- [Факт] `hardware_profile.max_speed_mps: 1.0`, `power_capacity_wh: 500`.
- [Факт] Актуаторы: `motor_left`, `motor_right`, `system_controller`.
- [Факт] Сенсоры: `lidar_front`, `imu_main`.

## Роль в системе и связи
- [Факт] `BotCore` использует данные для инициализации датчиков и актуаторов.
- [Гипотеза] `system_controller` выступает мостом к управляющему компьютеру.

## Несоответствия и риски
- [Факт] Нет проверки `schema_version` и обязательных полей — **Med**.
- [Факт] Не описаны единицы измерения (например, `power_capacity_wh`) — **Low**.
- [Гипотеза] При `mode="minimal"` конфигурация может игнорироваться — **Low**.

## Мини-патчи (safe-fix)
- [Патч] Добавить валидацию `schema_version` и наличия `system_controller`.
- [Патч] Документировать единицы измерения в README или комментариях.

## Рефактор-скетч (по желанию)
```python
@dataclass
class HardwareProfile:
    max_speed_mps: float
    power_capacity_wh: float
    actuators: list
    sensors: list
```

## Примеры использования
```python
from q_core_agent.core.bot_core import BotCore
core = BotCore(base_path="services/q_core_agent")
print(core.get_property("hardware_profile")["actuators"])
```

## Тест-хуки/чек-лист
- [Факт] Проверить, что `BotCore` аварийно завершает работу при отсутствии `system_controller`.
- [Факт] Тест на недопустимое значение `max_speed_mps` (<0).

## Вывод
- [Факт] Файл определяет состав бота и его железо.
- [Гипотеза] Строгая проверка структуры снизит риск рассинхронизации.

## Стиль и маркировка
В отчёте использованы теги: [Факт], [Гипотеза], [Патч].
