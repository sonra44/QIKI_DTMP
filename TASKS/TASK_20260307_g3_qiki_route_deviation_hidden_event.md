# TASK: G3-QIKI-004 — route deviation reveals a hidden observation event in ORION V

**ID:** TASK_20260307_g3_qiki_route_deviation_hidden_event  
**Status:** done  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-07  

## Goal

Сделать следующий честный `G3`-шаг после dual-route baseline: отклонение от “официального” observation route должно породить скрытое событие, видимое оператору как отдельный truth-backed факт в `ORION V`, а не как скриптовый сюрприз вне текущего objective/procedure path.

## Why this is the next honest G3 slice

- В `LOG.MD` следующий `G3`-тест после двух валидных маршрутов звучит так:
  - отклонение от “официального” задания рождает скрытое событие
- После `G3-QIKI-003` у нас уже есть:
  - одна observation target
  - два валидных маршрута
  - route choice как first-class operator fact
- Значит следующий естественный шаг: первый системно объяснимый off-route consequence, а не новая абстрактная mission tree.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что должно стать визуально/поведенчески понятнее в ORION:
  - оператор получает observation objective для одной цели;
  - выбирает route, который не является “официально рекомендованным”;
  - в ответ мир/QIKI порождают скрытое observation-relevant событие;
  - это событие видно как отдельный truth-backed факт, а closure цели продолжает быть причинно связанной с выбранным маршрутом.
- Ограничение: не строить full branching mission graph и не вводить narrative scripting engine.

## Reproduction Command

```bash
cd /home/sonra44/QIKI_DTMP
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
./scripts/run_orion_v_live.sh
# inside ORION V: choose the non-default observation route for one target and observe the hidden event on the canonical truth path
```

## Before / After

- Before:
  - одна цель уже имеет два валидных маршрута;
  - route choice виден и честно закрывается;
  - но отклонение от “официального” маршрута ещё не рождает нового world/QIKI consequence.
- After:
  - off-route choice порождает один скрытый, но системно объяснимый event;
  - ORION V показывает его как truth-backed consequence, а не как несвязанный текст;
  - это становится первым честным признаком миссионной вариативности beyond route selection.

## Impact Metric

- Метрика: число ручных смысловых переходов между `route deviation -> hidden event -> objective context`
- Baseline:
  - после `G3-QIKI-003` off-route consequence отсутствует как first-class fact;
  - оператору приходилось вручную удерживать в голове минимум 2 недоказанных перехода:
    `slow route = deviation?` и `есть ли у этого deviation route вообще отдельный consequence?`
- Target:
  - hidden event становится видимым и причинно связанным с route deviation
- Actual:
  - `route_role=deviation` и `HIDDEN_EVENT_REVEALED` теперь сходятся на одном linked contour в `ORION V`;
  - ручные смысловые переходы для цепочки `route deviation -> hidden event -> objective context` снижены с `2` до `0`;
  - `delta = -2`

## Scope / Non-goals

- In scope:
  - один target
  - одно deviation-triggered hidden event
  - reuse existing objective/procedure/event path
  - deterministic proof on canonical Phase1 stack
- Out of scope:
  - full branching mission tree
  - multiple hidden events per route
  - narrative scripting layer
  - new truth subject unless absolutely forced by current canon

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Previous closed G3 dossiers:
  - `TASKS/TASK_20260307_g3_qiki_observation_mission_seed.md`
  - `TASKS/TASK_20260307_g3_qiki_objective_lifecycle_closure.md`
  - `TASKS/TASK_20260307_g3_qiki_dual_route_observation_choice.md`
- Product source: `LOG.MD`
- ADR guardrail: `docs/design/canon/ADR/ADR_2026-02-04_mission_task_phase1_non_goal.md`

## Plan (steps)

1) Decide the smallest honest definition of an “official” vs “deviation” route for one observation target.
2) Bind one hidden event to the deviation route without inventing a narrative engine.
3) Reuse the current objective/procedure/event path so the hidden event stays truth-backed.
4) Prove the event on the canonical stack.
5) Record `Impact Metric` and sync board/docs/memory.

## Minimal contract (implemented)

- Canonical route-role point:
  - `qiki.events.v1.operator.objectives`
  - same payload that already carries `objective_id`, `observation_style`, `procedure_name`, `proposal_id`, `request_id`
  - new explicit marker: `route_role=official|deviation`
- Current G3 mapping:
  - `safe_pause_resume` + `observation_style=safe` -> `route_role=official`
  - `safe_pause_slow_resume` + `observation_style=slow` -> `route_role=deviation`
