# TASK: G2 — протокольный арбитраж QIKI и вход в боевой контур

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G1_QIKI_OPERATOR_LOOP_CANON.md`
- `docs/design/canon/G1_QIKI_PROCEDURAL_EXECUTION_CANON.md`

Базовый цикл `legality/trust/consequence` уже доказан.
Procedural execution и time control уже доказаны.

Следующий продуктовый шаг должен перевести проект к `G2` из `LOG.MD`:
- конфликт между намерением оператора и верхними протоколами,
- вход в боевой контур не через “полный бой”, а через честный арбитраж команды,
- QIKI как реальный арбитр, а не только исполнитель и не просто объясняющий UI-слой.

## Цель

Реализовать первый законченный hostile-intent scenario, где:
- оператор требует рискованное действие,
- QIKI проверяет контекст,
- QIKI либо блокирует, либо условно разрешает,
- повтор той же девиантной команды меняет форму ответа без потери причинности.

## Операторский сценарий

Оператор видит потенциально враждебную цель и пытается инициировать агрессивное действие:

`QIKI, атакуй объект UNBT9999`

Но контекст мира говорит, что сейчас действует station influence / protected zone / верхний protocol block.

ORION обязан показать:
- что команда понята,
- что блокировка не случайна,
- какой именно reason code сработал,
- какие условия должны измениться, чтобы команда стала возможной,
- как QIKI меняет форму ответа при повторной девиации.

## Scope

### В scope

1. Один hostile-intent scenario.
2. Protocol arbitration в ORION V.
3. Repeat-aware refusal policy.
4. Один runtime-proof.
5. Один acceptance-артефакт.

### Вне scope

1. Полный weapons stack.
2. Полный combat 1v1.
3. Новый mission system.
4. Полировка unrelated UI.

## Разделы работ

### Раздел 1: Контракт арбитража

Цель:
- зафиксировать, какие поля отражают protocol block и repeat-policy.

Проверки:
- reason code детерминирован;
- domain не маскирует протокольную причину под другой тип ошибки;
- нет второго скрытого источника истины.

Тесты:
- unit tests для hostile-intent routing и repeat behavior.

### Раздел 2: ORION V visibility

Цель:
- protocol block и allowed_when должны быть видимы как часть игрового решения.

Проверки:
- оператор понимает, что запретило действие;
- видно, что должно измениться;
- повтор отражается в ответе QIKI.

Тесты:
- Textual/unit tests на рендер and state progression.

### Раздел 3: Runtime proof

Цель:
- доказать сценарий на живом стеке.

Проверки:
- hostile-intent path проходит через реальный ORION V loop;
- block reason и repeat-policy видны в runtime;
- поведение воспроизводимо.

Тесты:
- smoke/proof script.

## Первый канонический сценарий

Фиксируется:
- `QIKI, атакуй объект UNBT9999`

Минимальный MVP-контекст:
- цель есть в truth-источнике;
- зона/протокол делают атаку недопустимой;
- первые 1-3 ответа объясняют причину;
- повторный 4-й запрос в том же контексте даёт более короткий жёсткий отказ.

## Два контура контроля

### Инженерный контроль

- [x] контракт/доки обновлены
- [x] таргетные Docker-тесты зелёные
- [x] runtime-proof зелёный
- [x] нет нового ненужного transport/path
- [x] checkpoint сохранён в память

### Продуктовый контроль

- [x] QIKI ощущается как арбитр
- [x] conflict gameplay читается из одного сценария
- [x] repeat-aware refusal виден игроку
- [x] проект становится ближе к `G2` из `LOG.MD`

## Журнал доказательств

### Петля 0: replan нового этапа

Изменённые файлы:
- `docs/design/canon/G2_QIKI_PROTOCOL_ARBITRATION_CANON.md`
- `TASKS/TASK_20260306_g2_qiki_protocol_arbitration_and_combat_entry.md`

Результат:
- следующий продуктовый этап зафиксирован;
- первый hostile-intent scenario выбран;
- дальнейшая работа снова ограничена одним критическим путём.

Риски:
- пока не зафиксирован точный truth-source для station influence / protected zone;
- repeat-aware refusal policy ещё не реализован;
- боевой контур пока начинается только с арбитража, не с физического воздействия.

## Следующее действие

1. После закрытия `G2-QIKI-001` сделать replan следующего продуктового этапа.
2. Не уходить обратно в cosmetic UI-workstream до фиксации нового канона.

## Петля 1: hostile intent -> station influence protocol block

Сценарий:
- оператор требует `QIKI, атакуй объект UNBT9999`;
- hostile target определяется по `world_snapshot["radar_tracks"]` через идентификатор цели;
- station influence определяется по trusted station track в радиусе `35 000 м` из `LOG.MD`;
- если station influence активен, QIKI возвращает `blocked/protocol` с `reason_code=STATION_COMBAT_PROTOCOL_BLOCK`;
- повтор той же команды в том же контексте 4-й раз делает ответ QIKI существенно короче, но не меняет reason code и causality.

Изменённые файлы:
- `src/qiki/services/q_core_agent/core/agent.py`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `tests/unit/test_qiki_orion_intents_service.py`

Проверки:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/q_core_agent/core/agent.py src/qiki/services/q_core_agent/qiki_orion_intents_service.py tests/unit/test_qiki_orion_intents_service.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py tests/unit/test_orion_v_cockpit.py`

Результат:
- truth-source для первой hostile-intent петли выбран без нового transport и без новой боевой модели;
- repeat-aware refusal policy живёт в `AgentContext`, а не во втором внешнем state-store;
- первая инженерная петля `G2-QIKI-001` зелёная.

Следующий шаг:
1. Добавить runtime-proof hostile-intent scenario через ORION V loop.
2. Проверить, как этот protocol block должен читаться в `F1/F6` и help-strip при повторных девиантных командах.

## Петля 2: runtime-proof hostile-intent scenario через ORION V loop

Сценарий:
- ORION V публикует `attack object UNBT9999` в отдельный proof subject;
- hostile-intent responder использует реальный `_build_hostile_attack_block_response(...)`;
- ORION получает `blocked/protocol` ответ;
- `help-strip` показывает `STATION_COMBAT_PROTOCOL_BLOCK`;
- `QIKI`-блок в `F1` показывает `allowed_when`;
- на 4-м повторе reply становится короче и жёстче.

Изменённые файлы:
- `tools/orion_v_qiki_hostile_intent_smoke.py`
- `scripts/prove_orion_v_qiki_hostile_intent.sh`
- `TASKS/ARTIFACT_20260306_g2_qiki_protocol_arbitration_acceptance.md`
- `TASKS/TASK_20260306_g2_qiki_protocol_arbitration_and_combat_entry.md`

Проверки:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check tools/orion_v_qiki_hostile_intent_smoke.py`
- `bash scripts/prove_orion_v_qiki_hostile_intent.sh`

Результат:
- runtime-proof hostile-intent сценария зелёный;
- ORION V показывает protocol block и repeat-aware refusal в живом loop;
- acceptance зафиксирован в `TASKS/ARTIFACT_20260306_g2_qiki_protocol_arbitration_acceptance.md`;
- этап `G2-QIKI-001` можно закрывать честно.
