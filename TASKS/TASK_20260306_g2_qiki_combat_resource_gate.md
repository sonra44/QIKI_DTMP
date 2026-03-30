# TASK: G2 — ресурсный боевой гейт и условное продолжение hostile-входа

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Контекст

Эта задача начинается после честного закрытия:
- `docs/design/canon/G2_QIKI_COMBAT_ENTRY_PREP_CANON.md`

Уже доказано:
- hostile intent может быть протокольно заблокирован;
- hostile context может открыться;
- hostile path может подготовить первый ограниченный combat-entry step;
- ORION V умеет доводить prepared combat-entry до `confirmed`.

Пока не доказано:
- как именно ресурсный контур ограничивает боевое продолжение.

## Цель

Реализовать первый законченный hostile-resource scenario, где:
- hostile context уже открыт;
- combat-entry path существует;
- QIKI проверяет ресурсную готовность hostile continuation;
- ORION V показывает причину, следующий шаг и не врёт о боевой готовности.

## Операторский сценарий

Оператор снова требует:

`QIKI, атакуй объект UNBT9999`

Но теперь система дополнительно смотрит:
- `propulsion.rcs`
- `thermal`

QIKI должна:
- не просто сказать “можно/нельзя”;
- объяснить, какой именно ресурсный контур мешает hostile-продолжению;
- при готовом ресурсе оставить путь к уже существующему prepared combat-entry step.

## Scope

### В scope

1. Один hostile-intent scenario после открытого hostile-контекста.
2. Один детерминированный resource truth-source.
3. Один runtime-proof.
4. Один acceptance-артефакт.

### Вне scope

1. Полный weapons stack.
2. Повреждения как отдельная физическая модель.
3. Новый mission system.
4. Побочный UI-polish.

## Разделы работ

### Раздел 1: выбрать resource truth-source

Цель:
- выбрать один уже существующий контур, который реально может ограничивать hostile continuation.

Проверки:
- truth-source уже есть в текущей телеметрии;
- не вводится новый hidden state;
- операторская причинность читаема.

Тесты:
- unit tests на hostile resource gate.

### Раздел 2: ORION V visibility

Цель:
- ORION V должен ясно показывать resource-причину и следующий шаг.

Проверки:
- `resource` виден в legality/reason;
- next step не размазан по тексту;
- consequence не врёт.

Тесты:
- Textual/unit tests на hostile resource state.

### Раздел 3: Runtime proof

Цель:
- доказать hostile resource gate через живой ORION V loop.

Проверки:
- path воспроизводим;
- block/defer или allow видны в runtime;
- proof детерминирован.

Тесты:
- smoke/proof script.

## Два контура контроля

### Инженерный контроль

- [x] контракт/доки обновлены
- [x] таргетные Docker-тесты зелёные
- [x] runtime-proof зелёный
- [x] resource truth-source детерминирован
- [ ] checkpoint сохранён в память

### Продуктовый контроль

- [x] hostile continuation зависит от ресурса, а не только от протокола
- [x] оператор видит причину и следующий шаг
- [x] проект становится ближе к `Encounter 1v1`

## Журнал доказательств

### Петля 0: replan следующего этапа

Изменённые файлы:
- `docs/design/canon/G2_QIKI_COMBAT_RESOURCE_GATE_CANON.md`
- `TASKS/TASK_20260306_g2_qiki_combat_resource_gate.md`

Результат:
- после честного закрытия `G2-QIKI-003` выбран следующий один этап;
- новый шаг не уходит ни в weapons stack, ни в mission-layer;
- следующим обязательным конфликтным контуром признан resource-gate hostile continuation.

Риски:
- нужно выбрать truth-source, который уже реально живёт в текущей телеметрии;
- нельзя превратить этап в бумажную “resource-story” без runtime-proof.

### Петля 1: hostile resource gate по RCS telemetry

Изменённые файлы:
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `tests/unit/test_qiki_orion_intents_service.py`
- `tests/unit/test_orion_v_cockpit.py`
- `tools/orion_v_qiki_hostile_resource_gate_smoke.py`
- `scripts/prove_orion_v_qiki_hostile_resource_gate.sh`

Результат:
- hostile-intent path теперь дополнительно проверяет ресурсную готовность combat-entry;
- если `propulsion.rcs` недоступен, path уходит в `deferred/resource`;
- если `propellant_kg` ниже минимума, path уходит в `blocked/resource`;
- при готовом ресурсе path возвращается к `COMBAT_ENTRY_PROCEDURE_READY`.

Доказательства:
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check src/qiki/services/q_core_agent/qiki_orion_intents_service.py tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_cockpit.py tools/orion_v_qiki_hostile_resource_gate_smoke.py`
- `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_cockpit.py`
- `bash scripts/prove_orion_v_qiki_hostile_resource_gate.sh`

Фактический proof:
- `RESOURCE_BLOCK_HELP=QIKI blocked: ... [COMBAT_ENTRY_RCS_RESOURCE_LOW]`
- `ALLOWED_HELP=QIKI allowed: ... [COMBAT_ENTRY_PROCEDURE_READY] | q confirm`
- `BLOCKED_CODE=COMBAT_ENTRY_RCS_RESOURCE_LOW`
- `ALLOWED_CODE=COMBAT_ENTRY_PROCEDURE_READY`

## Следующее действие

1. Зафиксировать acceptance этого этапа в отдельном артефакте.
2. Синхронизировать внешний canonical board и bootstrap.
3. Сделать replan следующего G2-этапа после resource-gate hostile continuation.
