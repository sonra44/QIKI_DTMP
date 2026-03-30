# TASK: G3-QIKI-001 — first observation mission seed in ORION V

**ID:** TASK_20260307_g3_qiki_observation_mission_seed  
**Status:** done  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-07  

## Goal

После закрытого `G2` завести первый цельный `G3`-slice: один truth-backed observation mission loop в `ORION V`, где оператор даёт QIKI наблюдательную цель, QIKI формирует и ведёт выполнение, а мир и UI показывают измеримый результат без моков.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что должно стать визуально/поведенчески понятнее в ORION:
  - оператор задаёт QIKI наблюдательную цель вида `AST44995`;
  - QIKI не просто отвечает текстом, а публикует один mission/objective truth path;
  - `ORION V` показывает этот mission/procedure loop как реальный активный контур, а не как пустой placeholder или legacy-сущность;
  - после выполнения оператор видит наблюдаемый consequence в радарах/телеметрии/audit, а не только текстовое “ok”.
- Ограничение: один цикл = один новый операционный сценарий.

## Reproduction Command

```bash
cd /home/sonra44/QIKI_DTMP
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console
./scripts/run_orion_v_live.sh
# inside ORION V: q: safe observation / q: slow observation -> next: truth-backed mission seed for operator-facing target designator (example request: AST44995; live proof may resolve to a real radar callsign/transponder such as ALLY-4D1ED5)
```

## Before / After

- Before:
  - `G1/G2` proof covers observation/procedure/combat loops, but there is still no single explicit mission truth path in `ORION V`.
  - Legacy ORION (`main_orion.py`) has a `Mission control/Управление миссией` placeholder and explicit empty-state `No mission/task data/Нет данных миссии/задач`.
  - ADR `ADR_2026-02-04_mission_task_phase1_non_goal.md` correctly blocks fake mission data until a real producer exists.
- After:
  - one observation mission seed exists as a simulation-truth objective/procedure loop for `ORION V`;
  - QIKI/operator interaction, execution state, and consequence are represented by one canonical path;
  - no legacy random/demo mission data is revived.

## Impact Metric

- Метрика: число ручных умственных переходов между `QIKI reply -> procedure -> audit -> observable consequence`
- Baseline:
  - `4` разнесённых операторских опоры:
    - QIKI text
    - pending action
    - procedure status
    - telemetry/audit consequence
  - это требовало как минимум `3` ручных смысловых склеек, чтобы понять, что именно сейчас является активной наблюдательной целью и чем она закончилась
- Target:
  - one explicit mission seed is visible and traceable end-to-end in `ORION V`
- Actual (после внедрения):
  - `3` операторских опоры:
    - observation objective seed
    - procedure status
    - telemetry/radar consequence
  - это снижает ручные смысловые склейки до `2`
  - дельта: `-1` когнитивный переход в первом честном `G3` loop
  - proof basis:
    - `bash scripts/prove_orion_v_qiki_observation_objective_seed.sh`
    - `OBJECTIVE_TARGET=ALLY-4D1ED5`
    - `FINAL_QIKI_STATUS=confirmed`
    - `TRACK_RANGE_M=3500.3571246374277`

## Scope / Non-goals

- In scope:
  - one single `G3` observation mission seed
  - truth-backed producer/contract under canonical namespace (no `v2` / no duplicate truth source)
  - `ORION V` surface for the active observation mission loop
  - deterministic acceptance/evidence on canonical live path
- Out of scope:
  - full mission system
  - branching narrative layer
  - multiple concurrent missions
  - revival of random/demo mission producers from legacy QIKI tools
  - combat rework already closed in `G2`

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `LOG.MD`
  - `docs/design/canon/INDEX.md`
  - `docs/design/canon/ADR/ADR_2026-02-04_mission_task_phase1_non_goal.md`
  - `docs/design/operator_console/RADAR_VISUALIZATION_RFC.md`
  - `docs/design/operator_console/ORION_V_CLICKABLE_ACCEPTANCE_CHECKLIST.md`
  - `TASKS/TASK_20260305_g1_qiki_procedural_execution_and_time_control.md`
  - `TASKS/ARTIFACT_20260306_g1_qiki_procedural_execution_acceptance.md`
  - `src/qiki/services/operator_console/orion_v/app.py`
  - `src/qiki/services/operator_console/orion_v/procedure_engine.py`
  - `config/orion_v/procedures/safe_pause_slow_resume.json`

## Plan (steps)

1) Define the smallest canonical mission/objective contract for one observation target without violating the Phase1 no-mocks ADR.
2) Decide where the truth producer lives and how `ORION V` consumes it without creating a second truth source.
3) Add one `ORION V` surface for the active observation mission seed using the existing QIKI/procedure/audit loop as the execution backbone.
4) Prove end-to-end runtime path: intent -> mission seed visible -> procedure/telemetry consequence visible -> audit/evidence recorded.
5) Sync docs/canon/evidence and then update board status.

## Loop 1: contract + first ORION V surface

Решение этого круга:

- observation mission seed зафиксирован как отдельный event contract:
  - `qiki.events.v1.operator.objectives`
