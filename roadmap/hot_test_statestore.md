СПИСОК ФАЙЛОВ

# Вход и цель
- [Факт] Скрипт `scripts/hot_test_statestore.sh` — bash‑утилита для комплексного тестирования архитектуры StateStore.
- [Факт] Итог: обзор возможностей скрипта и рекомендации по улучшению.

# Сбор контекста
- [Факт] Используются bash‑функции проверки окружения, синтаксиса, импортов и запусков тестов.
- [Факт] Рядом лежат: `services/q_core_agent/state/{types,store,conv}.py` и тесты в `services/q_core_agent/state/tests/`.
- [Гипотеза] Скрипт предназначен для CI/локальной проверки перед интеграцией StateStore в основную систему.

# Локализация артефакта
- [Факт] Путь: `scripts/hot_test_statestore.sh`.
- [Факт] Требует Python 3 с модулями `pytest`, `asyncio`, `psutil`.
- [Гипотеза] Запускается из корня репозитория, чтобы иметь доступ к сервисам.

# Фактический разбор
## Импорты и зависимости
- [Факт] Определены цветовые константы и функции `info`, `success`, `warning`, `error` для форматированного вывода.
- [Факт] Проверяется наличие файлов StateStore и библиотек Python.
## Основные функции
- [Факт] `check_environment` — проверка директорий и модулей.
- [Факт] `syntax_check` — компиляция Python модулей.
- [Факт] `import_check` — тестовые импорты DTO, Store и конвертеров.
- [Факт] `run_unit_tests`, `run_integration_tests`, `run_stress_tests` — запуск pytest‑тестов.
- [Факт] `performance_test`, `memory_leak_test`, `compatibility_test` — дополнительные проверки.
- [Факт] `generate_report` — формирование Markdown отчёта.
## Поведение
- [Факт] Скрипт прекращает работу при ошибке (`set -euo pipefail`).
- [Факт] Аргументы `--unit-only`, `--stress-only`, `--quick` позволяют выбрать подмножество тестов.
## Граничные случаи
- [Гипотеза] При отсутствии зависимостей скрипт завершится с кодом 1.
- [Гипотеза] При запуске вне корня репо будут ложные ошибки о путях.

# Роль в системе и связи
- [Факт] Автоматизирует многоуровневое тестирование StateStore: unit → integration → stress.
- [Гипотеза] Используется разработчиками для горячего теста перед деплоем.

# Несоответствия и риски
- [Гипотеза] Отсутствует проверка возвратного кода при запуске дополнительных тестов (они выполняются с `|| true`). Приоритет: Med.
- [Гипотеза] Отчёт сохраняется без проверки прав на запись. Приоритет: Low.

# Мини‑патчи (safe-fix)
- [Патч] Добавить проверку существования директории `reports/` перед записью отчёта.
- [Патч] Логировать пропуски тестов при `|| true`, чтобы не терять информацию.

# Рефактор‑скетч
```bash
main() {
  check_environment || return 1
  syntax_check || return 1
  import_check || return 1
  functional_test || return 1
  for step in run_unit_tests run_integration_tests run_stress_tests; do
    if ! $step; then warning "$step failed"; fi
  done
  generate_report
}
```

# Примеры использования
```bash
# 1. Полный прогон
scripts/hot_test_statestore.sh
# 2. Быстрая проверка
scripts/hot_test_statestore.sh --quick
# 3. Только unit-тесты
scripts/hot_test_statestore.sh --unit-only
# 4. Только stress-тесты
scripts/hot_test_statestore.sh --stress-only
# 5. Получить справку
scripts/hot_test_statestore.sh --help
```

# Тест‑хуки/чек‑лист
- [Факт] `python3 -m py_compile services/q_core_agent/state/*.py`
- [Факт] `python3 -m pytest services/q_core_agent/state/tests/test_store.py -q`
- [Факт] `python3 -m pytest services/q_core_agent/state/tests/test_conv.py -q`
- [Факт] `python3 -m pytest services/q_core_agent/state/tests/test_integration.py -q`
- [Факт] `python3 -m pytest services/q_core_agent/state/tests/test_stress.py -q`

# Вывод
1. [Факт] Скрипт обеспечивает комплексную проверку StateStore.
2. [Факт] Основные проверки останавливают выполнение при сбоях.
3. [Гипотеза] Дополнительные проверки могут скрыть ошибки из-за `|| true`.
4. [Факт] Отчёт формируется автоматически в Markdown.
5. [Гипотеза] Нужна явная очистка временных файлов.
6. [Патч] Добавить логирование пропущенных тестов.
7. [Патч] Проверять наличие директории перед записью отчёта.
8. [Гипотеза] Рассмотреть вывод краткого резюме по результатам.
9. [Патч] Вынести общие константы в начало файла.
10. [Гипотеза] Возможна интеграция со сторонней системой CI.

СПИСОК ФАЙЛОВ
