# TASK-0014 — MissionControlTerminal: 3D radar + HUD on EventStore

## Как было
- `mission_control_terminal.py` показывал только снимок систем и не имел truth-aware HUD.
- Не было replay-режима по `EventStore` JSONL.
- Не было отдельного слоя рендера для зон `Radar/HUD/EventLog`.

## Как стало
- Добавлен ASCII renderer: `src/qiki/services/q_core_agent/core/terminal_radar_renderer.py`.
- Экран теперь состоит из 3 зон:
  - `RADAR` (pseudo-3D сетка, глубина маркером `. o O @`, вектор по `vr_mps`).
  - `HUD` (`FSM`, `docking k/N`, `SAFE_MODE reason + exit hits`, `last actuation`, `truth-state`).
  - `EVENT LOG` (последние события `[ts] TYPE reason`).
- Источник данных только факты из `EventStore`:
  - `FSM_TRANSITION`
  - `SAFE_MODE`
  - `ACTUATION_RECEIPT`
  - `SENSOR_TRUST_VERDICT`
- Для radar/HUD в trust-событие добавлен нормализованный `payload.data` (если есть), без изменения бизнес-логики.

## Режимы
- `live`: команда `hud` в интерактивном терминале рендерит экран из `EventStore.recent(...)`.
- `replay`: CLI чтение trace JSONL и отрисовка одного экрана:
  - `python -m qiki.mission_control_terminal --replay artifacts/e2e_task_0013_events.jsonl`

## Truth-инварианты
- Если `SensorTrust.ok=false`, UI печатает `NO DATA: <reason>` и не рисует цель как валидную.
- Если `is_fallback=true`, в HUD есть пометка `FALLBACK`.
- При `SAFE_MODE` показывается `WHY` (reason) и `EXIT hits k/N`.

## Тесты
- `test_terminal_renderer_renders_screen_from_events_without_exception`
- `test_terminal_renderer_no_data_shows_no_data_and_hides_target_marker`
- `test_terminal_renderer_safe_mode_shows_reason_and_exit_counter`

