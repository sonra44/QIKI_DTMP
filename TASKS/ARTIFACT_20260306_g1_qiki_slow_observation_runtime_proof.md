# ARTIFACT: G1-QIKI-002 slow observation runtime proof

Статус: pass
Дата: 2026-03-06
Этап: `G1-QIKI-002`

## Цель

Доказать второй procedural scenario этапа:
- QIKI готовит не просто `pause/start`, а сценарий осторожного наблюдения,
- процедура переводит симуляцию в `RUNNING` на скорости `x0.25`,
- ORION V показывает шаг с параметром скорости,
- итог подтверждается живой телеметрией `sim_state.speed=0.25`.

## Что реализовано

1. `ProcedureEngine` расширен поддержкой параметров шага.
2. Добавлена процедура:
   - `config/orion_v/procedures/safe_pause_slow_resume.json`
3. Добавлен новый QIKI intent:
   - `slow observation`
   - `подготовь медленное наблюдение`
4. ORION V теперь показывает procedural step с параметрами:
   - `sim.start speed=0.25 -> ack sim.start`
5. После завершения процедуры `consequence` отражает фактическую скорость выполнения.

## Команды проверки

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/operator_console/orion_v/procedure_engine.py \
  src/qiki/services/operator_console/orion_v/app.py \
  src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  tests/unit/test_orion_v_procedure_engine.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_qiki_loop.py \
  tests/unit/test_orion_v_cockpit.py \
  tools/orion_v_qiki_slow_observation_smoke.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_procedure_engine.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_qiki_loop.py \
  tests/unit/test_orion_v_cockpit.py

bash scripts/prove_orion_v_qiki_slow_observation.sh
```

## Результаты

### Unit

- `ruff check` -> `All checks passed!`
- `pytest -q ...` -> green

### Live runtime proof

```text
OK: orion_v_qiki_slow_observation_smoke
PLAN_LINES=['1. sim.pause -> ack sim.pause', '2. sim.start speed=0.25 -> ack sim.start']
PROCEDURE_STATUS=ok
SIM_STATE={'running': True, 'paused': False, 'speed': 0.25, 'fsm_state': 'RUNNING'}
FINAL_QIKI_STATUS=confirmed
```

## Что этим доказано

1. `G1-QIKI-002` больше не ограничен одним procedural scenario.
2. Этап теперь честно включает time-control path с изменением скорости, а не только `pause/start -> x1.0`.
3. ORION V показывает параметризованный procedural step и подтверждает его consequence по живой телеметрии.
