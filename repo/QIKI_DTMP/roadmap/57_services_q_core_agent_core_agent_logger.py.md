# Анализ: services/q_core_agent/core/agent_logger.py

## Вход и цель
- [Факт] Изучить модуль `agent_logger` и описать его назначение.

## Сбор контекста
- [Факт] Использует стандартный модуль `logging`, `logging.config`, а также стороннюю библиотеку `yaml`.
- [Факт] Глобальный логгер `q_core_agent` и функция `setup_logging`.
- [Гипотеза] Конфигурационный файл `logging.yaml` располагается рядом со стартовым скриптом.

## Локализация артефакта
- [Факт] Путь: `services/q_core_agent/core/agent_logger.py`.
- [Факт] Выполняется в среде Python 3; используется другими модулями через `from .agent_logger import logger`.

## Фактический разбор
- [Факт] `setup_logging(default_path='logging.yaml', default_level=logging.INFO, env_key='LOG_CFG')` — читает YAML-файл и настраивает логирование через `logging.config.dictConfig`.
- [Факт] При отсутствии файла или ошибке выводит сообщение `print` и включает `logging.basicConfig`.
- [Факт] Глобальная переменная `logger = logging.getLogger("q_core_agent")`.

## Роль в системе и связи
- [Факт] Обеспечивает единообразную настройку логирования для всех компонентов Q-Core Agent.
- [Гипотеза] Файл `logging.yaml` поставляется вместе с сервисом и может переопределяться переменной окружения `LOG_CFG`.

## Несоответствия и риски
- [Гипотеза] Использование `print` вместо логгера при ошибках снижает наблюдаемость (Med).
- [Гипотеза] Широкий `except Exception` скрывает тип ошибки конфигурации (Med).

## Мини-патчи (safe-fix)
- [Патч] Заменить `print` на `logging.error` и логировать стектрейс.
- [Патч] Ограничить перехват исключений до `yaml.YAMLError` и `OSError`.

## Рефактор-скетч (по желанию)
```python
import logging, logging.config, os, yaml

def setup_logging(path="logging.yaml", level=logging.INFO, env_key="LOG_CFG"):
    cfg_path = os.getenv(env_key, path)
    try:
        with open(cfg_path) as fh:
            config = yaml.safe_load(fh)
        logging.config.dictConfig(config)
    except (yaml.YAMLError, OSError) as e:
        logging.basicConfig(level=level)
        logging.getLogger(__name__).exception("Logging config failed: %s", e)
```

## Примеры использования
```python
from services.q_core_agent.core.agent_logger import setup_logging, logger
setup_logging()
logger.info("Старт агента")
```

## Тест-хуки/чек-лист
- [Факт] Подставить корректный `logging.yaml` и проверить запись в файл.
- [Факт] Удалить/испортить `logging.yaml` и убедиться, что используется базовая конфигурация без падения.

## Вывод
- [Факт] Модуль централизует настройку логов.
- [Патч] Улучшить обработку ошибок и заменить `print` на сообщения логгера.
