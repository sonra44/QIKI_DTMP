# Анализ `tools/qiki_docgen/core/config.py`

## Вход и цель
- [Факт] Анализ модуля конфигурации `qiki_docgen`.
- [Факт] Итог: описание API, рисков и предложений.

## Сбор контекста
- [Факт] Импортирует `Path`, `Dict`, `Any`, `List`, `logging`.
- [Факт] Реализует класс `QikiDocgenConfig` и функцию `get_config`.
- [Гипотеза] Используется остальными модулями `qiki_docgen` для доступа к настройкам.

## Локализация артефакта
- [Факт] Путь: `tools/qiki_docgen/core/config.py`.
- [Факт] Окружение: Python ≥3.8, без внешней зависимости `yaml`.
- [Гипотеза] Вызывается через `from tools.qiki_docgen.core.config import get_config`.

## Фактический разбор
- [Факт] `QikiDocgenConfig.__init__` определяет корень проекта и загружает YAML.
- [Факт] `_find_project_root` ищет маркеры: `protos`, `services`, `docs`, `README.md`.
- [Факт] `_load_config` читает `config.yaml` или использует `_get_default_config` при ошибке.
- [Факт] `_parse_yaml` — самописный парсер с поддержкой секций и списков.
- [Факт] `_parse_value` приводит строки к `bool`/числам/строкам без кавычек.
- [Факт] Методы `get_path`, `get_protoc_includes`, `get` предоставляют доступ к данным.
- [Факт] `get_config()` реализует ленивый синглтон.

## Роль в системе и связи
- [Факт] Центральная точка доступа к настройкам `qiki-docgen`.
- [Гипотеза] Ошибка парсинга YAML может нарушить генерацию документации.

## Несоответствия и риски
- [Гипотеза][High] Ручной YAML-парсер не покрывает сложные конструкции и может работать некорректно.
- [Гипотеза][Med] `_find_project_root` зависит от жёстко заданных маркеров.
- [Гипотеза][Low] `get_config` не потокобезопасен.

## Мини-патчи (safe-fix)
- [Патч] Использовать `yaml.safe_load` вместо `_parse_yaml`.
- [Патч] Добавить проверку `config_path` и явное исключение при отсутствии файла.
- [Патч] Защитить синглтон блокировкой при многопоточном доступе.

## Рефактор-скетч
```python
import yaml
class QikiDocgenConfig:
    def _load_config(self):
        if self.config_path and self.config_path.exists():
            self._config_data = yaml.safe_load(self.config_path.read_text())
        else:
            self._config_data = self._get_default_config()
```

## Примеры использования
```python
from tools.qiki_docgen.core.config import get_config
cfg = get_config()
print(cfg.get_path('docs_dir'))
```

## Тест-хуки/чек-лист
- Тест `_parse_yaml` (или `yaml.safe_load`) на корректный парсинг и обработку ошибок.
- Проверка `get_protoc_includes` с существующими и отсутствующими путями.
- Тест, что повторные вызовы `get_config` возвращают один и тот же объект.
- Интеграционный тест с реальным `config.yaml`.

## Вывод
- [Факт] Модуль предоставляет загрузку конфигурации без внешних зависимостей.
- Первые шаги: перейти на `yaml.safe_load` и улучшить определение корня проекта; далее — расширять API и потокобезопасность.
