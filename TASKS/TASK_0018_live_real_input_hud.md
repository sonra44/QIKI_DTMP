# TASK-0018 — Live HUD на real input (event-driven cockpit)

## Как было
- `--real-input` применялся только в replay-режиме.
- Live режим работал через `command>` loop, поэтому HUD не был непрерывным cockpit-циклом.

## Как стало
- Добавлен live event-driven loop `MissionControlTerminal.live_radar_loop(...)`.
- `--real-input` в live режиме запускает cockpit loop без `command>` как основного цикла.
- Рендер выполняется по триггерам:
  - input event (wheel/click/drag/hotkeys),
  - новые события в `EventStore`,
  - heartbeat.
- Соблюдается FPS cap через `RADAR_FPS_MAX` (или `--fps`).
- В режиме real input используется `clear+home` ANSI для стабильного экрана.

## Режимы запуска
- Live (real input upgrade):
  - `python -m qiki.mission_control_terminal --real-input`
- Live с backend/fps override:
  - `python -m qiki.mission_control_terminal --real-input --renderer auto --fps 10`
- Replay:
  - `python -m qiki.mission_control_terminal --replay artifacts/e2e_task_0013_events.jsonl --interactive --real-input`

## tmux/SSH деградация
- Если real backend недоступен: выводится warning и управление возвращается в `command>` mode (без падения).
- Baseline Unicode не ломается; replay и command mode продолжают работать.

## Быстрая проверка
1. Запустить live с `--real-input`.
2. Проверить hotkeys `1/2/3/4`, `r`, `o`, `c`, `+`, `-`.
3. Проверить wheel/click/drag (если терминал прокидывает mouse events).
4. В tmux без mouse passthrough убедиться, что происходит fallback в command mode.
