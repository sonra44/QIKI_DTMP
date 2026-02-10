# TASK-0017 — Real Input Backend (mouse + hotkeys) with graceful fallback

## Как было
- Интерактивный replay в `mission_control_terminal.py` принимал только строковые команды (`wheel up`, `click x y`, `drag dx dy`).
- Реальные mouse/key events из терминала не читались.

## Как стало
- Добавлен модуль `src/qiki/services/q_core_agent/core/terminal_input_backend.py`:
  - `LineInputBackend` (baseline, всегда работает через `input()`).
  - `RealTerminalInputBackend` (capability-upgrade: raw key/mouse events, wheel/click/drag).
  - `select_input_backend(prefer_real=...)` с fallback в line mode без краша.
- В `mission_control_terminal.py`:
  - новый CLI флаг `--real-input`;
  - `replay --interactive --real-input` использует real backend, иначе line backend;
  - при недоступности real backend выводится warning и автоматически используется line mode;
  - добавлен event-driven loop с FPS cap (`RADAR_FPS_MAX`) и без лишних перерисовок.

## Режимы
- Baseline:
  - `python -m qiki.services.q_core_agent.core.mission_control_terminal --replay <trace.jsonl> --interactive`
- Real input upgrade:
  - `python -m qiki.services.q_core_agent.core.mission_control_terminal --replay <trace.jsonl> --interactive --real-input`

## Жесты/клавиши
- wheel up/down -> zoom in/out
- click -> select nearest target
- drag -> pan (top/side/front) или rotate (iso)
- hotkeys: `1/2/3/4`, `r`, `o`, `c`, `+/-`, `q`

## tmux/SSH деградация
- Если real backend недоступен (нет TTY/capability), система автоматически переходит в line mode.
- В tmux выводится подсказка про mouse passthrough; управление hotkeys и command mode остаётся доступным.

## Optional deps
- Runtime авто-установка зависимостей не используется.
- Для TASK-0017 не требуется auto-pip/`os.system`.
- Реализация выполнена на stdlib; baseline не ломается.

## Проверка
1. Unit tests:
   - `pytest -q src/qiki/services/q_core_agent/tests/test_terminal_input_backend_mapping.py`
2. Radar regression:
   - `pytest -q src/qiki/services/q_core_agent/tests/test_radar_controls.py src/qiki/services/q_core_agent/tests/test_radar_pipeline.py src/qiki/services/q_core_agent/tests/test_terminal_renderer.py`
3. Replay smoke:
   - `python -m qiki.services.q_core_agent.core.mission_control_terminal --replay artifacts/e2e_task_0013_events.jsonl --interactive --real-input`

