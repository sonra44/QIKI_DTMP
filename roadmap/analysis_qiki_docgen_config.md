СПИСОК ФАЙЛОВ
- tools/qiki_docgen/config.yaml

## Вход и цель
[Факт] Разобрать конфигурацию `qiki_docgen` и выделить ключевые настройки.

## Сбор контекста
- [Факт] YAML описывает пути, параметры protoc, генерацию и логирование.
- [Гипотеза] Файл используется модулем `core.config` при загрузке.

## Локализация артефакта
[Факт] Путь: `tools/qiki_docgen/config.yaml`.
[Гипотеза] Загружается при инициализации `QikiDocgenConfig`.

## Фактический разбор
- `paths`:
    - [Факт] `protos_dir`, `generated_dir`, `docs_dir`, `design_dir`, `templates_dir`.
    - [Факт] `protoc_includes` содержит системные пути.
- `protoc`:
    - [Факт] Флаг `--python_out`.
    - [Факт] Опции `generate_pyi`, `package_relative`.
- `generation`:
    - [Факт] `default_template`, `available_templates`.
    - [Факт] `readme` с настройками `include_proto_stats`, `max_overview_length`.
- `logging` и `compatibility` секции задают уровень и требования версий.
- Граничные случаи:
    - [Гипотеза] Список include путей может содержать несуществующие директории.

## Роль в системе и связи
- [Факт] Конфигурация управляет генерацией документации и путями.
- [Гипотеза] Может переопределяться пользователем для адаптации окружения.

## Несоответствия и риски
- [Факт] Жёстко закодированные пути могут не работать на другой платформе. (Med)
- [Гипотеза] Отсутствие версионирования шаблонов. (Low)

## Мини-патчи (safe-fix)
- [Патч] Сделать include пути относительными к проекту или проверять их существование.
- [Патч] Добавить возможность отключать `check_protoc_version`.

## Рефактор-скетч
```yaml
paths:
  protos_dir: "protos"
  generated_dir: "generated"
```

## Примеры использования
```python
# 1. Чтение конфигурации
import yaml, pathlib
cfg = yaml.safe_load(pathlib.Path('tools/qiki_docgen/config.yaml').read_text())
```
```python
# 2. Получение шаблонов
print(cfg['generation']['available_templates'])
```
```bash
# 3. Проверка существования include путей
while read p; do [ -d "$p" ] && echo ok "$p"; done < <(yq '.paths.protoc_includes[]' tools/qiki_docgen/config.yaml)
```
```python
# 4. Использование в QikiDocgenConfig
from tools.qiki_docgen.core.config import QikiDocgenConfig
conf = QikiDocgenConfig()
print(conf.get_path('docs_dir'))
```
```bash
# 5. Проверка версии protoc из YAML
protoc --version
```

## Тест-хуки/чек-лист
- [Факт] Проверить корректность парсинга всех секций YAML.
- [Гипотеза] Тест на отсутствие include путей.

## Вывод
1. Файл задаёт пути и параметры компиляции.
2. Предустановленные include пути покрывают Linux/Mac/Windows.
3. Опции protoc ограничены Python-генерацией.
4. В секции generation определены поддерживаемые шаблоны.
5. README может включать статистику по proto.
6. Логирование настроено на INFO.
7. Проверяется минимальная версия Python и наличие `protoc`.
8. Жёстко заданные пути требуют адаптации.
9. Нет параметров для кастомных флагов компиляции.
10. Стоит добавить проверку существования include путей.

СПИСОК ФАЙЛОВ
- tools/qiki_docgen/config.yaml
