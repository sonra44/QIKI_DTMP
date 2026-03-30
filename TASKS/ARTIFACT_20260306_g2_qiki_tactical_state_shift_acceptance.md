# ACCEPTANCE: G2-QIKI-005 — tactical state shift hostile follow-up

Статус: PASS/PASS
Дата: 2026-03-06

## Что доказано

Для одного и того же hostile-intent сценария:

`QIKI, атакуй объект UNBT9999`

система теперь различает два тактических состояния:

1. `COMBAT_ENTRY_PROCEDURE_READY`
- hostile context открыт;
- ресурсный контур готов;
- следующий шаг = подготовить первый combat-entry burst.

2. `TACTICAL_STATE_INTERCEPT_ACTIVE`
- `propulsion.rcs` уже показывает активный intercept pulse;
- тот же burst второй раз не подготавливается;
- следующий шаг меняется на `удерживать трек и переоценить ситуацию после завершения импульса`.

## Truth-source

Тактический сдвиг закреплён через текущую телеметрию:
- `propulsion.rcs.active`
- `propulsion.rcs.command_pct`
- `propulsion.rcs.time_left_s`

Новый hidden state не вводился.

## Docker-proof

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  ruff check src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_cockpit.py \
  tools/orion_v_qiki_tactical_state_shift_smoke.py
```

Результат:
- `All checks passed!`

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_cockpit.py
```

Результат:
- green

## Runtime-proof

```bash
bash scripts/prove_orion_v_qiki_tactical_state_shift.sh
```

Фактический результат:

```text
OK: orion_v_qiki_tactical_state_shift_smoke
PREPARED_CODE=COMBAT_ENTRY_PROCEDURE_READY
TACTICAL_CODE=TACTICAL_STATE_INTERCEPT_ACTIVE
TACTICAL_REPLY_RU=QIKI видит, что начальный combat-entry импульс уже переводит аппарат в перехват. Следующий шаг — удерживать трек и переоценить ситуацию после завершения текущего импульса.
```

## Контур A: инженерный

PASS:
- tactical shift опирается на реальную телеметрию `propulsion.rcs`;
- тот же hostile запрос меняет ответ детерминированно;
- Docker и runtime-proof зелёные.

## Контур B: продуктовый

PASS:
- боевое решение теперь меняет тактическое состояние и следующий допустимый ход;
- hostile loop стал ближе к `Encounter 1v1`;
- проект не ушёл в premature weapons stack.
