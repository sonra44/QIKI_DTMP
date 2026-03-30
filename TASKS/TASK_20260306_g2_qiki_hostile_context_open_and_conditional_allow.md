# TASK: G2 — hostile context open и условный допуск

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G2_QIKI_PROTOCOL_ARBITRATION_CANON.md`

Первый hostile-intent loop уже доказан:
- station influence может заблокировать атаку;
- QIKI умеет жёстко арбитрировать;
- ORION V показывает protocol block;
- 4-й повтор становится короче.

Следующий продуктовый шаг должен перевести проект в следующую фазу `G2`:
- та же hostile-intent команда должна менять результат после смены контекста мира;
- QIKI должна не просто отказывать, а затем условно открывать путь вперёд.

## Цель

Реализовать первый законченный hostile-intent scenario, где:
- команда сначала `blocked`;
- затем после смены контекста становится `allowed`;
- ORION V показывает, что именно изменилось;
- QIKI готовит следующий допустимый шаг.

## Операторский сценарий

Оператор видит цель `UNBT9999` и требует:

`QIKI, атакуй объект UNBT9999`

В первом состоянии мира действует station influence, и QIKI блокирует действие.

Во втором состоянии мира hostile context уже открыт, station influence больше не активен, и QIKI меняет ответ с `blocked` на `allowed`.

ORION обязан показать:
- что решение QIKI изменилось не случайно;
- какой reason code был раньше;
- какой reason code стал теперь;
- какой следующий шаг допустим.

## Scope

### В scope

1. Один hostile-intent scenario с переходом `blocked -> allowed`.
2. Один truth-source для открытия hostile context.
3. ORION V visibility нового `allowed` state.
4. Один runtime-proof.
5. Один acceptance-артефакт.

### Вне scope

1. Полный weapons stack.
2. Полный combat 1v1.
3. Новый mission system.
4. Побочная полировка UI.

## Разделы работ

### Раздел 1: Truth-source hostile context open

Цель:
- выбрать детерминированный источник, который открывает hostile context.

Проверки:
- нет второго скрытого источника истины;
- новое условие не ломает уже существующий station block.

Тесты:
- unit tests на переход `blocked -> allowed`.

### Раздел 2: ORION V visibility

Цель:
- новый `allowed` должен быть так же читаем, как прошлый `blocked`.

Проверки:
- видно, что именно изменилось;
- видно, какой следующий шаг допустим;
- нет ощущения, что QIKI “просто передумала”.

Тесты:
- Textual/unit tests на state progression.

### Раздел 3: Runtime proof

Цель:
- доказать оба состояния в живом ORION V loop.

Проверки:
- hostile-intent path воспроизводим;
- transition `blocked -> allowed` виден в runtime;
- proof детерминирован.

Тесты:
- smoke/proof script.

## Два контура контроля

### Инженерный контроль

- [x] контракт/доки обновлены
- [x] таргетные Docker-тесты зелёные
- [x] runtime-proof зелёный
- [x] hostile-context truth-source детерминирован
- [ ] checkpoint сохранён в память

### Продуктовый контроль

- [x] игрок видит смену контекста, а не “каприз QIKI”
- [x] hostile gameplay становится динамическим
- [x] есть следующий допустимый шаг после `allowed`
- [x] проект становится ближе к `G2` из `LOG.MD`

## Журнал доказательств

### Петля 0: replan следующего этапа

Изменённые файлы:
- `docs/design/canon/G2_QIKI_HOSTILE_CONTEXT_OPEN_CANON.md`
- `TASKS/TASK_20260306_g2_qiki_hostile_context_open_and_conditional_allow.md`

Результат:
- после закрытия `G2-QIKI-001` выбран следующий один этап;
- новая цель не уходит ни в полный бой, ни в mission-layer;
- следующий цикл снова ограничен одним операторским сценарием.

Риски:
- hostile-context truth-source пока ещё не выбран окончательно;
- нужно не повторить `G2-QIKI-001`, а доказать именно смену решения.

### Петля 1: blocked -> allowed через `iff=FOE`

Изменённые файлы:
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `tests/unit/test_qiki_orion_intents_service.py`
- `tools/orion_v_qiki_hostile_intent_smoke.py`
- `docs/design/canon/G2_QIKI_HOSTILE_CONTEXT_OPEN_CANON.md`

Результат:
- hostile-context truth-source закреплён без нового hidden state: `world_snapshot["radar_tracks"][target].iff == FOE`;
- station influence по-прежнему имеет высший приоритет и удерживает `STATION_COMBAT_PROTOCOL_BLOCK`;
- при отсутствии station influence, но без `FOE`, команда остаётся `deferred/protocol` с `HOSTILE_CONTEXT_NOT_OPEN`;
- при `FOE` и отсутствии station influence команда становится `allowed/protocol` с `HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK`;
- ORION V runtime-proof показывает оба состояния мира и смену причинности для одной и той же команды `QIKI, атакуй объект UNBT9999`.

Доказательства:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/q_core_agent/qiki_orion_intents_service.py tests/unit/test_qiki_orion_intents_service.py tools/orion_v_qiki_hostile_intent_smoke.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py`
- `bash scripts/prove_orion_v_qiki_hostile_intent.sh`

Фактический proof:
- `BLOCKED_CODE=STATION_COMBAT_PROTOCOL_BLOCK`
- `ALLOWED_CODE=HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK`
- `ALLOWED_HELP=QIKI allowed: Цель UNBT9999 отслеживается как FOE...`

## Следующее действие

1. Зафиксировать acceptance этого этапа в отдельном артефакте.
2. Синхронизировать внешний canonical board.
3. Сделать replan следующего этапа G2 без ухода в weapons stack.
