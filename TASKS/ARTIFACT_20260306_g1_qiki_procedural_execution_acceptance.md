# ARTIFACT: G1-QIKI-002 acceptance audit

Статус: pass
Дата: 2026-03-06
Этап: `G1-QIKI-002`

## Цель

Честно проверить, можно ли закрывать этап `Procedural Execution + Time Control`, или после четырёх зелёных петель остаётся реальный незакрытый пункт.

## Что проверялось

### Канон и DoD

Сверка велась против:
- `docs/design/canon/G1_QIKI_PROCEDURAL_EXECUTION_CANON.md`
- `TASKS/TASK_20260305_g1_qiki_procedural_execution_and_time_control.md`

Обязательные пункты этапа:
1. один многошаговый QIKI-сценарий реализован как процедура;
2. ORION V показывает `Plan Preview` и `Execution State`;
3. `pause/start/speed` участвуют в доказуемом операторском цикле;
4. есть Docker-proof и runtime-proof;
5. оба контура контроля исполнения можно зафиксировать как `PASS`.

### Повторная инженерная проверка

Запущено:

```bash
docker compose -f docker-compose.phase1.yml ps

docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_procedure_engine.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_qiki_loop.py \
  tests/unit/test_orion_v_cockpit.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/operator_console/orion_v/app.py \
  tests/unit/test_orion_v_qiki_loop.py

bash scripts/prove_orion_v_qiki_safe_observation.sh
bash scripts/prove_orion_v_qiki_procedure_surface.sh
bash scripts/prove_orion_v_qiki_slow_observation.sh
```

## Что было найдено во время аудита

Аудит нашёл не только формальный статус, но и реальный дефект:

- `slow observation` live proof падал по таймауту ожидания `sim_state.speed=0.25`;
- причина: ORION мог перевести procedural consequence в `confirmed` раньше, чем живая телеметрия догоняла ожидаемый reduced-speed effect;
- исправление внесено в `src/qiki/services/operator_console/orion_v/app.py`:
  - procedural path теперь ждёт ожидаемый телеметрический эффект процедуры;
  - `confirmed` выставляется только после наблюдаемого `sim_state`;
  - если процедура завершилась, но телеметрия ещё не подтвердила эффект, состояние остаётся `pending`, а не ложно `confirmed`.

Дополнительно добавлен unit-тест:
- `tests/unit/test_orion_v_qiki_loop.py::test_execute_qiki_pending_slow_procedure_waits_for_telemetry_effect`

## Результаты

### Unit / lint

- `pytest -q ...` -> зелёный (`59 passed`)
- `ruff check ...` -> `All checks passed!`

### Live runtime proofs

`safe observation`

```text
OK: orion_v_qiki_safe_observation_smoke
PLAN_LINES=['1. sim.pause -> ack sim.pause', '2. sim.start -> ack sim.start']
PROCEDURE_STATUS=ok
SIM_STATE={'running': True, 'paused': False, 'speed': 1.0, 'fsm_state': 'RUNNING'}
FINAL_QIKI_STATUS=confirmed
```

`procedure surface`

```text
OK: orion_v_qiki_procedure_surface_smoke
PROCEDURE_BUTTON=Процедуры/Procedures OK -> F6
FINAL_LEVEL=f6
AUDIT_FILTER=procedures
```

`slow observation`

```text
OK: orion_v_qiki_slow_observation_smoke
PLAN_LINES=['1. sim.pause -> ack sim.pause', '2. sim.start speed=0.25 -> ack sim.start']
PROCEDURE_STATUS=ok
SIM_STATE={'running': True, 'paused': False, 'speed': 0.25, 'fsm_state': 'RUNNING'}
FINAL_QIKI_STATUS=confirmed
```

## Сверка покрытия этапа

- [x] QIKI готовит многошаговую процедуру
- [x] ORION V показывает `Plan Preview`
- [x] ORION V показывает `Execution State`
- [x] `F1` показывает отдельную секцию `Процедура/Procedure`
- [x] `F1 -> F6` даёт прямой вход в procedural audit trail
- [x] `pause/start` участвуют в реальном procedural path
- [x] reduced-speed path (`speed=0.25`) доказан живой телеметрией
- [x] `confirmed` теперь зависит от наблюдаемого телеметрического эффекта, а не только от статуса procedure engine

## Два контура контроля

### Инженерный

PASS

Причины:
- используется существующий `ProcedureEngine`;
- используется существующий `qiki.commands.control` / `qiki.responses.control`;
- новый transport не введён;
- unit/lint/live-proof зелёные;
- найденный дефект подтверждения устранён.

### Продуктовый

PASS

Причины:
- QIKI теперь не только объясняет, но и разворачивает намерение в исполняемый сценарий;
- оператор видит план, ход исполнения и изменение времени;
- `pause/start/speed` стали частью игрового цикла, а не скрытой служебной функцией;
- проект стал ближе к `LOG.MD`: QIKI-centic execution во времени реально наблюдаемо.

## Вывод

Этап `G1-QIKI-002` можно закрывать честно.

После устранения дефекта подтверждения reduced-speed procedure осталось без реальных незакрытых пунктов в рамках текущего канона этапа.

## Следующий правильный шаг

Не добавлять третий procedural scenario по инерции.

Следующее допустимое действие:
- короткий replan следующего продуктового этапа поверх уже закрытых `G1-QIKI-001` и `G1-QIKI-002`, с опорой на `LOG.MD`.
