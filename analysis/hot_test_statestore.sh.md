# Анализ файла hot_test_statestore.sh

## Вход и цель
- **Файл**: hot_test_statestore.sh
- **Итог**: Обзор скрипта комплексного тестирования StateStore архитектуры

## Сбор контекста
- **Исходник**: /home/sonra44/QIKI_DTMP/scripts/hot_test_statestore.sh
- **Связанные файлы**:
  - services/q_core_agent/state/types.py (DTO типы)
  - services/q_core_agent/state/store.py (хранилище состояний)
  - services/q_core_agent/state/conv.py (конвертеры)
  - services/q_core_agent/state/tests/test_types.py (unit тесты типов)
  - services/q_core_agent/state/tests/test_store.py (unit тесты хранилища)
  - services/q_core_agent/state/tests/test_conv.py (unit тесты конвертеров)
  - services/q_core_agent/state/tests/test_integration.py (интеграционные тесты)
  - services/q_core_agent/state/tests/test_stress.py (стресс-тесты)

**[Факт]**: Файл является скриптом комплексного тестирования StateStore архитектуры с поддержкой различных режимов проверки.

## Локализация артефакта
- **Точный путь**: /home/sonra44/QIKI_DTMP/scripts/hot_test_statestore.sh
- **Окружение**: Bash, Python 3.x, pytest, asyncio, psutil

## Фактический разбор
### Ключевые функции скрипта:
- **check_environment()**: Проверка окружения и зависимостей
- **syntax_check()**: Проверка синтаксиса модулей StateStore
- **import_check()**: Проверка корректности импортов
- **run_unit_tests()**: Запуск unit тестов
- **run_integration_tests()**: Запуск интеграционных тестов
- **run_stress_tests()**: Запуск стресс-тестов
- **functional_test()**: Быстрый функциональный тест StateStore
- **performance_test()**: Тест производительности
- **compatibility_test()**: Тест совместимости с protobuf
- **memory_leak_test()**: Проверка утечек памяти
- **generate_report()**: Генерация отчета о тестировании

### Режимы работы:
1. **Полный тест** (по умолчанию): Все проверки
2. **--unit-only**: Только unit тесты
3. **--stress-only**: Только стресс-тесты
4. **--quick**: Быстрая проверка
5. **--help**: Справка

**[Факт]**: Скрипт поддерживает различные режимы тестирования и генерирует отчеты о результатах.

## Роль в системе и связи
- **Как участвует в потоке**: Инструмент для комплексной проверки StateStore архитектуры перед интеграцией
- **Кто вызывает**: Разработчики и CI/CD системы для проверки качества кода
- **Что от него ждут**: Быстрая и точная проверка работоспособности StateStore
- **Чем он рискует**: Долгое выполнение при запуске всех тестов, возможные ложные срабатывания на слабом железе

**[Факт]**: Скрипт обеспечивает высокое качество StateStore архитектуры через многоуровневое тестирование.

## Несоответствия и риски
1. **Средний риск**: Некоторые тесты могут давать ложные предупреждения на слабом железе
2. **Низкий риск**: Отсутствует проверка покрытия кода тестами
3. **Низкий риск**: Нет явной интеграции с CI/CD системами
4. **Низкий риск**: Нет проверки безопасности кода

**[Гипотеза]**: Может потребоваться интеграция с системами непрерывной интеграции для автоматического запуска тестов.

## Мини-патчи (safe-fix)
**[Патч]**: Добавить проверку покрытия кода тестами:
```bash
# Добавить новую функцию для проверки покрытия
coverage_check() {
    info "Проверка покрытия кода тестами..."
    
    if ! python3 -c "import pytest_cov" 2>/dev/null; then
        warning "pytest-cov не установлен, пропускаем проверку покрытия"
        return 0
    fi
    
    if python3 -m pytest services/q_core_agent/state/tests/ \
       --cov=services/q_core_agent/state/ \
       --cov-report=term-missing \
       --cov-fail-under=80; then
        success "Покрытие кода: 80%+"
    else
        warning "Низкое покрытие кода тестами"
    fi
}

# Добавить вызов в main()
# В секции дополнительных тестов:
coverage_check || true
```

