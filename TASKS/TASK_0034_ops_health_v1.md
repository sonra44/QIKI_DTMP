# TASK-0034 — Ops/Health v1

## Что сделано
- Добавлен единый health-слой: `src/qiki/services/q_core_agent/core/health.py`.
- Введён контракт `HealthSnapshot` с секциями:
  - `pipeline`
  - `fusion`
  - `policy`
  - `eventstore`
  - `session`
  - `replay`
- Добавлены конфигурируемые пороги из ENV:
  - `QIKI_HEALTH_FRAME_P95_WARN_MS`
  - `QIKI_HEALTH_FRAME_P95_CRIT_MS`
  - `QIKI_HEALTH_SQLITE_QUEUE_WARN`
  - `QIKI_HEALTH_SQLITE_QUEUE_CRIT`
  - `QIKI_HEALTH_SESSION_STALE_MS`
  - `QIKI_HEALTH_FUSION_CONFLICT_WARN_RATE`

## Логика состояний и события
- `HealthMonitor` вычисляет `overall`: `OK | WARN | CRIT | NO_DATA`.
- Эмитятся только transition-события (дедуп):
  - `HEALTH_WARN`
  - `HEALTH_CRIT`
  - `HEALTH_NO_DATA`
  - `HEALTH_RECOVERED`
- Спам исключён: одинаковая проблема с той же severity не переэмитится каждый тик.

## Интеграция
- `RadarPipeline`:
  - собирает health snapshot на каждом рендер-цикле;
  - отдаёт `health_snapshot()` для CLI/HUD;
  - принимает session-метрики через `update_session_health(...)`.
- `SessionServer` обновляет session-метрики в pipeline при публикации snapshot.
- `load_harness` (TASK-0030) учитывает health:
  - при `QIKI_LOAD_STRICT=1` и `overall=CRIT` падает с `RuntimeError`.

## CLI
- Добавлен быстрый health dump:
  - `python -m qiki.core.health_cli --json`
- Вывод: единый JSON snapshot + top issues.

## HUD
- В терминальном экране добавлена строка:
  - `[HEALTH: OK|WARN|CRIT|NO_DATA]`
  - при проблемах показывает 1–2 top issues.

## Проверка вручную
1. `python -m qiki.core.health_cli --json`
2. `QIKI_HEALTH_FRAME_P95_CRIT_MS=0.0001 QIKI_LOAD_STRICT=1 python -m qiki.core.load_harness --scenario single_target_stable --duration 2 --targets 1 --fusion on --sqlite on`
3. `python -m qiki.mission_control_terminal --renderer unicode` и убедиться, что в HUD есть строка `[HEALTH: ...]`.

