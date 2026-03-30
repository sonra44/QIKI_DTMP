# Канон G2: открытие hostile-контекста и условный допуск

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Назначение

Этот этап начинается после честного закрытия:
- `G2-QIKI-001` — первый протокольный block hostile-intent команды

Первый конфликтный контур уже доказан:
- оператор хочет атаковать;
- station influence / верхний protocol block запрещают действие;
- QIKI арбитрирует и может ужесточать форму отказа при повторе.

Следующий шаг должен доказать не просто ещё один отказ, а **смену контекста**:
- в одном состоянии мира команда запрещена;
- после изменения контекста мира она становится условно допустимой;
- QIKI не ломает причинность и не “передумывает”, а честно меняет решение из-за новых условий.

## Почему именно этот этап теперь главный

Из `LOG.MD` уже зафиксировано:
- QIKI объясняет невозможность, если условия не выполнены;
- station influence блокирует hostile action;
- после смены условий контекст может открыться;
- бой должен рождаться из честного арбитража, а не из внезапного weapons-stack.

После `G2-QIKI-001` уже доказано:
- QIKI умеет жёстко блокировать hostile intent;
- ORION V умеет показывать protocol block;
- repeat-aware refusal работает.

Но пока не доказано следующее обязательное отличие:
- **та же команда** должна перейти из `blocked` в `allowed`, если мир реально изменился.

Без этого проект умеет запрещать, но ещё не умеет показывать игроку, как протоколы **открывают путь** к следующему действию.

## Имя этапа

`G2-QIKI-002: Hostile Context Open + Conditional Allow`

## Цель

Сделать первый законченный контур, где:
- hostile-intent команда сначала блокируется;
- затем после смены игрового контекста становится условно допустимой;
- ORION V показывает, почему теперь можно;
- QIKI подготавливает следующий безопасный операторский шаг без полного weapons-stack.

## Продуктовая истина этапа

1. Один и тот же hostile intent не должен быть вечно заблокирован.
2. Протоколы должны быть контекстными, а не “магическим нет”.
3. Игрок должен видеть:
   - почему раньше было нельзя;
   - что изменилось;
   - почему теперь стало можно;
   - какой следующий шаг QIKI считает допустимым.
4. Conditional allow не равен “автоматическое оружие”.
5. Вход в боевой контур по-прежнему начинается через арбитраж и подготовку, а не через готовый weapons stack.

## В scope

1. Один hostile-intent scenario с переходом `blocked -> allowed`.
2. Явный truth-source, открывающий hostile context.
3. `allowed_when` и/или proposal следующего шага в ORION V.
4. Docker-proof и runtime-proof.

## Вне scope

1. Полный weapons stack.
2. Полный combat 1v1.
3. Новый mission system.
4. Полировка unrelated UI.

## Канонический первый сценарий этапа

Первым сценарием фиксируется:

`QIKI, атакуй объект UNBT9999`

в двух состояниях мира:

### Состояние A
- target tracked;
- station influence активен;
- hostile context не открыт.

Ожидаемый результат:
- `blocked/protocol`
- `reason_code=STATION_COMBAT_PROTOCOL_BLOCK`

### Состояние B
- target tracked;
- station influence больше не активен;
- hostile context открыт детерминированно:
  - target track классифицирован как `iff=FOE`.

Ожидаемый результат:
- `allowed/protocol`
- `reason_code=HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK`;
- ORION V показывает, что именно изменилось;
- QIKI подготавливает следующий операторский шаг:
  - conditional allow
  - и/или proposal безопасного combat-entry действия.

## Definition of Done

Этап считается завершённым, когда:
1. один hostile-intent scenario честно проходит через `blocked -> allowed`;
2. context-opening truth-source детерминирован;
3. ORION V показывает новую причинность;
4. есть Docker-proof и runtime-proof;
5. оба контура контроля исполнения зафиксированы как PASS.

## Двухконтурный контроль исполнения

### Контур A: инженерный

Обязан доказать:
- context-open truth-source не выдуман и не дублирует другой канал истины;
- новый `allowed` не ломает существующий protocol block;
- reason code и domain остаются детерминированными;
- Docker tests и runtime-proof зелёные.

Фактическое закрытие:
- truth-source = `world_snapshot["radar_tracks"][target].iff == FOE`;
- `blocked` остаётся за `STATION_COMBAT_PROTOCOL_BLOCK`, если station influence внутри `35 000 м`;
- без station influence, но без `FOE`, команда остаётся `deferred/protocol` с `HOSTILE_CONTEXT_NOT_OPEN`;
- при `FOE` и отсутствии station influence команда становится `allowed/protocol` с `HOSTILE_CONTEXT_OPEN_BY_FOE_TRACK`.

### Контур B: продуктовый

Обязан доказать:
- игрок видит, что QIKI не “передумала”, а честно сменила решение по контексту;
- hostile gameplay начинает ощущаться динамическим;
- проект двигается от первого запрета к первому условному допуску.

Фактическое закрытие:
- ORION V в runtime показывает два разных reason code для одного и того же hostile-intent запроса;
- help-strip и `F1/QIKI` объясняют не только новый допуск, но и то, что именно изменилось: цель классифицирована как `FOE`;
- следующий допустимый шаг показывается через `allowed_when` как явный future combat-entry path.

## Restart-контекст

Если новая сессия стартует заново, сначала читать:
1. этот файл,
2. `TASKS/TASK_20260306_g2_qiki_hostile_context_open_and_conditional_allow.md`,
3. `TASKS/ARTIFACT_20260306_g2_qiki_hostile_context_open_acceptance.md`,
4. `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.
