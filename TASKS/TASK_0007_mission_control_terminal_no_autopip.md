# TASK-0007 — MissionControlTerminal: убрать небезопасную автоустановку зависимостей

## Scope
- Target: `src/qiki/services/q_core_agent/core/mission_control_terminal.py`
- Goal: запретить auto-pip в терминальном UI и закрепить это тестом.

## Как было (фактическая проверка)
- В целевом файле `mission_control_terminal.py` отсутствуют:
  - `prompt_toolkit` import/usage,
  - `try/except ImportError` с установкой пакетов,
  - `os.system("pip install ...")`.
- Следовательно, небезопасной автоустановки в целевом модуле уже нет.

## Почему риск всё равно важен
- Возврат `os.system(...pip install...)` в рантайм-слой нарушает Docker-first и делает поведение недетерминированным.
- Нужен регрессионный тест, чтобы это не появилось повторно.

## Что сделано
- Добавлен unit-тест:
  - `src/qiki/services/q_core_agent/tests/test_mission_control_terminal_no_autopip.py`
- Тест проверяет исходник `mission_control_terminal.py` и гарантирует:
  - нет вызова `os.system`,
  - нет строк `pip install`,
  - нет `prompt_toolkit` runtime-path в этом модуле.

## DoD check
- ✅ В коде целевого файла нет `os.system("pip install ...")`.
- ✅ По умолчанию модуль не пытается ставить пакеты сам.
- ✅ Поведение закреплено детерминированным тестом (регрессия на auto-pip).
