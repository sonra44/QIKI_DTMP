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
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev mypy src/qiki/services/q_bios_service/tests/test_http_endpoints.py`
  - `Success: no issues found in 1 source file`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_bios_service/tests/test_http_endpoints.py`
  - `. [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 8'`
  - `Found 183 errors in 13 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_qiki_response_handling.py src/qiki/services/operator_console/tests/test_events_rowkey_normalization.py`
  - `3 passed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 8'`
  - `Found 176 errors in 11 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_record_replay_commands.py`
  - `3 passed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 8'`
  - `Found 171 errors in 10 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_incidents_store.py`
  - `4 passed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 8'`
  - `Found 169 errors in 8 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_qiki_response_handling.py src/qiki/services/operator_console/tests/test_record_replay_commands.py src/qiki/services/operator_console/tests/test_events_rowkey_normalization.py tests/unit/test_orion_proposal_actions.py`
  - `........ [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 8'`
  - `Found 159 errors in 8 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_record_replay_commands.py src/qiki/services/operator_console/tests/test_qiki_response_handling.py tests/unit/test_orion_proposal_actions.py tests/unit/test_orion_control_provenance.py`
  - `................. [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 8'`
  - `Found 150 errors in 8 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_qiki_response_handling.py src/qiki/services/operator_console/tests/test_record_replay_commands.py src/qiki/services/operator_console/tests/test_events_rowkey_normalization.py src/qiki/services/operator_console/tests/test_incidents_store.py tests/unit/test_orion_proposal_actions.py tests/unit/test_orion_control_provenance.py`
  - `...................... [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 8'`
  - `Found 135 errors in 8 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_incidents_store.py src/qiki/services/operator_console/tests/test_record_replay_commands.py src/qiki/services/operator_console/tests/test_qiki_response_handling.py tests/unit/test_orion_control_provenance.py tests/unit/test_orion_proposal_actions.py`
  - `..................... [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 8'`
  - `Found 113 errors in 8 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_incidents_store.py src/qiki/services/operator_console/tests/test_record_replay_commands.py src/qiki/services/operator_console/tests/test_qiki_response_handling.py tests/unit/test_orion_control_provenance.py tests/unit/test_orion_proposal_actions.py`
  - `..................... [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 12'`
  - `Found 105 errors in 8 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_incidents_store.py src/qiki/services/operator_console/tests/test_record_replay_commands.py src/qiki/services/operator_console/tests/test_qiki_response_handling.py tests/unit/test_orion_control_provenance.py tests/unit/test_orion_proposal_actions.py`
  - `..................... [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 14'`
  - `Found 82 errors in 8 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_incidents_store.py src/qiki/services/operator_console/tests/test_record_replay_commands.py src/qiki/services/operator_console/tests/test_qiki_response_handling.py tests/unit/test_orion_control_provenance.py tests/unit/test_orion_proposal_actions.py`
  - `..................... [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 24'`
  - `Found 59 errors in 8 files (checked 214 source files)`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/operator_console/tests/test_incidents_store.py src/qiki/services/operator_console/tests/test_record_replay_commands.py src/qiki/services/operator_console/tests/test_qiki_response_handling.py tests/unit/test_orion_control_provenance.py tests/unit/test_orion_proposal_actions.py`
  - `..................... [100%]`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc 'mypy src 2>&1 | tail -n 28'`
  - `Found 37 errors in 7 files (checked 214 source files)`

## Notes / Risks

- Главный риск: расползание области и попытка "починить всё сразу".
- Митигация: маленькие батчи (10-20 ошибок), модульный приоритет, частые коммиты.
- Решение по gate: feature-loop принимается по slice-acceptance; mypy debt ведётся отдельным треком.

## Next

1) Week 1 batch-1 completed: reduced baseline from `198/19` to `191/14`.
2) Week 1 batch-2 completed: reduced baseline from `191/14` to `183/13`.
3) Week 1 batch-3 completed: reduced baseline from `183/13` to `176/11` via low-risk `operator_console/tests`.
4) Week 1 batch-4 completed: reduced baseline from `176/11` to `171/10` via `test_record_replay_commands.py`.
5) Week 1 batch-5 completed: reduced baseline from `171/10` to `169/8` via `test_incidents_store.py` + yaml stub suppression.
6) Week 1 batch-6 completed: reduced baseline from `169/8` to `159/8` via low-risk arg-type fixes in `main_orion.py` (QIKI request types + callback signatures).
7) Week 1 batch-7 completed: reduced baseline from `159/8` to `150/8` via `main_orion.py` union-attr and optional-assignment cleanup in openai/record/replay/radar command paths.
8) Week 1 batch-8 completed: reduced baseline from `150/8` to `144/8` via `main_orion.py` validation/focus/secret-key typing fixes.
9) Week 1 batch-9 completed: reduced baseline from `144/8` to `135/8` via `main_orion.py` incident/radar/selection/secret-key/type narrowing fixes.
10) Week 1 batch-10 completed: reduced baseline from `135/8` to `113/8` via `main_orion.py` sensor-plane typing cleanup, callback signatures, and optional narrowing in command paths.
11) Week 1 batch-11 completed: reduced baseline from `113/8` to `105/8` via additional `main_orion.py` sensor-plane narrowing (`radiation/proximity` typed extraction).
12) Week 1 batch-12 completed: reduced baseline from `105/8` to `82/8` via `main_orion.py` sensor-plane typing cleanup (`imu/radiation/magnetometer` extraction + numeric narrowing).
13) Week 2 batch-13 completed: reduced baseline from `82/8` to `59/8` via `main_orion.py` medium-risk cleanup (`selection` optional guards, widget/app typed dispatch, mission payload narrowing, and local no-redef normalization in sensor-plane/command paths).
14) Week 2 batch-14 completed: reduced baseline from `59/8` to `37/7` via early-file `main_orion.py` cluster cleanup (`post_results` list narrowing, speed parsing guard, `_RadarMouseMixin` app/button-safe access, and radar bitmap fallback typing ignores) + yaml import typing.
15) Week 2 batch-15: continue cross-file residual cluster now in tail (`src/qiki/services/operator_console/main.py`, `src/qiki/services/qiki_chat/handler.py`, `src/qiki/services/operator_console/clients/nats_client.py`, `src/qiki/shared/record_replay.py`) using same micro-batch/test/recount loop.
