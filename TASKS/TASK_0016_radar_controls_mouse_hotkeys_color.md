# TASK-0016 — ORION Radar Controls: Mouse + Hotkeys + Color

## Как было
- Радар рендерился через pipeline/backends, но не имел единого `ViewState` для zoom/pan/rotate/select.
- Ввод в `MissionControlTerminal` был командным и не управлял проекцией/оверлеями/цветом радара.
- Цветовая семантика truth/severity не была единообразной для HUD/EventLog.

## Как стало
- Введён `RadarViewState` (`zoom`, `pan_x/pan_y`, `rot_yaw/rot_pitch`, `view`, `selected_target_id`, `overlays_enabled`, `color_enabled`).
- Добавлен `RadarInputController`:
  - hotkeys: `1/2/3/4`, `r`, `o`, `c`, `+/-`, `q`
  - mouse actions: wheel zoom, left click select, drag pan/iso rotate
- Pipeline/backends принимают `ViewState` и учитывают:
  - view + zoom/pan/rot
  - selected target highlight
  - overlays toggle
  - color toggle with graceful mono mode
- `MissionControlTerminal`:
  - поддерживает hotkeys и `mouse ...` команды
  - `--replay --interactive` даёт интерактивный loop для trace из JSONL.

## Таблица hotkeys
- `1` -> `top`
- `2` -> `side`
- `3` -> `front`
- `4` -> `iso`
- `r` -> reset view
- `o` -> overlays on/off
- `c` -> color on/off
- `+/-` -> zoom in/out
- `q` -> exit interactive replay

## Mouse gestures
- `wheel up/down` -> zoom in/out
- `click <x> <y>` -> select nearest target (projected space)
- `drag <dx> <dy>` -> pan (`top/side/front`) or rotate (`iso`)

## Цветовая семантика и fallback
- Truth states:
  - `OK` -> green
  - `NO_DATA/STALE/LOW_QUALITY` -> yellow
  - `FALLBACK/INVALID` -> red
- EventLog severity markers всегда текстовые: `[INFO]`, `[WARN]`, `[SAFE]`.
- При `RADAR_COLOR=0` ANSI отключён, остаются текстовые метки (`[WARN]`, `FALLBACK`, `[MONO]`).
- Если mouse events недоступны, loop работает через hotkeys и не падает.

## Проверка (Docker-first)
- Unit tests:
  - `pytest -q src/qiki/services/q_core_agent/tests/test_radar_controls.py`
  - `pytest -q src/qiki/services/q_core_agent/tests/test_radar_pipeline.py src/qiki/services/q_core_agent/tests/test_terminal_renderer.py`
- Replay demo:
  - `python -m qiki.services.q_core_agent.core.mission_control_terminal --replay artifacts/e2e_task_0013_events.jsonl --interactive`

