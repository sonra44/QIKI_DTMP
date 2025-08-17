# HOT_TEST_STATESTORE.SH — аналитический отчёт

## Вход и цель
- [Факт] Анализ bash-скрипта `hot_test_statestore.sh`.
- [Факт] Итог — обзор функций, рисков и мини-патчей.

## Сбор контекста
- [Факт] Просмотрен исходник скрипта и файлы `services/q_core_agent/state/*.py`.
- [Гипотеза] Скрипт используется разработчиками для быстрой проверки StateStore.

## Локализация артефакта
- [Факт] Путь: `scripts/hot_test_statestore.sh` внутри репозитория.
- [Факт] Требуется окружение с `pytest`, `psutil`, Python ≥3.10.

## Фактический разбор
- [Факт] Функции: `check_environment`, `syntax_check`, `import_check`, `run_unit_tests`, `run_integration_tests`, `run_stress_tests`, `functional_test`.
- [Факт] Используются цвета ANSI и функции `info/success/warning/error` для логирования.
- [Факт] Стресс-тесты запускают ограниченный набор тестов с таймаутом 30 с.

## Роль в системе и связи
- [Факт] Скрипт объединяет линтинг, unit, integration и stress проверки.
- [Гипотеза] Применяется в CI перед деплоем модулей StateStore.

## Несоответствия и риски
- [Факт] Отсутствует проверка существования каталога `generated/` с protobuf.
- [Гипотеза] Возможны ложноположительные результаты stress-тестов при низкой производительности.
- [Факт] Обработчики ошибок возвращают код 1, но не всегда логируют подробности.

## Мини-патчи (safe-fix)
- [Патч] Добавить проверку наличия каталога `generated/` и вывод подсказки.
- [Патч] Логировать время выполнения каждого блока для анализа производительности.

## Рефактор-скетч
```bash
main(){
  check_environment || exit 1
  syntax_check
  import_check
  run_unit_tests && run_integration_tests && run_stress_tests
}
```

## Примеры использования
- [Факт]
```bash
./scripts/hot_test_statestore.sh --quick
```
- [Факт]
```bash
./scripts/hot_test_statestore.sh --unit-only
```

## Тест-хуки/чек-лист
- [Факт] `bash -n scripts/hot_test_statestore.sh`
- [Факт] `pytest services/q_core_agent/state/tests/test_store.py -q`

## Вывод
- [Факт] Скрипт покрывает ключевые пути проверки StateStore.
- [Гипотеза] При расширении тестов стоит вынести общие утилиты в отдельный модуль.
