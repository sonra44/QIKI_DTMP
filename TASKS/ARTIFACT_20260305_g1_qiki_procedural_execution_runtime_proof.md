# ARTIFACT: G1-QIKI-002 procedural execution runtime proof

Статус: pass
Дата: 2026-03-05
Этап: `G1-QIKI-002`

## Цель

Доказать первую рабочую петлю нового этапа:
- QIKI подготавливает не атомарную команду, а процедуру,
- ORION V показывает план,
- оператор подтверждает исполнение,
- процедура реально проходит через существующие `sim.pause/start`,
- итог подтверждается `procedure status` и `sim_state`.

## Что реализовано

1. В контракт `qiki.responses.qiki` добавлен тип действия:
   - `ORION_PROCEDURE`
2. В `qiki_orion_intents_service` добавлен сценарий:
   - `safe observation`
   - `подготовь безопасную стабилизацию наблюдения`
3. QIKI возвращает подготовленную процедуру:
   - `safe_pause_resume`
4. ORION V:
   - извлекает procedural pending-action,
   - показывает plan preview,
   - показывает execution-state,
   - исполняет процедуру по `q confirm`.

## Команды проверки

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/shared/models/qiki_chat.py \
  src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  src/qiki/services/operator_console/orion_v/app.py \
  src/qiki/services/operator_console/orion_v/screens/cockpit.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_qiki_loop.py \
  tests/unit/test_orion_v_cockpit.py \
  tools/orion_v_qiki_safe_observation_smoke.py

docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_qiki_loop.py \
  tests/unit/test_orion_v_cockpit.py

bash scripts/prove_orion_v_qiki_safe_observation.sh
```

## Результаты

### Unit/UI

- `ruff check` -> `All checks passed!`
- `pytest -q ...` -> `50 passed`

### Live runtime proof

```text
OK: orion_v_qiki_safe_observation_smoke
PLAN_LINES=['1. sim.pause -> ack sim.pause', '2. sim.start -> ack sim.start']
PROCEDURE_STATUS=ok
SIM_STATE={'running': True, 'paused': False, 'speed': 1.0, 'fsm_state': 'RUNNING'}
FINAL_QIKI_STATUS=confirmed
```

## Что этим доказано

1. Новый этап не остался на уровне планирования.
2. QIKI уже умеет подготовить procedural action без нового transport.
3. ORION V уже умеет:
   - показать план,
   - подтвердить процедуру,
   - дождаться завершения,
   - перевести consequence в `confirmed`.
4. `sim.pause/start` уже реально участвуют в игровом цикле нового этапа.

## Остаточный риск

- Пока реализован только первый безопасный procedural scenario.
- Следующая петля должна усилить не инфраструктуру, а операторскую читаемость plan/execution surface в обычном живом использовании.
