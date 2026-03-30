# СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/config/bot_config.json

## Вход и цель
- [Факт] Проанализировать конфигурацию бота и её структуру.
- [Факт] Итог: описание полей, рисков и способов использования.

## Сбор контекста
- [Факт] JSON описывает `schema_version`, `bot_id`, `bot_type`, `mode` и `hardware_profile`.
- [Гипотеза] Файл используется симулятором или контроллером для загрузки характеристик бота.

## Локализация артефакта
- [Факт] Путь: `/home/sonra44/QIKI_DTMP/services/q_core_agent/config/bot_config.json`.
- [Факт] Формат: JSON, вложенные объекты `hardware_profile` с массивами `actuators` и `sensors`.

## Фактический разбор
- [Факт] `schema_version: 1.0` — версия схемы.
- [Факт] `bot_id: QIKI-DEFAULT-001` — идентификатор бота.
- [Факт] `mode: full` — режим работы.
- [Факт] `actuators` включает `motor_left`, `motor_right`, `system_controller`.
- [Факт] `sensors` включает `lidar_front`, `imu_main`.
- [Гипотеза] Отсутствие проверок на дубли ID может привести к конфликтам.

## Роль в системе и связи
- [Факт] Определяет аппаратные возможности для модуля управления.
- [Гипотеза] Может использоваться при генерации симуляций и логов.

## Несоответствия и риски
- [Факт] Нет явной валидации `schema_version`. — Приоритет: Med.
- [Гипотеза] Отсутствие указания единицы измерения скорости. — Приоритет: Low.
- [Гипотеза] При расширении списка сенсоров возможна несогласованность типов. — Приоритет: Med.

## Мини-патчи (safe-fix)
- [Патч] Добавить поле `units` для скоростей и энергий.
- [Патч] Проверять уникальность `id` в массивах.
- [Патч] Ввести поле `description` для каждого сенсора.

## Рефактор-скетч (по желанию)
```python
from pydantic import BaseModel, Field

class Actuator(BaseModel):
    id: str
    type: str

class Sensor(BaseModel):
    id: str
    type: str

class HardwareProfile(BaseModel):
    max_speed_mps: float
    power_capacity_wh: int
    actuators: list[Actuator]
    sensors: list[Sensor]
```

## Примеры использования
```python
import json
cfg = json.load(open('config/bot_config.json'))
print(cfg['bot_id'])
```
```bash
jq '.hardware_profile.actuators[] | .id' config/bot_config.json
```
```python
import json
ids = {a['id'] for a in json.load(open('config/bot_config.json'))['hardware_profile']['actuators']}
```
```bash
python - <<'PY'
import json,sys
cfg=json.load(open('config/bot_config.json'))
print(len(cfg['hardware_profile']['sensors']))
PY
```
```bash
sed -n '1,20p' config/bot_config.json
```

## Тест-хуки/чек-лист
- Проверить уникальность `id` в `actuators` и `sensors`.
- Валидировать `schema_version` на соответствие поддерживаемым.
- Тест на отсутствующие обязательные поля.
- Проверить реакции на неизвестные типы устройств.
- Тест загрузки файла с неверным JSON.

## Вывод
- Конфиг задаёт базовые параметры бота.
- Структура проста, но отсутствуют единицы измерения.
- Нет встроенной валидации версии схемы.
- Расширение списков требует контроля уникальности.
- Добавление описаний улучшит читаемость.
- Валидация предотвратит ошибки конфигурации.
- Поддержка нескольких режимов может потребоваться позднее.
- Файл легко парсится стандартными средствами.
- Пример использования показал корректное чтение.
- Рекомендуется описать формат в отдельной спецификации.

# СПИСОК ФАЙЛОВ
- /home/sonra44/QIKI_DTMP/services/q_core_agent/config/bot_config.json
