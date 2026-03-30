# TASK: G3-QIKI-003 — dual-route observation choice for one target in ORION V

**ID:** TASK_20260307_g3_qiki_dual_route_observation_choice  
**Status:** done  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-07  

## Goal

Сделать первый честный `G3`-шаг после seed + closure baseline: одна observation objective должна иметь минимум два валидных маршрута достижения для одной и той же цели, чтобы `ORION V` и QIKI показывали не один “канонный” путь, а первую реальную миссионную вариативность без нового mission engine.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что должно стать визуально/поведенчески понятнее в ORION:
  - оператор задаёт observation target;
  - QIKI может предложить не один, а как минимум два валидных observation route для той же цели;
  - оператор осознанно выбирает маршрут;
  - `ORION V` показывает выбранный route как часть objective/procedure truth path;
  - closure цели остаётся на том же canonical path без ручной склейки между “какой был route” и “чем всё закончилось”.
- Ограничение: не расширять систему до full mission tree или narrative branching.

## Why this is the next honest G3 slice

- `LOG.MD` для `G3` требует: одна цель — минимум два валидных маршрута достижения.
- В текущем runtime уже есть реальные observation procedures:
  - `safe_pause_resume`
  - `safe_pause_slow_resume`
- Значит следующий шаг можно строить на существующем truth path, а не придумывать новый mission engine или synthetic branch logic.

## Reproduction Command

```bash
cd /home/sonra44/QIKI_DTMP
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
./scripts/run_orion_v_live.sh
# inside ORION V: trigger two valid observation routes for the same target and verify route selection + closure on the same objective path
```

## Before / After

- Before:
  - `G3-QIKI-001` даёт один truth-backed observation objective seed;
  - `G3-QIKI-002` даёт explicit lifecycle closure;
  - но одна цель всё ещё ощущается как один “правильный” путь за раз.
- After:
  - одна и та же observation target может идти как минимум двумя валидными route-contours;
  - route choice явно виден и объясним;
  - выбранный route сохраняется в objective/procedure contour и не теряется при closure.

## Impact Metric

- Метрика: число ручных смысловых переходов между `target -> route choice -> procedure -> closure`
- Baseline:
  - после `G3-QIKI-002` route choice остаётся implicit и требует `1` дополнительную операторскую склейку
- Target:
  - route choice становится first-class fact для одной observation objective
- Actual:
  - после явного `Маршрут/Route` в objective contour и dual-route proof для одной цели дополнительных ручных склеек по route choice не осталось
  - `delta = -1` относительно baseline этого шага
- Обоснование:
  - один и тот же target теперь проходит через `safe` и `slow` route на одном canonical path;
  - route identity (`observation_style + procedure_name`) видна в `F1` и не теряется при closure;
  - оператору больше не нужно вручную выводить, каким именно маршрутом была закрыта observation objective.

## Scope / Non-goals

- In scope:
  - один target
  - два валидных observation route
  - route choice на существующем QIKI/ORION path
  - deterministic proof на canonical Phase1 stack
- Out of scope:
  - full mission tree
  - multiple concurrent objectives
  - hidden branches/event chains
  - new truth subject or mission engine

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Previous baseline dossiers:
  - `TASKS/TASK_20260307_g3_qiki_observation_mission_seed.md`
  - `TASKS/TASK_20260307_g3_qiki_objective_lifecycle_closure.md`
- Product source: `LOG.MD`
- ADR guardrail: `docs/design/canon/ADR/ADR_2026-02-04_mission_task_phase1_non_goal.md`

## Plan (steps)

1) Decide the smallest honest contract for “two valid routes for one observation target” on the existing truth path.
2) Reuse the already existing `safe` and `slow` observation procedures rather than inventing a new route system.
3) Make route choice explicit in the operator-facing objective/procedure contour.
4) Prove that the same target can complete through two valid routes on the canonical stack.
5) Record an updated `Impact Metric` and sync board/docs/memory.

## Contract baseline (pre-code)

Для `G3-QIKI-003` фиксируем минимальный честный контракт без новых полей и без нового subject:

- route identity для одной observation target выражается через уже существующие поля:
  - `observation_style`
  - `procedure_name`
  - `proposal_id`
- `observation_style=safe` <-> `procedure_name=safe_pause_resume`
- `observation_style=slow` <-> `procedure_name=safe_pause_slow_resume`
- route choice остаётся внутри того же canonical path:
  - `qiki.events.v1.operator.objectives`
- `objective_id` продолжает связывать seed, route choice и closure в один contour.

Почему этого достаточно для текущего шага:

- это уже реальные runtime procedures, а не synthetic branches;
- это даёт два валидных route для одной цели без второго truth source;
- это не превращает route choice в отдельный mission engine раньше времени.

## Definition of Done (DoD)

- [x] One observation target has at least two valid routes on the canonical path
- [x] Route choice is visible as a first-class operator fact in `ORION V`
- [x] Route identity survives through objective closure
- [x] Canonical proof covers both routes without mocks or parallel truth sources
- [x] Есть измеримый `Impact Metric` (baseline -> actual)

## Current progress

Сделано в текущем круге:

- objective contract cleanup:
  - `kind` в schema/readme теперь честно допускает и `observation_objective_seed`, и `observation_objective_update`;
- минимальный route-choice contract зафиксирован без новых полей:
  - `observation_style`
  - `procedure_name`
  - `proposal_id`
- `ORION V` теперь показывает route как first-class факт:
  - `Маршрут/Route: безопасный (safe)`
  - `Маршрут/Route: медленный (slow)`
- canonical dual-route proof проходит для одного live target на default Phase1 stack:
  - `safe_pause_resume`
  - `safe_pause_slow_resume`
  - оба с `OBJECTIVE_STATUS=confirmed`
  - route identity survives through closure on the same objective path.

## Evidence

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_cockpit.py -k 'observation_objective'`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/operator_console/orion_v/screens/cockpit.py tests/unit/test_orion_v_cockpit.py tools/orion_v_qiki_observation_objective_seed_smoke.py`
- `bash scripts/prove_orion_v_qiki_dual_route_observation_choice.sh`
  - `OBSERVATION_STYLE=safe`
  - `OBJECTIVE_TARGET=ALLY-244FA0`
  - `OBJECTIVE_PROCEDURE=safe_pause_resume`
  - `OBJECTIVE_STATUS=confirmed`
  - `OBSERVATION_STYLE=slow`
  - `OBJECTIVE_TARGET=ALLY-244FA0`
  - `OBJECTIVE_PROCEDURE=safe_pause_slow_resume`
  - `OBJECTIVE_STATUS=confirmed`

## Next

1) Sync board after the completed `G3-QIKI-003` closeout.
2) Define the next single honest `G3` sub-slice before entering new code.

## Notes / Risks

- Не вводить новый mission engine.
- Не дублировать objective truth path отдельным route-subject.
- Не превращать `safe` и `slow` в два разных несвязанных objective мира; речь именно про два route-contour для одной observation цели.
