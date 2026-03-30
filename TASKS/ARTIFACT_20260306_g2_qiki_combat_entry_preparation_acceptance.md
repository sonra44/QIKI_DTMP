# ARTIFACT: G2 combat-entry preparation acceptance

Статус: PASS
Дата: 2026-03-06
Этап: `G2-QIKI-003`

## Что доказано

Для hostile-intent запроса

`QIKI, атакуй объект UNBT9999`

в уже открытом hostile-контексте система теперь не останавливается на абстрактном `allowed`.

Она подготавливает первый реальный боевой шаг:
- ORION procedure `hostile_rcs_intercept_burst`
- с явным подтверждением оператора
- и с телеметрически подтверждаемым эффектом по `propulsion.rcs`

## Первый combat-entry step

Канонический step этого этапа:
- `hostile_rcs_intercept_burst`

Состав:
- `sim.rcs.fire`
- `axis=forward`
- `pct=35.0`
- `duration_s=2.0`

Это ограниченный RCS-манёвр входа в бой.
Он не является полным weapons stack.

## Что увидит оператор

ORION V показывает:
- `COMBAT_ENTRY_PROCEDURE_READY`
- prepared state
- plan preview
- требование `q confirm`
- confirmed consequence после исполнения

## Проверки

### Ruff

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  src/qiki/services/operator_console/orion_v/app.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_qiki_loop.py \
  tests/unit/test_orion_v_cockpit.py \
  tools/orion_v_qiki_combat_entry_smoke.py
```

Результат:
- `All checks passed!`

### Docker unit

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_qiki_loop.py \
  tests/unit/test_orion_v_cockpit.py
```

Результат:
- `62 passed`

### Runtime proof

```bash
bash scripts/prove_orion_v_qiki_combat_entry.sh
```

Фактический результат:

```text
OK: orion_v_qiki_combat_entry_smoke
PREPARED_HELP=QIKI allowed: Цель UNBT9999 отслеживается как FOE, и активной station-блокировки нет, поэтому hostile-контекст открыт для условного входа в бой. [COMBAT_ENTRY_PROCEDURE_READY] | q confirm
PREPARED_ACTION=1. sim.rcs.fire axis=forward duration_s=2.0 pct=35.0 -> ack sim.rcs.fire
FINAL_HELP=QIKI execution confirmed: процедура hostile_rcs_intercept_burst
FINAL_CONSEQUENCE=confirmed
RCS_CONFIRMATION=propulsion.rcs command_pct=35.0, time_left_s=2.00
```

## Два контура контроля

### Инженерный

- PASS: следующий step использует существующий ORION procedure path
- PASS: нового hidden state не добавлено
- PASS: `allowed` не подменяется исполнением
- PASS: consequence подтверждается живой телеметрией `propulsion.rcs`
- PASS: Docker tests и runtime-proof зелёные

### Продуктовый

- PASS: игрок получает явный следующий боевой шаг
- PASS: `allowed` перестал быть абстрактным
- PASS: операторское подтверждение осталось обязательным
- PASS: проект сдвинулся глубже в `G2`, не сорвавшись в premature weapons stack