## Рефактор-скетч (по желанию)
```bash
#!/usr/bin/env bash
set -euo pipefail

# Улучшенная версия скрипта с модульной архитектурой

# Глобальные переменные
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORT_DIR="$PROJECT_ROOT/reports"

# Конфигурация
declare -A CONFIG=(
    ["stress_test_duration"]=2.0
    ["high_load_operations"]=1000
    ["concurrency_workers"]=50
)

# Модуль логирования
source "$SCRIPT_DIR/modules/logging.sh"

# Модуль проверки окружения
source "$SCRIPT_DIR/modules/environment.sh"

# Модуль тестирования
source "$SCRIPT_DIR/modules/testing.sh"

# Модуль отчетов
source "$SCRIPT_DIR/modules/reporting.sh"

# Основной workflow
main() {
    local mode="${1:-full}"
    
    # Инициализация
    init_logging
    ensure_directories
    
    case "$mode" in
        "full")
            run_full_test_suite
            ;;
        "unit")
            run_unit_tests_only
            ;;
        "integration")
            run_integration_tests
            ;;
        "stress")
            run_stress_tests
            ;;
        "quick")
            run_quick_check
            ;;
        *)
            show_help
            exit 1
            ;;
    esac
    
    # Генерация отчета
    generate_report "$mode"
    
    # Отправка уведомлений (если настроено)
    send_notifications
}

# Функции тестирования
run_full_test_suite() {
    log_info "Запуск полного набора тестов StateStore"
    
    # Базовые проверки
    check_environment
    syntax_check
    import_check
    
    # Функциональные тесты
    functional_test
    
    # Расширенные тесты
    run_unit_tests
    run_integration_tests
    run_stress_tests
    
    # Качество кода
    performance_test
    memory_leak_test
    compatibility_test
    coverage_check
}

# Инициализация
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

## Примеры использования
```bash
# Полный тест (по умолчанию)
./scripts/hot_test_statestore.sh

# Только unit тесты
./scripts/hot_test_statestore.sh --unit-only

# Только стресс-тесты
./scripts/hot_test_statestore.sh --stress-only

# Быстрая проверка
./scripts/hot_test_statestore.sh --quick

# Справка
./scripts/hot_test_statestore.sh --help
```

```python
# Пример интеграции в Python код
import subprocess
import sys

def run_statestore_tests():
    """Запустить тесты StateStore из Python кода"""
    try:
        result = subprocess.run(
            ['./scripts/hot_test_statestore.sh', '--quick'],
            cwd='/path/to/QIKI_DTMP',
            capture_output=True,
            text=True,
            timeout=300  # 5 минут максимум
        )
        
        if result.returncode == 0:
            print("StateStore тесты пройдены успешно")
            return True
        else:
            print(f"StateStore тесты провалены: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("Тесты StateStore превысили лимит времени")
        return False
    except Exception as e:
        print(f"Ошибка запуска тестов StateStore: {e}")
        return False

if __name__ == "__main__":
    success = run_statestore_tests()
    sys.exit(0 if success else 1)
```

## Тест-хуки/чек-лист
- [ ] Проверить работу скрипта в различных режимах (--unit-only, --stress-only, --quick)
- [ ] Проверить корректность генерации отчетов
- [ ] Проверить обработку ошибок при отсутствии зависимостей
- [ ] Проверить работу на разных платформах (Linux, macOS)
- [ ] Проверить поведение при низких ресурсах системы
- [ ] Проверить корректность цветового вывода в терминале
- [ ] Проверить работу временных файлов и их очистку

## Вывод
- **Текущее состояние**: Скрипт предоставляет комплексное тестирование StateStore архитектуры с различными режимами работы
- **Что починить сразу**: Добавить проверку покрытия кода тестами
- **Что отложить**: Интеграцию с CI/CD системами и модульную архитектуру

**[Факт]**: Анализ завершен на основе содержимого файла и его роли в системе тестирования.