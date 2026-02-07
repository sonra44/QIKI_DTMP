# TASK: Mypy baseline burndown sprint (2 weeks)

**ID:** TASK_20260207_mypy_baseline_burndown_sprint
**Status:** in_progress
**Owner:** Codex
**Date created:** 2026-02-07

## Goal

Снизить mypy baseline debt с 198 ошибок до управляемого уровня без блокировки feature-delivery.

## Scope / Non-goals

- In scope:
  - Плановое снижение текущего mypy-долга по приоритетным модулям.
  - Правило "изменяемый файл должен становиться mypy-clean".
  - Регулярные checkpoint-отчёты по числу ошибок.
- Out of scope:
  - Большой архитектурный рефактор ORION за один батч.
  - Блокировка feature-срезов из-за legacy mypy-долга вне изменяемых файлов.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `scripts/quality_gate_docker.sh`
  - `mypy.ini`
  - `src/qiki/services/q_bios_service/`
  - `src/qiki/services/shell_os/`
  - `src/qiki/services/operator_console/`

## Plan (steps)

1) Зафиксировать baseline: `198 errors in 19 files` (на 2026-02-07).
2) Week 1: закрыть low-risk ошибки в `q_bios_service`, `shell_os`, части `tests` (целевой спад: 40-60).
3) Week 2: закрыть среднерисковые ошибки в `operator_console/radar` и `shared` (целевой спад: 60-80).
4) На каждом PR: не допускать новых mypy-ошибок в изменённых файлах.
5) Раз в рабочий цикл фиксировать прогресс в `STATUS` + `TODO_NEXT`.

## Definition of Done (DoD)

- [ ] Mypy baseline reduced to <= 110 errors
- [ ] No new mypy errors introduced in changed files during sprint
- [ ] Progress checkpoints recorded with commands and counts
- [ ] Canon docs synced if policy changed

## Evidence (commands -> output)

- `QUALITY_GATE_RUN_MYPY=1 QUALITY_GATE_RUN_INTEGRATION=0 QUALITY_GATE_RUFF_FORMAT_CHECK=0 bash scripts/quality_gate_docker.sh`
  - `Found 198 errors in 19 files`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev mypy src/qiki/services/shell_os/main.py src/qiki/services/shell_os/ui/system_panel.py src/qiki/services/shell_os/ui/services_panel.py src/qiki/services/shell_os/ui/resources_panel.py src/qiki/services/q_bios_service/health_checker.py`
  - `Success: no issues found in 5 source files`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_bios_service/tests/test_http_endpoints.py src/qiki/services/shell_os/tests`
  - `..... [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 8'`
  - `Found 191 errors in 14 files (checked 214 source files)`

## Notes / Risks

- Главный риск: расползание области и попытка "починить всё сразу".
- Митигация: маленькие батчи (10-20 ошибок), модульный приоритет, частые коммиты.
- Решение по gate: feature-loop принимается по slice-acceptance; mypy debt ведётся отдельным треком.

## Next

1) Week 1 batch-1 completed: reduced baseline from `198/19` to `191/14`.
2) Week 1 batch-2: закрыть оставшиеся быстрые ошибки в `q_bios_service/tests/test_http_endpoints.py`.
3) Week 1 batch-3: перейти к low-risk `operator_console/tests` mypy issues (lambda typing / fixtures).