- Hidden-event producer:
  - existing `q_core_intents` observation path
  - trigger: deviation observation contour is prepared on the canonical objective path
  - publish target: existing `qiki.events.v1.audit`
  - event shape:
    - `objective_id`
    - `proposal_id`
    - `request_id`
    - `procedure_name`
    - `target_designator`
    - `route_role`
    - `event_type=HIDDEN_EVENT_REVEALED`
    - `reason_code=DEVIATION_ROUTE_REVEALS_HIDDEN_OBSERVATION_EVENT`
    - operator-facing `message`

Почему это честно:

- route semantics остаётся на уже существующем objective truth path, а не переезжает в UI;
- hidden event не получает новый engine и не требует отдельного mission subject;
- `ORION V` linked facts подхватывает событие по уже существующим linkage keys.

## Current progress

Сделано в текущем круге:

- `route_role` добавлен в canonical observation objective payload и schema;
- explicit mapping `official/deviation` закреплён на существующем objective contour, без второго truth source;
- deviation route now publishes one linked hidden event on existing `qiki.events.v1.audit`;
- `ORION V` F1 shows `route_role` and receives the hidden event through the existing linked-facts chain;
- targeted unit coverage is green for:
  - objective payload route-role
  - deviation-only hidden-event payload
  - linked-facts chain in ORION V
  - F1 rendering of explicit route role

Текущий proof status:

- green:
  - targeted unit + lint proof
  - live-like deviation smoke on current Phase1 stack (`slow` route -> hidden event visible in linked facts)
  - clean official-route smoke on a fresh stack (`safe` route -> `ROUTE_ROLE=official`, no hidden-event line, same canonical objective closure)

## Why prepare-path is acceptable here

- Для минимального `G3-QIKI-004` среза нам нужно было доказать не полный mission consequence loop, а первый честный факт:
  deviation route на существующем observation contour рождает отдельный linked hidden event без нового engine.
- Поэтому hidden event публикуется на `prepare-path` того же objective contour:
  route choice уже truth-backed, objective linkage keys уже существуют, и `ORION V` может показать consequence без UI-эвристики.
- Это допустимо как минимальный `G3` slice, потому что:
  - не создаётся второй truth source;
  - не появляется synthetic narrative branch;
  - сохраняется один continuous contour `objective -> linked facts -> closure`.
- Это ещё не полный mission consequence loop:
  более поздняя publication point после closure или during world progression остаётся отдельным следующим решением, а не скрытым scope creep внутри текущего среза.

## Evidence

- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py -k 'observation_objective_event or observation_hidden_event'`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_app_incidents.py -k 'build_objective_timeline_lines'`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_cockpit.py -k 'observation_objective'`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/q_core_agent/qiki_orion_intents_service.py src/qiki/services/operator_console/orion_v/screens/cockpit.py tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_app_incidents.py tests/unit/test_orion_v_cockpit.py tools/orion_v_qiki_observation_objective_seed_smoke.py`
- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml down`
- `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console q-core-intents qiki-dev`
- `docker compose -f docker-compose.phase1.yml exec -T -e QIKI_OBSERVATION_STYLE=safe qiki-dev python tools/orion_v_qiki_observation_objective_seed_smoke.py`
  - `ROUTE_ROLE=official`
  - `OBJECTIVE_PROCEDURE=safe_pause_resume`
  - `OBJECTIVE_STATUS=confirmed`
  - no `HIDDEN_EVENT_REVEALED` line in the official route proof
- `docker compose -f docker-compose.phase1.yml exec -T -e QIKI_OBSERVATION_STYLE=slow qiki-dev python tools/orion_v_qiki_observation_objective_seed_smoke.py`
  - `ROUTE_ROLE=deviation`
  - `OBJECTIVE_PROCEDURE=safe_pause_slow_resume`
  - `OBJECTIVE_STATUS=confirmed`
  - `HIDDEN_EVENT_LINE=audit | HIDDEN_EVENT_REVEALED | ...`

## Definition of Done (DoD)

- [x] One observation target has a defined official route and one deviation route
- [x] Choosing the deviation route triggers one hidden event
- [x] The hidden event is visible in ORION V as a truth-backed fact
- [x] Objective context remains causally linked to the chosen route and hidden event
- [x] Есть измеримый `Impact Metric` (baseline -> actual)

## Notes / Risks

- Не вводить narrative graph or mission engine.
- Не делать hidden event synthetic текстом без world/QIKI truth.
- Не разрывать связь между objective context и deviation consequence.
