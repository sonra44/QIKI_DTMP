# TASK: G2 — подготовка первого combat-entry шага

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G2_QIKI_PROTOCOL_ARBITRATION_CANON.md`
- `docs/design/canon/G2_QIKI_HOSTILE_CONTEXT_OPEN_CANON.md`

Уже доказано:
- hostile intent может быть протокольно заблокирован;
- hostile context может открыться по реальной смене мира;
- ORION V умеет показать `blocked -> allowed`.

Пока не доказано:
- какой именно первый шаг получает оператор после `allowed`.

## Цель

Реализовать первый законченный hostile-intent scenario, где:
- команда уже допустима;
- QIKI подготавливает явный combat-entry step;
- step требует явного подтверждения;
- ORION V показывает подготовку, подтверждение и consequence.

## Операторский сценарий

Оператор снова требует:

`QIKI, атакуй объект UNBT9999`

Но теперь мир уже в состоянии:
- station influence снят;
- цель подтверждена как `FOE`.

QIKI должна:
- не просто сказать “можно”;
- подготовить следующий combat-entry step;
- объяснить, почему именно этот шаг допустим сейчас;
- ждать явного подтверждения оператора.

## Scope

### В scope

1. Один hostile-intent scenario после `HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK`.
2. Один prepared combat-entry step.
3. Explicit confirmation path в ORION V.
4. Один runtime-proof.
5. Один acceptance-артефакт.

### Вне scope

1. Полный weapons stack.
2. Полный combat 1v1.
3. Новый mission system.
4. Побочная полировка UI.

## Разделы работ

### Раздел 1: выбрать первый combat-entry step

Цель:
- выбрать один ограниченный и причинный шаг входа в бой.

Проверки:
- это не полный weapons stack;
- это не пустой текстовый совет;
- это можно провести по существующим transport/path.

Тесты:
- unit tests на prepared action/procedure.

### Раздел 2: ORION V visibility

Цель:
- prepared combat-entry должен читаться как следующий шаг, а не как уже исполненная команда.

Проверки:
- виден prepared state;
- виден confirmation requirement;
- consequence до подтверждения не врёт.

Тесты:
- Textual/unit tests на state progression.

### Раздел 3: Runtime proof

Цель:
- доказать hostile-intent path до prepared combat-entry и подтверждения в живом ORION V loop.

Проверки:
- path воспроизводим;
- prepared/confirm/consequence видны в runtime;
- proof детерминирован.

Тесты:
- smoke/proof script.

## Два контура контроля

### Инженерный контроль

- [x] контракт/доки обновлены
- [x] таргетные Docker-тесты зелёные
- [x] runtime-proof зелёный
- [x] prepared combat-entry step детерминирован
- [ ] checkpoint сохранён в память

### Продуктовый контроль

- [x] игрок получает явный следующий боевой шаг
- [x] `allowed` больше не абстрактен
- [x] подтверждение оператора остаётся обязательным
- [x] проект становится ближе к игровому `G2`

## Журнал доказательств

### Петля 0: replan следующего этапа

Изменённые файлы:
- `docs/design/canon/G2_QIKI_COMBAT_ENTRY_PREP_CANON.md`
- `TASKS/TASK_20260306_g2_qiki_combat_entry_preparation.md`

Результат:
- после честного закрытия `G2-QIKI-002` выбран следующий один этап;
- новый шаг не уходит ни в полный weapons stack, ни в mission-layer;
- следующий цикл снова ограничен одним операторским сценарием.

Риски:
- нужно выбрать первый combat-entry step так, чтобы он был и игровым, и технически выполнимым на текущем стеке;
- нельзя подменить step пустой текстовой рекомендацией.

### Петля 1: prepared combat-entry procedure + confirm

Изменённые файлы:
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `config/orion_v/procedures/hostile_rcs_intercept_burst.json`
- `tests/unit/test_qiki_orion_intents_service.py`
- `tests/unit/test_orion_v_qiki_loop.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tools/orion_v_qiki_combat_entry_smoke.py`
- `scripts/prove_orion_v_qiki_combat_entry.sh`

Результат:
- hostile-intent scenario в уже открытом hostile-контексте теперь готовит первый реальный combat-entry step;
- step оформлен как ORION procedure `hostile_rcs_intercept_burst`;
- ORION V показывает prepared state и требует `q confirm`;
- after confirm consequence доходит до `confirmed` по `propulsion.rcs`.

Доказательства:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/q_core_agent/qiki_orion_intents_service.py src/qiki/services/operator_console/orion_v/app.py tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py tests/unit/test_orion_v_cockpit.py tools/orion_v_qiki_combat_entry_smoke.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py tests/unit/test_orion_v_cockpit.py`
- `bash scripts/prove_orion_v_qiki_combat_entry.sh`

Фактический proof:
- `PREPARED_ACTION=1. sim.rcs.fire axis=forward duration_s=2.0 pct=35.0 -> ack sim.rcs.fire`
- `FINAL_HELP=QIKI execution confirmed: процедура hostile_rcs_intercept_burst`
- `RCS_CONFIRMATION=propulsion.rcs command_pct=35.0, time_left_s=2.00`

## Следующее действие

1. Зафиксировать acceptance этого этапа в отдельном артефакте.
2. Синхронизировать внешний canonical board.
3. Сделать replan следующего этапа G2 после первого prepared combat-entry.
