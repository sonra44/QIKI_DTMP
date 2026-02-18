# TASK-0035 — Unified Orion Shell Foundation (runtime config extraction)

## Почему
- Логика режимов (`QIKI_MODE`), сессии (`QIKI_SESSION_*`) и training-defaults была размазана внутри `mission_control_terminal.py`.
- Это усложняло миграцию к единой оболочке и увеличивало риск дублирования при развитии `Orion Shell` и `Operator Console`.

## Что сделано (этот срез)
- Введён единый runtime-слой: `src/qiki/services/q_core_agent/core/orion_shell_runtime.py`.
- Добавлен `OrionShellRuntimeConfig.from_env()`:
  - централизованный разбор `QIKI_MODE`, `QIKI_SESSION_MODE/HOST/PORT/CLIENT_ID/ROLE/TOKEN`,
  - детерминированный fallback для `QIKI_SESSION_PORT`,
  - стабильная генерация `client_id`.
- Добавлен `apply_training_defaults()`:
  - `QIKI_PLUGINS_PROFILE=training`,
  - `EVENTSTORE_BACKEND=sqlite`,
  - `EVENTSTORE_DB_PATH=artifacts/training_eventstore.sqlite`,
  - `RADAR_EMIT_OBSERVATION_RX=0`,
  - только через `setdefault` (без затирания явных env override).
- `MissionControlTerminal` переведён на этот слой без изменения внешнего CLI-контракта.

## Инварианты
- Backward compatible: прежние env-переменные продолжают работать.
- No silent behavior changes: training-defaults по-прежнему применяются автоматически при `QIKI_MODE=training`.
- Никакие proof-файлы (`TASKS/ARTIFACT_*`, `TASK_20260205_*`) не затронуты.

## Тесты
- `test_orion_shell_runtime.py`:
  - defaults + deterministic `client_id`,
  - invalid port fallback,
  - training defaults (без перезаписи явных env),
  - idempotency `apply_training_defaults()`.

## Следующий шаг
- Подключить этот runtime-слой как единый вход для shell entrypoint, затем поэтапно перевести session/policy/training переключения в plugin-driven orchestration.
