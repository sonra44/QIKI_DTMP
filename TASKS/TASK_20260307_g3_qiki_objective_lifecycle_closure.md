# TASK: G3-QIKI-002 — observation objective lifecycle closure in ORION V

**ID:** TASK_20260307_g3_qiki_objective_lifecycle_closure  
**Status:** done  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-07  

## Goal

Сделать следующий честный `G3`-шаг после seed baseline: observation objective в `ORION V` должен иметь явный lifecycle closure, чтобы оператор видел завершение цели как отдельный truth-backed факт, а не собирал его вручную из QIKI текста, procedure status и побочного telemetry consequence.

Зафиксированная vocabulary для этого шага:

- `prepared` — objective seed подготовлен и видим оператору;
- `confirmed` — objective закрыт успешно на подтверждённом consequence;
- `failed` — objective закрыт неуспешно;
- `cancelled` — objective снят до успешного closure;
- отдельный `active` в `v1` не вводим: running-state уже живёт на procedure backbone и не должен дублироваться objective event path.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что должно стать визуально/поведенчески понятнее в ORION:
  - оператор задаёт observation objective;
  - objective появляется как отдельная сущность, как и раньше;
  - после выполнения/срыва objective меняет собственный статус в том же truth path;
  - оператор видит closure цели в `F1`, а не выводит его косвенно из нескольких поверхностей.
- Ограничение: не расширять mission system до множественных миссий, ветвлений и narrative-оркестрации.

## Reproduction Command

```bash
cd /home/sonra44/QIKI_DTMP
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
./scripts/run_orion_v_live.sh
# inside ORION V: trigger safe/slow observation objective and observe objective status transition in F1
```

## Before / After

- Before:
  - `G3-QIKI-001` уже даёт truth-backed objective seed и radar-visible consequence;
  - но closure цели остаётся операторским выводом из нескольких поверхностей;
  - `F1` показывает seed, а не отдельный objective outcome.
- After:
  - тот же canonical event path несёт не только seed, но и lifecycle closure;
  - `ORION V` показывает objective completion/failure как отдельный статус цели;
  - оператору не нужно вручную склеивать “QIKI подтвердил” + “процедура завершилась” + “трек виден”.

## Impact Metric

- Метрика: число ручных умственных переходов между `objective seed -> execution -> objective closure`
- Baseline:
  - после `G3-QIKI-001` осталось `2` ручных смысловых склейки
- Target:
  - уменьшить до `1` за счёт явного objective lifecycle closure в той же операторской поверхности
- Actual:
  - после текущего closure-aware loop осталось `1` ручная смысловая склейка
  - `delta = -1` относительно baseline `G3-QIKI-001`
- Обоснование:
  - `F1` теперь сама показывает objective closure как first-class state (`confirmed`), поэтому оператору больше не нужно вручную склеивать `procedure status + QIKI confirmation + objective outcome`;
  - один ручной переход всё ещё остаётся: оператор по-прежнему соотносит request-level objective context с live radar/telemetry consequence конкретной цели.

## Scope / Non-goals

- In scope:
  - lifecycle closure для одного observation objective
  - использование существующего canonical subject `qiki.events.v1.operator.objectives`
  - ORION V updates for explicit objective status rendering
  - deterministic acceptance on canonical live path
- Out of scope:
  - multiple simultaneous objectives
  - full mission tree / branching narrative
  - fake completion derived from unrelated telemetry
  - новый parallel truth source или `v2` subject

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Previous baseline dossier: `TASKS/TASK_20260307_g3_qiki_observation_mission_seed.md`
- Acceptance baseline: `TASKS/ARTIFACT_20260307_g3_qiki_observation_objective_seed_acceptance.md`
- ADR guardrail: `docs/design/canon/ADR/ADR_2026-02-04_mission_task_phase1_non_goal.md`
- Product schema source: `LOG.MD`

## Plan (steps)

1) Bind the exact closure fact to the fixed `v1` vocabulary (`confirmed|failed|cancelled`) without introducing a second mission truth source.
2) Decide which runtime fact closes the objective and where that fact is emitted on the canonical path.
3) Update `ORION V` objective rendering so closure is visible in `F1`.
4) Prove end-to-end live path on the default Phase1 stack.
5) Record a new `Impact Metric` actual value and sync board/docs/memory.

