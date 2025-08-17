# Анализ файла `services/q_core_agent/config/logging.yaml`

## Вход и цель
- [Факт] Конфигурация логирования для сервиса.
- [Факт] Цель: разобрать текущую схему и отметить улучшения.

## Сбор контекста
- [Факт] Файл читается функцией `setup_logging` из `core/agent_logger.py`.
- [Гипотеза] Используется всеми компонентами через логгер `q_core_agent`.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/config/logging.yaml`.
- [Факт] Применяется через `logging.config.dictConfig`.

## Фактический разбор
- [Факт] `version: 1`, `disable_existing_loggers: false`.
- [Факт] Форматтер `simple` с шаблоном `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.
- [Факт] Обработчик `console` уровня `DEBUG`.
- [Факт] Логгер `q_core_agent` использует `console`, `propagate: no`.
- [Факт] Корневой логгер уровня `INFO`.

## Роль в системе и связи
- [Факт] `main.py` загружает файл перед запуском.
- [Гипотеза] Отсутствие файловых обработчиков усложняет аудит.

## Несоответствия и риски
- [Факт] Нет ротации и сохранения логов — **Med**.
- [Факт] Разница уровней `DEBUG`/`INFO` может создавать шум — **Low**.

## Мини-патчи (safe-fix)
- [Патч] Добавить `RotatingFileHandler` с ограничением размера.
- [Патч] Управлять уровнем логирования через `config.yaml`.

## Рефактор-скетч (по желанию)
```yaml
handlers:
  file:
    class: logging.handlers.RotatingFileHandler
    filename: q_core_agent.log
    maxBytes: 1048576
    backupCount: 3
    formatter: simple
loggers:
  q_core_agent:
    level: INFO
    handlers: [console, file]
```

## Примеры использования
```python
from q_core_agent.core.agent_logger import logger
logger.debug("debug line")
```

## Тест-хуки/чек-лист
- [Факт] Проверить загрузку конфигурации без ошибок.
- [Факт] Убедиться, что при добавлении `RotatingFileHandler` файл логов создаётся и ротируется.

## Вывод
- [Факт] Конфигурация минимальна и ориентирована на консоль.
- [Гипотеза] Ротация и централизованное управление уровнями улучшат наблюдаемость.

## Стиль и маркировка
В отчёте использованы теги: [Факт], [Гипотеза], [Патч].
