# TASK-0025 — Trace API v1 (EventStore JSONL export)

## Что сделано
- Добавлен асинхронный экспорт EventStore в JSONL: `src/qiki/services/q_core_agent/core/trace_export.py`.
- Добавлен CLI:
  - `python -m qiki.services.q_core_agent.trace export --out ...`
- Добавлены фильтры:
  - `--from`, `--to`
  - `--types`
  - `--subsystems`
  - `--truth`
  - `--max-lines`
  - `--sample` (`EVENT_TYPE=N`)
- Добавлены события трассировки:
  - `TRACE_EXPORT_STARTED`
  - `TRACE_EXPORT_FINISHED`
  - `TRACE_EXPORT_FAILED`

## Контракт export-envelope (стабильный)
Каждая JSONL строка:
- `schema_version` (int, `1`)
- `ts` (float)
- `subsystem` (str)
- `event_type` (str)
- `truth_state` (str)
- `reason` (str)
- `payload` (object, без модификации)
- `session_id` (str, из payload или `""`)

## Ограничения и безопасность
- Экспорт работает по snapshot-копии (`EventStore.snapshot()`), не блокируя рендер.
- Запись в файл выполняется в отдельном потоке с батчами.
- `max-lines` ограничивает размер выгрузки.
- По умолчанию окно экспорта: последние `60s`.

## Примеры запуска
```bash
python -m qiki.services.q_core_agent.trace export \
  --out /tmp/trace.jsonl \
  --from 1739300000 \
  --to 1739300060 \
  --types RADAR_RENDER_TICK,FUSED_TRACK_UPDATED \
  --subsystems RADAR,FUSION \
  --truth OK \
  --max-lines 5000 \
  --sample RADAR_RENDER_TICK=10
```

## Тестовое покрытие
- `test_trace_export_envelope_stable_and_payload_preserved`
- `test_trace_export_filters_and_types_subsystems_truth`
- `test_trace_export_max_lines_limit`
- `test_trace_export_emits_started_and_finished_events`
- `test_trace_export_integration_with_pipeline`