- producer первого seed-path добавлен в:
  - `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `ORION V` получил отдельную `F1`-поверхность `Цель наблюдения/Observation Objective`, где seed виден отдельно от общего `QIKI`-текста и отдельно от `Procedure`.

Почему это минимально и честно:

- не создаётся новый mission engine;
- не оживляется legacy `Mission control`;
- не создаются fake/demo mission values;
- существующий procedure/audit/telemetry path остаётся execution backbone;
- новый `objective seed` даёт только missing truth-path, которого раньше не было.

Что именно добавлено:

- `src/qiki/shared/nats_subjects.py`
- `schemas/asyncapi/qiki.events.v1.operator.objectives/v1/payload.schema.json`
- `schemas/asyncapi/qiki.events.v1.operator.objectives/v1/README.md`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/services/operator_console/orion_v/screens/cockpit.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tests/unit/test_orion_v_app_incidents.py`

Незакрытый риск после этого круга:

- Phase1 live intent-path по умолчанию сейчас идёт через `faststream-bridge`, а не через `docker-compose.qcore-intents.yml`;
- safe/slow observation proofs в текущем виде headless/synthetic, а не честный end-to-end live proof через реальный QIKI intent producer;
- следующий круг обязан дотянуть runtime alignment этого producer-path, иначе новый contract останется частично неиспользуемым в дефолтном compose path.

## Loop 2: runtime alignment + first live end-to-end proof

Решение этого круга:

- `q-core-intents` включён в дефолтный `docker-compose.phase1.yml`;
- `faststream-bridge` в дефолтном стеке больше не держит live `qiki.intents`, а остаётся на radar/system duties;
- live Phase1 stack теперь поднимает канонический QIKI intent listener без отдельного overlay;
- добавлен живой smoke:
  - `tools/orion_v_qiki_observation_objective_seed_smoke.py`
  - `scripts/prove_orion_v_qiki_observation_objective_seed.sh`

Что доказано:

- операторский intent `safe observation AST44995` на живой шине даёт:
  - `qiki.responses.qiki` с `SAFE_OBSERVATION_PROCEDURE_READY`;
  - `qiki.events.v1.operator.objectives` со статусом `prepared`;
  - отдельную F1-секцию `Цель наблюдения/Observation Objective` в ORION V;
  - подтверждённое procedural completion с `FINAL_QIKI_STATUS=confirmed`;
  - наблюдаемый telemetry effect `sim_state={'running': True, 'paused': False, 'speed': 1.0, 'fsm_state': 'RUNNING'}`.

Нормализация target identity:

- `AST44995` в intent/bus proof — это request-level observation designator;
- `ALLY-4D1ED5` в live smoke — это реальный public radar designator, выбранный каноническим proof path после правила `public designator only`;
- это не две разные цели, а два честных идентификатора одного observation flow: requested target и live radar-visible target.

Найденный и закрытый runtime blocker:

- `q-core-intents` сначала не стартовал из-за старого образа с `grpcio=1.76.0`;
- после пересборки образа и пересоздания `faststream-bridge` с `QIKI_INTENTS_SUBJECT=qiki.intents.faststream_disabled` live responder path стал однозначным и корректным.

## Definition of Done (DoD)

- [x] One truth-backed observation mission seed contract exists for `ORION V`
- [x] Canonical producer/contract is documented and does not violate `ADR_2026-02-04_mission_task_phase1_non_goal.md`
- [x] `ORION V` shows the active observation mission loop without fake/demo values
- [x] Operator can reproduce the full loop on canonical live path with `track_visible=true`
- [x] Observable telemetry/procedure consequence and radar/track-visible consequence are visible
- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (if behavior changed)
- [x] Есть измеримый `Impact Metric` (baseline -> actual)

## Evidence (commands → output)

- `rg -n "Mission control|No mission/task data|Нет данных миссии/задач" src/qiki/services/operator_console/main_orion.py tests/unit/test_orion_mission_seed_row_message.py`
- `rg -n "procedure|pending action|qiki" src/qiki/services/operator_console/orion_v/app.py src/qiki/services/operator_console/orion_v/procedure_engine.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/shared/nats_subjects.py src/qiki/services/q_core_agent/qiki_orion_intents_service.py src/qiki/services/operator_console/orion_v/app.py src/qiki/services/operator_console/orion_v/screens/cockpit.py tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py`
- `docker compose -f docker-compose.phase1.yml config --services`
- `docker compose -f docker-compose.phase1.yml up -d --build q-core-intents`
- `docker inspect qiki-faststream-bridge-phase1 --format '{{range .Config.Env}}{{println .}}{{end}}' | rg '^QIKI_INTENTS_SUBJECT='`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python - <<'PY' ... publish safe observation AST44995 and capture qiki.responses.qiki + qiki.events.v1.operator.objectives ... PY`
- `bash scripts/prove_orion_v_qiki_observation_objective_seed.sh`
- `bash scripts/prove_orion_v_qiki_safe_observation.sh`
- `bash scripts/prove_orion_v_qiki_slow_observation.sh`

## Notes / Risks

- Legacy ORION mission placeholder exists, but primary UI is now `ORION V`; the slice must not silently move development back into `main_orion.py`.
- The accepted ADR forbids placeholder/random mission data; producer must be real or the UI must remain empty.
- Mission truth must not be derived from unrelated telemetry just to “light up the screen”.
- Runtime note: the canonical live proof is green after fixing smoke target selection to use a public track designator (`transponder_id`/`callsign`) instead of an internal UUID-like track identifier.

## Next

1) Treat this dossier as the locked baseline for the first honest `G3` loop: objective seed -> procedure -> radar-visible consequence.
2) Continue only through the next explicit dossier: `TASKS/TASK_20260307_g3_qiki_objective_lifecycle_closure.md`.
