# TASK: ORION BIOS loaded indicator (console history)

**ID:** TASK_20260123_orion_bios_loaded_indicator  
**Status:** done  
**Owner:** sonra44  
**Date created:** 2026-01-23  

## Goal

Сделать факт «BIOS загрузился» видимым в ORION без угадывания момента attach: одна детерминированная строка в UI при первом событии BIOS.

## Scope / Non-goals

- In scope:
  - ORION пишет в историю (console/calm-log) строку `BIOS loaded/BIOS загрузился: ...` при первом `qiki.events.v1.bios_status`.
  - Добавить воспроизводимый пункт в validation checklist.
- Out of scope:
  - Любые изменения BIOS payload/контракта.
  - Изменения Radar UX.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `src/qiki/services/operator_console/main_orion.py`
  - `docs/design/operator_console/ORION_OS_VALIDATION_CHECKLIST.md`

## Plan (steps)

1) Добавить одноразовую строку в ORION при первом событии BIOS.
2) Подтвердить реальный publish BIOS через smoke (Docker-first).
3) Визуально подтвердить строку внутри ORION (console history).
4) Добавить чек в validation checklist.
5) Прогнать `scripts/quality_gate_docker.sh` и закоммитить.

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (behavior changed)
- [x] Repo clean (`git status --porcelain` is expected)

## Evidence (commands → output)

- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build --force-recreate operator-console` → `operator-console Started/healthy`
- `docker exec qiki-operator-console python /workspace/tools/bios_status_smoke.py` → `OK: received bios status on qiki.events.v1.bios_status`
- ORION UI confirmation (tmux capture):
  - `tmux capture-pane -p -t %3 -S -120 | sed -r 's/\x1B\[[0-9;?]*[ -/]*[@-~]//g' | rg 'BIOS (loaded|загрузился)'`
  - → `BIOS loaded/BIOS загрузился: OK/ОК`
- `bash scripts/quality_gate_docker.sh` → `OK`

## Notes / Risks

- Лог-строка объявляется один раз (first event) и зависит от реального события BIOS (без моков).

## Next

1) Вести дальнейшие шаги по канону `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.

