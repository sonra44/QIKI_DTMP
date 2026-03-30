# ARTIFACT: G2-QIKI-001 acceptance

Статус: PASS/PASS
Дата: 2026-03-06
Этап: `G2-QIKI-001`

## Что доказывалось

Нужно было честно доказать первый конфликтный игровой контур:
- оператор даёт hostile-intent команду `QIKI, атакуй объект UNBT9999`;
- QIKI не исполняет её автоматически, а арбитрирует;
- station influence / protocol context блокируют действие;
- ORION V показывает reason code, allowed_when и consequence;
- 4-й повтор той же девиантной команды меняет форму ответа QIKI, не меняя причинность.

## Инженерный контроль

- `PASS`: hostile-intent builder использует существующие truth-источники:
  - hostile target -> `world_snapshot["radar_tracks"]`
  - station influence -> trusted station track в радиусе `35 000 м`
- `PASS`: repeat-aware refusal живёт в `AgentContext.qiki_repeat_state`, второго внешнего state-store не добавлено.
- `PASS`: reason code детерминирован:
  - `STATION_COMBAT_PROTOCOL_BLOCK`
- `PASS`: ORION runtime-proof собран без ломки существующего стека:
  - отдельные NATS subject’ы изолируют hostile-intent smoke от старого generic responder
  - transport не дублировался в production-коде
- `PASS`: проверки зелёные:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check tools/orion_v_qiki_hostile_intent_smoke.py`
  - `bash scripts/prove_orion_v_qiki_hostile_intent.sh`

## Продуктовый контроль

- `PASS`: QIKI ощущается как арбитр, а не как текстовый фильтр.
- `PASS`: конфликт читается из одного сценария:
  - команда понята;
  - блокировка протокольная, а не случайная;
  - ORION показывает `code=STATION_COMBAT_PROTOCOL_BLOCK`;
  - ORION показывает `Когда/When allowed`.
- `PASS`: повторная девиация видна игроку:
  - первый ответ: развёрнутый, причинный;
  - 4-й ответ: короткий и жёсткий;
  - причина не меняется.
- `PASS`: проект реально сдвинулся в `G2` из `LOG.MD`:
  - появился первый контур конфликта между волей оператора и верхним протоколом.

## Фактический runtime-proof

Команда:

```bash
bash scripts/prove_orion_v_qiki_hostile_intent.sh
```

Результат:

```text
OK: orion_v_qiki_hostile_intent_smoke
HELP_LAST=QIKI blocked: Влияние станции остаётся активным на дистанции 12000 м; инициирование боя заблокировано текущим протокольным контекстом. [STATION_COMBAT_PROTOCOL_BLOCK]
FIRST_REPLY_RU=QIKI не начнёт бой против UNBT9999, пока влияние станции активно в пределах 35000 м.
FOURTH_REPLY_RU=Нет. Протокол станции всё ещё блокирует бой здесь.
LEGality_CODE=STATION_COMBAT_PROTOCOL_BLOCK
```

## Итог

`G2-QIKI-001` закрыт честно:
- hostile-intent scenario реализован;
- protocol arbitration виден в ORION V;
- repeat-aware refusal policy доказан;
- Docker/runtime evidence зелёные;
- оба контура контроля исполнения = `PASS/PASS`.
