# TASK-0026 — Deterministic Replay & Timeline Engine (Forensic Mode)

## Что сделано
- Добавлен модуль `src/qiki/services/q_core_agent/core/radar_replay.py`:
  - `load_trace(path) -> list[event]`
  - `RadarReplayEngine` с `replay_events()`, `next_batch()`, `jump_to_ts()`, `jump_to_event_type()`, `jump_to_situation_id()`, `pause()`, `resume()`
  - `TimelineState` (`current_ts`, `speed`, `paused`, `cursor`, `total_events`)
- Добавлен clock abstraction `src/qiki/services/q_core_agent/core/radar_clock.py`:
  - `Clock`, `SystemClock`, `ReplayClock`, `ensure_clock()`
- `RadarSituationEngine` переведён на `Clock` (без `time.time()` в evaluate).
- `RadarPipeline` интегрирован с replay:
  - ENV: `RADAR_REPLAY_FILE`, `RADAR_REPLAY_SPEED`, `RADAR_REPLAY_STEP`, `RADAR_REPLAY_STRICT_DETERMINISM`
  - при replay ingest реальных observations отключается и заменяется на источник из trace (`SOURCE_TRACK_UPDATED`)
  - добавлены методы управления timeline: pause/resume/jump.
- HUD/терминальный рендер получил forensic строку:
  - `[REPLAY xN] ts=... status=PLAYING|PAUSED cursor=...`

## Контракт deterministic replay
- Replay использует таймштампы trace как источник времени (`ReplayClock`).
- Fusion/Situations/Adaptive получают время через единый `Clock`.
- Повтор trace воспроизводит ту же последовательность:
  - `FUSED_TRACK_UPDATED`
  - `situation_*` событий.

## ENV knobs
- `RADAR_REPLAY_FILE` — путь к JSONL trace.
- `RADAR_REPLAY_SPEED` — коэффициент скорости replay (default `1.0`).
- `RADAR_REPLAY_STEP` — step-режим (`1|true|on`).
- `RADAR_REPLAY_STRICT_DETERMINISM` — strict загрузка trace (`1` fail-fast, `0` warning + replay off).

## Ограничения v1
- Replay использует события `SOURCE_TRACK_UPDATED` как вход для ingest/fusion/situations.
- Невалидные replay-события сенсоров пропускаются (без падения).
