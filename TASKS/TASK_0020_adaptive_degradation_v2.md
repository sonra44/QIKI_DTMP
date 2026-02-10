# TASK-0020 — Adaptive Degradation v2

## Как было
- В `RadarRenderPlan` был только `clutter_reason` (одна причина).
- Деградация bitmap была фиксированной (`<=0.75`) без ступеней и без восстановления.
- Не было hysteresis: реакция на перегруз могла быть слишком резкой.
- Не было системной телеметрии render-tick в `EventStore`.

## Как стало
- `RadarRenderPlan`/`RadarRenderStats` используют `clutter_reasons: tuple[str, ...]` (multi-reason).
- Добавлен `DegradationState` в `RadarPipeline` (персистентно между кадрами):
  - `current_level`, `last_change_ts`, `consecutive_budget_violations`, `consecutive_budget_ok`, `last_scale`.
- Добавлены детерминированные уровни деградации:
  - Level 0: scale=1.0
  - Level 1: disable labels, scale=0.75
  - Level 2: disable trails, scale=0.5
  - Level 3: disable vectors, scale=0.35
- Восстановление работает ступенчато (уровень -1) после подтверждения `ok` кадров и cooldown.
- Добавлена telemetry запись `RADAR_RENDER_TICK` в `EventStore` на каждом render tick (если `RADAR_TELEMETRY=1`).

## Clutter reasons
- `TARGET_OVERLOAD`
- `FRAME_BUDGET_EXCEEDED`
- `LOW_CAPABILITY_BACKEND`
- `MANUAL_CLUTTER_LOCK`

Причины сохраняются списком без дублей и выводятся в HUD.

## Knobs (env)
- `RADAR_FRAME_BUDGET_MS` (default `80`)
- `RADAR_CLUTTER_TARGETS_MAX` (default `30`)
- `RADAR_DEGRADE_COOLDOWN_MS` (default `800`)
- `RADAR_RECOVERY_CONFIRM_FRAMES` (default `6`)
- `RADAR_DEGRADE_CONFIRM_FRAMES` (default `2`)
- `RADAR_BITMAP_SCALES` (default `1.0,0.75,0.5,0.35`)
- `RADAR_TELEMETRY` (default `1`)
- `RADAR_MANUAL_CLUTTER_LOCK` (default `0`)

## Hysteresis
- Degrade: только после `RADAR_DEGRADE_CONFIRM_FRAMES` подряд нарушений + после cooldown.
- Recover: только после `RADAR_RECOVERY_CONFIRM_FRAMES` подряд кадров в бюджете + после cooldown.
- Это убирает флаппинг и “пилу” уровня качества.

## Telemetry event format
- `subsystem=RADAR`, `event_type=RADAR_RENDER_TICK`
- payload:
  - `frame_ms`
  - `fps_cap`
  - `targets_count`
  - `lod_level`
  - `degradation_level`
  - `bitmap_scale`
  - `dropped_overlays`
  - `clutter_reasons`
  - `backend`

## HUD примеры
- `PERF: 42.1ms (budget 80) lvl=1 scale=0.75`
- `CLUTTER: ON reasons=[TARGET_OVERLOAD,FRAME_BUDGET_EXCEEDED] dropped=labels,trails`

## Проверка
- Локально:
  - `pytest -q src/qiki/services/q_core_agent/tests/test_radar_semantics_lod_clutter.py src/qiki/services/q_core_agent/tests/test_radar_pipeline.py`
- Docker-first:
  - `docker compose -f docker-compose.phase1.yml run --rm qiki-dev pytest -q src/qiki/services/q_core_agent/tests/test_radar_semantics_lod_clutter.py src/qiki/services/q_core_agent/tests/test_radar_pipeline.py src/qiki/services/q_core_agent/tests/test_terminal_renderer.py src/qiki/services/q_core_agent/tests/test_radar_controls.py src/qiki/services/q_core_agent/tests/test_mission_control_terminal_live_real_input.py`