## Current progress

Сделано в текущем круге:

- exact `v1` vocabulary зафиксирована в contract docs:
  - `prepared`
  - `confirmed`
  - `failed`
  - `cancelled`
- отдельный `active` сознательно не вводился, чтобы не дублировать procedure running-state;
- `ORION V` теперь публикует objective closure update на том же `qiki.events.v1.operator.objectives` path:
  - `confirmed` при подтверждённом telemetry consequence;
  - `failed` при неуспешном завершении procedure;
  - `cancelled` при отмене prepared objective оператором;
- `ORION V` `F1` теперь рендерит closure status как отдельный first-class operator fact.

Что уже доказано:

- live canonical proof на default Phase1 stack теперь доходит до:
  - `OBJECTIVE_KIND=observation_objective_update`
  - `OBJECTIVE_STATUS=confirmed`
  - `FINAL_QIKI_STATUS=confirmed`
- unit coverage подтверждает:
  - local/objective bus update path;
  - render confirmed-closure в cockpit;
  - cancelled path через `_cancel_qiki_pending_action`.
- explicit `failed` contour теперь тоже подтверждён unit-proof:
  - `_execute_qiki_pending_procedure(...)` публикует `status=failed`
  - local objective state переходит в `failed`
  - `qiki_last_response.consequence.status` переходит в `failed`
- `Impact Metric` обновлён до `2 -> 1` ручных смысловых склеек (`delta = -1`) для closure-aware loop.

## Definition of Done (DoD)

- [x] Objective lifecycle closure is emitted on the canonical `qiki.events.v1.operator.objectives` path
- [x] `ORION V` shows objective completion/failure as a first-class operator fact
- [x] Canonical live proof passes on the default Phase1 stack
- [x] No new fake/demo mission state is introduced
- [x] Есть измеримый `Impact Metric` (baseline -> actual)

Текущий честный статус DoD:

- [x] Exact closure vocabulary fixed in schema/readme
- [x] `confirmed` closure emitted on canonical path and proven live
- [x] `cancelled` closure path covered by unit test
- [x] `failed` closure path covered by unit test
- [x] `ORION V` renders confirmed closure as first-class objective state
- [x] `Impact Metric` updated to `2 -> 1` manual joins (`delta = -1`)
- [x] Dossier closeout criteria are satisfied

## Evidence (commands → output)

- `rg -n "operator.objectives|objective" src/qiki/services/q_core_agent src/qiki/services/operator_console/orion_v`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q ...`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check ...`
- `bash scripts/prove_orion_v_qiki_observation_objective_seed.sh`

Current proof snapshot:

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_app_incidents.py -k 'failed_objective_update or publish_observation_objective_update_updates_local_state_and_bus or cancel_qiki_pending_action_emits_cancelled_objective_update'`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/app.py src/qiki/services/operator_console/orion_v/screens/cockpit.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py tools/orion_v_qiki_observation_objective_seed_smoke.py`
- `bash scripts/prove_orion_v_qiki_observation_objective_seed.sh`
  - `OBJECTIVE_KIND=observation_objective_update`
  - `OBJECTIVE_STATUS=confirmed`
  - `FINAL_QIKI_STATUS=confirmed`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check tests/unit/test_orion_v_app_incidents.py`
  - `All checks passed!`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_app_incidents.py -k 'failed_objective_update or publish_observation_objective_update_updates_local_state_and_bus or cancel_qiki_pending_action_emits_cancelled_objective_update'`
  - `... [100%]`

## Notes / Risks

- Нужно сохранить один truth path; closure нельзя “дорисовать” из unrelated telemetry.
- Exact closure vocabulary is now fixed in the current `v1` schema/readme as `prepared|confirmed|failed|cancelled`; code work must stay inside that set and must not reintroduce `active` as a duplicate of procedure running-state.
- Если lifecycle closure потребует нового event, сначала нужен ADR-level аргумент, иначе это drift.
- Этот шаг существует только как продолжение `G3-QIKI-001`, не как новый mission engine.

## Next

1) Sync board after the completed `G3-QIKI-002` closeout.
2) Define the next single honest `G3` sub-slice before entering new code.
