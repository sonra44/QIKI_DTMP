# ARTIFACT: G2 hostile context open acceptance

Статус: PASS
Дата: 2026-03-06
Этап: `G2-QIKI-002`

## Что доказано

Для одного и того же hostile-intent запроса

`QIKI, атакуй объект UNBT9999`

система теперь честно проходит два состояния мира:

1. `blocked/protocol`
   - `reason_code=STATION_COMBAT_PROTOCOL_BLOCK`
   - station influence активен внутри `35 000 м`

2. `allowed/protocol`
   - `reason_code=HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK`
   - station influence снят
   - target track классифицирован как `iff=FOE`

## Источник истины

Открытие hostile-контекста не требует нового скрытого state-store.

Канонический truth-source:
- `world_snapshot["radar_tracks"]`
- target track по designator `UNBT9999`
- контекст считается открытым только при `target_track.iff == FOE`

При этом station influence остаётся приоритетным блоком:
- если станция в радиусе `35 000 м`, hostile intent остаётся `blocked`, даже если цель уже известна.

## Что увидит оператор

ORION V показывает:
- прежний protocol block;
- новый `allowed` state;
- различие reason code;
- различие help-strip формулировок;
- следующий допустимый шаг через `allowed_when`.

Это устраняет ощущение, что QIKI “просто передумала”.

## Проверки

### Ruff

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check \
  src/qiki/services/q_core_agent/qiki_orion_intents_service.py \
  tests/unit/test_qiki_orion_intents_service.py \
  tools/orion_v_qiki_hostile_intent_smoke.py
```

Результат:
- `All checks passed!`

### Docker unit

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_qiki_orion_intents_service.py \
  tests/unit/test_orion_v_qiki_loop.py
```

Результат:
- `40 passed`

### Runtime proof

```bash
bash scripts/prove_orion_v_qiki_hostile_intent.sh
```

Фактический результат:

```text
OK: orion_v_qiki_hostile_intent_smoke
BLOCKED_HELP=QIKI blocked: Влияние станции остаётся активным на дистанции 12000 м; инициирование боя заблокировано текущим протокольным контекстом. [STATION_COMBAT_PROTOCOL_BLOCK]
BLOCKED_REPLY_RU=QIKI не начнёт бой против UNBT9999, пока влияние станции активно в пределах 35000 м.
ALLOWED_HELP=QIKI allowed: Цель UNBT9999 отслеживается как FOE, и активной station-блокировки нет, поэтому hostile-контекст открыт для условного входа в бой. [HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK]
ALLOWED_REPLY_RU=QIKI не видит активной station-протокольной блокировки, а цель теперь классифицирована как FOE, поэтому hostile-контекст открыт для условного входа в бой.
BLOCKED_CODE=STATION_COMBAT_PROTOCOL_BLOCK
ALLOWED_CODE=HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK
```

## Два контура контроля

### Инженерный

- PASS: truth-source детерминирован и не требует нового hidden state
- PASS: station block не сломан
- PASS: reason code перехода детерминирован
- PASS: Docker tests и runtime-proof зелёные

### Продуктовый

- PASS: один и тот же запрос меняет решение из-за смены контекста, а не из-за “каприза QIKI”
- PASS: hostile gameplay стал динамическим
- PASS: после `allowed` у оператора есть явный следующий шаг через `allowed_when`

