СПИСОК ФАЙЛОВ
- services/q_sim_service/main.py

## Вход и цель
[Факт] Необходимо разобрать модуль симулятора `q_sim_service/main.py` и подготовить обзор, риски и мини-патчи.

## Сбор контекста
- [Факт] Рядом лежат `config.yaml`, `core/world_model.py`, `grpc_server.py`.
- [Гипотеза] Очереди сенсоров/актуаторов предназначены для обмена с gRPC‑сервером.

## Локализация артефакта
[Факт] Путь: `services/q_sim_service/main.py` внутри проекта QIKI_DTMP; Python 3.12.
[Гипотеза] Запуск через `python services/q_sim_service/main.py` в виртуальном окружении.

## Фактический разбор
- Импорты: time, yaml, protobuf‑типы, `WorldModel`.
- Класс `QSimService`:
    - [Факт] Инициализирует `WorldModel` и две очереди.
    - [Факт] `generate_sensor_data` возвращает `SensorReading` с текущей X‑координатой.
    - [Факт] `receive_actuator_command` логирует и обновляет модель.
    - [Факт] `step` двигает мир и генерирует данные.
- Функция `load_config` считывает YAML с диска.
- Граничные случаи:
    - [Гипотеза] Неограниченный рост очередей может привести к утечке памяти.

## Роль в системе и связи
- [Факт] Модуль запускает цикл симуляции и служит источником сенсорных данных.
- [Гипотеза] Используется в интеграционных тестах для имитации реального робота.

## Несоответствия и риски
- [Факт] Отсутствует обработка ошибок при загрузке YAML. (Med)
- [Факт] Очереди не ограничены по размеру. (High)
- [Гипотеза] Добавление `ROOT_DIR` в `sys.path` без проверки может дублировать путь. (Low)

## Мини-патчи (safe-fix)
- [Патч] Ограничить размер очередей и сбрасывать старые элементы.
- [Патч] Обернуть `yaml.safe_load` в `try/except`.
- [Патч] Проверять наличие `ROOT_DIR` в `sys.path` перед добавлением.

## Рефактор-скетч
```python
class QSimService:
    def __init__(self, config: dict, max_queue: int = 100):
        self.sensor_data_queue: deque = deque(maxlen=max_queue)
        self.actuator_command_queue: deque = deque(maxlen=max_queue)
```

## Примеры использования
```python
# 1. Запуск одного шага симуляции
cfg = {"sim_tick_interval": 1}
svc = QSimService(cfg)
svc.step()
```
```python
# 2. Отправка команды актуатору
cmd = ActuatorCommand(actuator_id=UUID(value="motor_left"), command_type="set_velocity_percent", int_value=50)
svc.receive_actuator_command(cmd)
```
```python
# 3. Получение сенсорных данных
sensor = svc.generate_sensor_data()
print(sensor.scalar_data)
```
```python
# 4. Загрузка конфигурации из файла
config = load_config("config.yaml")
svc = QSimService(config)
```
```bash
# 5. Полный запуск сервиса
python services/q_sim_service/main.py
```

## Тест-хуки/чек-лист
- [Факт] Проверить, что `step` обновляет позицию при заданной скорости.
- [Факт] Убедиться, что очередь не превышает `max_queue` после патча.
- [Гипотеза] Интеграционный тест с gRPC‑сервером для обмена команд.

## Вывод
1. Модуль запускает бесконечную симуляцию.
2. Очереди данных не ограничены.
3. Логирование уже настроено через `setup_logging`.
4. Конфигурация читается из YAML без валидации.
5. Мир обновляется простыми кинематическими формулами.
6. Ошибки загрузки конфигурации не перехватываются.
7. Отсутствует очистка очередей.
8. Потенциально полезно добавить типы и докстринги.
9. Возможен дубликат `ROOT_DIR` в `sys.path`.
10. Первым шагом стоит добавить защиту очередей и обработку YAML.

СПИСОК ФАЙЛОВ
- services/q_sim_service/main.py
