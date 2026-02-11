# TASK-0021 — Situational Awareness v1

## Как было
- Радар показывал геометрию + truth/HUD/EventLog, но не вычислял приоритеты угроз.
- Оператор видел треки, но сам интерпретировал риск сближения и срочность.
- В EventStore не было формализованных lifecycle событий по ситуациям.

## Как стало
- Добавлен `radar_situation_engine.py`:
  - типы: `CPA_RISK`, `CLOSING_FAST`, `ZONE_VIOLATION`, `LOST_CONTACT`, `UNKNOWN_NEARBY`
  - severity: `INFO | WARN | CRITICAL`
  - lifecycle deltas: `SITUATION_CREATED | SITUATION_UPDATED | SITUATION_RESOLVED`
- `RadarPipeline` теперь:
  - вычисляет ситуации на каждом кадре
  - пишет события подсистемы `SITUATION` в `EventStore`
  - связывает alert-cursor с выбором цели (jump-to-alert)
- Unicode backend:
  - рисует CRITICAL overlay (`✶` + CPA dotted vector)
  - WARN overlay — только при zoom/selection
  - respect `ack` (mute) и `situations_enabled`
- HUD/Inspector:
  - строка `ALERTS: <critical> CRITICAL, <warn> WARN`
  - inspector показывает ситуации/метрики выбранной цели
  - добавлен статус `SITUATION OVERLAYS ON/OFF`

## Пороги (env knobs)
- `RADAR_SITUATION_ENABLE` (default `1`)
- `RADAR_CPA_WARN_T` (default `20`)
- `RADAR_CPA_CRIT_T` (default `8`)
- `RADAR_CPA_CRIT_DIST` (default `150`)
- `RADAR_CLOSING_SPEED_WARN` (default `5.0`)
- `RADAR_CLOSING_CONFIRM_FRAMES` (default `3`)
- `RADAR_NEAR_DIST` (default `300`)
- `RADAR_NEAR_RECENT_S` (default `8`)
- `RADAR_LOST_CONTACT_RECENT_S` (default `10`)

## UX v1
- Hotkeys: `a/j` next alert, `k` prev alert, `A` acknowledge (mute target), `s` toggle situation overlays.
- CRITICAL всегда видим на сцене; INFO не загромождает сцену (только HUD/Inspector/EventStore).
- `NO_DATA` не создаёт новые ситуации.

## Проверка
- Unit suite: `src/qiki/services/q_core_agent/tests/test_radar_situational_awareness.py`
- Регресс: LOD/clutter/render plan остаются активными в pipeline.
