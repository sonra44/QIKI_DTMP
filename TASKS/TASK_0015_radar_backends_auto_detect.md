# TASK-0015 — Radar Pipeline Backends (Unicode + Kitty + SIXEL)

## Как было
- Рендер делался напрямую в `terminal_radar_renderer.py` и всегда в одном текстовом формате.
- Не было единого backend-pipeline с auto-detect.
- Не было runtime fallback с bitmap backend на Unicode в рамках одной сессии.

## Как стало
- Добавлен единый pipeline: `Scene -> Projection -> Rasterize/Glyphize -> Backend Output`.
- Реализованы backend'ы:
  - `unicode` (mandatory baseline, всегда доступен);
  - `kitty` (bitmap через Kitty graphics protocol);
  - `sixel` (bitmap через SIXEL output).
- Добавлен селектор `RADAR_RENDERER=auto|unicode|kitty|sixel`.
- В `auto`: `kitty` (если поддержан) -> `sixel` (если поддержан) -> `unicode`.
- При runtime-ошибке bitmap backend происходит seamless fallback на Unicode без краша.

## Pipeline диаграмма
1. EventStore events -> `_build_view()`
2. `_view_to_scene()` -> `RadarScene`
3. `RadarPipeline.render_scene(scene)`
4. Backend render -> radar pane lines
5. HUD + Event Log собираются в итоговый экран

## Что считается supported
- `UnicodeRadarBackend`: всегда `True`.
- `KittyRadarBackend`: true при `QIKI_FORCE_KITTY_SUPPORTED=1` или kitty-признаках (`TERM`/`KITTY_WINDOW_ID`).
- `SixelRadarBackend`: true при `QIKI_FORCE_SIXEL_SUPPORTED=1` или `TERM` с `sixel`.
- Консервативное правило: если не уверены, backend считает себя unsupported.

## Runtime fallback правила
- Если выбранный backend падает в `render()`, pipeline переключается на `unicode` в этой же сессии.
- В output добавляется маркер:
  - `[RADAR RUNTIME FALLBACK <from>->unicode: <error>]`

## Env knobs
- `RADAR_RENDERER=auto|unicode|kitty|sixel`
- `RADAR_VIEW=top|side|front|iso`
- `RADAR_FPS_MAX=10` (конфиг, подготовлен для live-loop throttle)
- `RADAR_COLOR=1|0`

## Truth constraints
- Если `SensorTrustVerdict.ok=False` -> показывается `NO DATA: <reason>`, target не рисуется.
- Если `is_fallback=True` -> HUD явно показывает `FALLBACK`.
- UI остаётся отображением фактов, не источником truth.

## Ручная проверка
```bash
# Unicode (forced)
RADAR_RENDERER=unicode python -m qiki.mission_control_terminal --replay artifacts/e2e_task_0013_events.jsonl

# Auto (best available)
RADAR_RENDERER=auto python -m qiki.mission_control_terminal --replay artifacts/e2e_task_0013_events.jsonl

# Kitty forced (должен fail-fast если unsupported)
RADAR_RENDERER=kitty python -m qiki.mission_control_terminal --replay artifacts/e2e_task_0013_events.jsonl

# SIXEL forced (должен fail-fast если unsupported)
RADAR_RENDERER=sixel python -m qiki.mission_control_terminal --replay artifacts/e2e_task_0013_events.jsonl
```
