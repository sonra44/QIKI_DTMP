**ID:** TASK_20260126_docking_permissions  
**Status:** done  
**Owner:** OpenCode  
**Date created:** 2026-01-26  

## Goal

Ввести политику допуска для docking команд: `sim.dock.*` и `power.dock.*` исполняются только в FACTORY; в MISSION блокируются с предупреждением и audit‑событием.

## Scope / Non-goals

- In scope:
  - Gating при ACCEPT предложений (faststream_bridge)
  - Предупреждение оператору в ORION (warnings)
  - Audit trail: зафиксировать blocked в `qiki.events.audit`
  - Обновление доков по `DOCUMENTATION_UPDATE_PROTOCOL.md`
- Out of scope:
  - Изменения логики симулятора docking
  - Новые команды/предложения
  - Рефакторинг CLI маршрутизации

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/design/operator_console/QIKI_INTEGRATION_PLAN.md`
  - `src/qiki/services/faststream_bridge/app.py`
  - `src/qiki/services/operator_console/main_orion.py`

## Plan (steps)

1) Добавить FACTORY‑only gating для `sim.dock.*` и `power.dock.*` в faststream_bridge.
2) Добавить предупреждения в ORION при `resp.warnings`.
3) Обновить `QIKI_INTEGRATION_PLAN.md` (политика допуска для docking).
4) Docker‑проверка (ruff check + smoke/quality gate при необходимости).
5) Зафиксировать evidence и закрыть DoD.

## Definition of Done (DoD)

- [x] Docking команды блокируются в MISSION, исполняются в FACTORY.
- [x] ORION показывает предупреждение при блокировке.
- [x] Audit event содержит `blocked` и `blocked_reason`.
- [x] Docs обновлены по `DOCUMENTATION_UPDATE_PROTOCOL.md`.
- [x] Docker-first checks выполнены (команды + вывод сохранены).
- [x] Repo clean (`git status --porcelain` пуст).

## Evidence (commands → output)

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/faststream_bridge/app.py src/qiki/services/operator_console/main_orion.py`
  - `All checks passed!`
- `docker compose -f docker-compose.phase1.yml up -d --build faststream-bridge`
  - `qiki-faststream-bridge-phase1` recreated and started
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY' ... PY`
  - `OK: warning=Docking commands are blocked in MISSION mode./Команды стыковки заблокированы в режиме МИССИЯ.`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY' ... PY`
  - `OK: audit event {"kind": "proposal_accept", "blocked": ["sim.dock.engage"], "blocked_reason": "mode_mission", "mode": "MISSION", ...}`
- ORION (tmux pane) after accept in MISSION:
  - `warning/предупреждение QIKI: warning/предупреждение: Docking commands are blocked in MISSION mode./Команды стыковки заблокированы в режиме МИССИЯ.`

## Notes / Risks

- Риск: несоответствие UI ↔ backend; mitigated единым источником состояния (faststream_bridge).
- Риск: doc‑drift при изменении политики допуска.

## Next

1) Перейти к следующему приоритету из `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.
