# TASK: ORION V Level 0 Alerts Overlay

Статус: in_progress
Дата: 2026-03-13
Ответственные: user + codex

## Цель

Собрать Level 0 Alerts Overlay как третий фундаментальный слой ORION V поверх существующих F1/F2, без нового источника истины и без превращения overlay в event log.

## Решение

- Overlay переведён из incident-only режима в общий severity-first слой `critical/warning/attention`.
- Источники overlay:
  - активные incidents (`qiki.events.v1.audit` / active incident queue),
  - агрегированные F2 system cards из `hardware_view_model + telemetry + objective + safe_mode + radar_tracks`,
  - objective follow-up truth (`review_required`, `hold_for_recheck`, missing observation confidence),
  - последний QIKI legality/warnings контур.
- Grammar alert item:
  - `severity`
  - `title`
  - `short meaning`
  - `source`
  - `operator effect`
  - `optional next action hint`

## Изменённые файлы

- `src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `tests/unit/test_orion_v_app_incidents.py`

## Proof

- Docker tests:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q /workspace/tests/unit/test_orion_v_app_incidents.py /workspace/tests/unit/test_orion_v_systems_uses_hardware_model.py /workspace/tests/unit/test_orion_v_cockpit.py`
- Lint:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check /workspace/src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py /workspace/src/qiki/services/operator_console/orion_v/app.py /workspace/tests/unit/test_orion_v_app_incidents.py`
- Compile:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python -m py_compile /workspace/src/qiki/services/operator_console/orion_v/widgets/alerts_overlay.py /workspace/src/qiki/services/operator_console/orion_v/app.py`

## Live evidence

- tmux session `orionv_alerts_system_0313`, window `0`, pane `%82`
- tmux session `orionv_alerts_objective_0313`, window `0`, pane `%83`
- `capture-pane` shows live overlay above F1 with:
  - objective-driven `Review required`
  - system-driven `Comms / Link / Protocol`

## Ограничения

- Current live stack still hydrates the latest objective follow-up into fresh ORION sessions, so the system-driven proof pane also carries the objective-driven alert at the same time.
- Overlay is intentionally Level 0 only: no separate routing engine, no notification history, no deep metrics expansion.
