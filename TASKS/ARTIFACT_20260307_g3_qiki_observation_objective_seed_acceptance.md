# ARTIFACT: G3-QIKI-001 observation objective seed acceptance

Статус: pass  
Дата: 2026-03-07  
Этап: `G3-QIKI-001`

## Цель

Подтвердить первый честный `G3`-контур:

- реальный QIKI intent в живом Phase1 stack;
- отдельный mission/objective truth path под `qiki.events.v1.operator.objectives`;
- видимая `F1`-поверхность в `ORION V`;
- подтверждённый procedural completion и telemetry effect без synthetic response injection.

## Что было проверено

### 1. Compose/runtime alignment

Проверено, что дефолтный `docker-compose.phase1.yml` теперь содержит:

- `q-core-intents` как канонический live listener для `qiki.intents`;
- `faststream-bridge` с `QIKI_INTENTS_SUBJECT=qiki.intents.faststream_disabled`;
- сохранённый `qiki.responses.qiki` path для `ORION V`.

### 2. Code/contract slice

Проверено наличие:

- canonical subject `qiki.events.v1.operator.objectives`;
- schema/docs для нового event contract;
- ORION V `F1` section `Цель наблюдения/Observation Objective`;
- targeted unit coverage для objective rendering/state ingestion.

### 3. Live end-to-end proof

Проверен живой сценарий:

- intent: `safe observation AST44995`
- response: `qiki.responses.qiki`
- objective event: `qiki.events.v1.operator.objectives`
- ORION V receives both and renders objective seed
- procedure executes and reaches `confirmed`
- telemetry reaches `sim_state=RUNNING paused=false speed=1.0`
- note on target identity: request-level proof still uses `AST44995`, while the live smoke records the public radar designator actually resolved on the stack (`ALLY-4D1ED5`); this is the expected normalization after the `public designator only` rule for canonical live proofs.

## Команды

```bash
docker compose -f docker-compose.phase1.yml config --services

docker compose -f docker-compose.phase1.yml up -d --build q-core-intents

docker inspect qiki-faststream-bridge-phase1 \
  --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | rg '^QIKI_INTENTS_SUBJECT='

docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/shared/nats_subjects.py \
  src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  src/qiki/services/operator_console/orion_v/app.py \
  src/qiki/services/operator_console/orion_v/screens/cockpit.py \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_app_incidents.py \
  tools/orion_v_qiki_observation_objective_seed_smoke.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_cockpit.py \
  tests/unit/test_orion_v_app_incidents.py

bash scripts/prove_orion_v_qiki_observation_objective_seed.sh
```

## Результаты

### Runtime bus proof

```text
OK: qiki_safe_observation_runtime_bus_proof
OBJECTIVE_JSON.subject = qiki.events.v1.operator.objectives
OBJECTIVE_JSON.status = prepared
OBJECTIVE_JSON.observation_style = safe
OBJECTIVE_JSON.target_designator = AST44995
RESPONSE_JSON.legality.reason_code = SAFE_OBSERVATION_PROCEDURE_READY
RESPONSE_JSON.proposed_actions[0].name = safe_pause_resume
```

### Live ORION V proof

```text
OK: orion_v_qiki_observation_objective_seed_smoke
OBJECTIVE_TARGET=ALLY-4D1ED5
TRACK_ID=21ddb257-e20a-5e0a-a75a-c26c4085f666
TRACK_RANGE_M=3500.3571246374277
TRACK_QUALITY=1.0
OBJECTIVE_PROCEDURE=safe_pause_resume
FINAL_QIKI_STATUS=confirmed
SIM_STATE={'running': True, 'paused': False, 'speed': 1.0, 'fsm_state': 'RUNNING'}
```

### Targeted unit/lint

```text
ruff check ... -> All checks passed!
pytest -q tests/unit/test_orion_v_cockpit.py tests/unit/test_orion_v_app_incidents.py -> PASS
```

## Вывод

Первый честный `G3`-контур теперь существует:

- observation mission/objective seed публикуется как отдельный truth event;
- ORION V показывает его как отдельную операторскую сущность, а не только как кусок QIKI-текста;
- live Phase1 stack использует канонический `q-core-intents` path по умолчанию;
- procedural completion и telemetry consequence подтверждены;
- radar/track-visible consequence подтверждён на каноническом live proof path.

## Следующий обязательный шаг

Не расширять mission system по инерции.

Следующий шаг:

1. считать этот `G3` loop закрытым baseline: `3 -> 2` ручных смысловых склеек (`delta = -1`) за счёт явного observation objective seed;
2. следующий шаг вести только через новый dossier `TASKS/TASK_20260307_g3_qiki_objective_lifecycle_closure.md`, не расширяя mission system без отдельного contract/proof.
