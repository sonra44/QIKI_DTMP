# TASK-0030 — E2E Load & Stability Harness

## Что сделано
- Добавлен deterministic Scenario Engine: `src/qiki/services/q_core_agent/core/load_scenarios.py`.
- Добавлен CLI harness: `src/qiki/core/load_harness.py`.
- Добавлен public re-export сценариев: `src/qiki/core/load_scenarios.py`.
- В `RadarPipeline` добавлен внутренний сборщик `PerformanceMetrics` и `snapshot_metrics()`.
- В `EventStore` добавлены публичные счётчики `sqlite_queue_depth` и `sqlite_dropped_events`.
- Добавлен набор нагрузочных тестов с `@pytest.mark.load`:
  `src/qiki/services/q_core_agent/tests/test_load_stability_harness.py`.
- Добавлен CI job: `.github/workflows/load-tests.yml`.

## Сценарии
- `single_target_stable`
- `multi_target_300`
- `fusion_conflict`
- `sensor_dropout`
- `oscillation_threshold`
- `high_write_sqlite`
- `replay_long_trace`

Все сценарии deterministic (seed + fixed-step, без `sleep`).

## CLI
```bash
python -m qiki.core.load_harness \
  --scenario multi_target_300 \
  --duration 30 \
  --targets 300 \
  --fusion on \
  --sqlite on
```

Вывод: JSON в stdout с ключами:
- `avg_frame_ms`
- `p95_frame_ms`
- `max_frame_ms`
- `fusion_clusters`
- `situation_events`
- `sqlite_queue_peak`
- `dropped_events`
- `total_events_written`

## Strict load mode
- ENV: `QIKI_LOAD_STRICT=1`
- При strict:
  - превышение `avg/max` порогов -> ошибка
  - `dropped_events > 0` -> ошибка

## Проверка
```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev \
  pytest -q -m load src/qiki/services/q_core_agent/tests/test_load_stability_harness.py
```
