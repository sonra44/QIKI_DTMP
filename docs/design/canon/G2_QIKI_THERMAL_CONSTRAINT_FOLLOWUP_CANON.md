# Канон G2: тепловое follow-up ограничение после боевого шага

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Назначение

Этот этап начинается после честного закрытия:
- `G2-QIKI-008` — power combat constraint

Уже доказано:
- propulsion-cost hostile burst;
- combat event как отдельный факт;
- power-gate через `pdu_overcurrent`.

Пока не доказано:
- что hostile/combat action оставляет ещё и отдельный тепловой боевой след,
- и что hostile follow-up меняется по тепловому состоянию так же честно, как уже меняется по propulsion/power.

## Имя этапа

`G2-QIKI-009: Thermal Follow-up Constraint`

## Цель

Сделать следующий hostile-контур, где:
- hostile/combat action даёт не только propulsion и power cost;
- тепловой контур тоже фиксирует отдельный след;
- QIKI учитывает этот тепловой след в hostile follow-up.

## Реализованный сценарий

Тот же hostile контур вокруг `UNBT9999`, но в таком состоянии мира, где:
- hostile burst переводит thermal nodes в `WARN` или `TRIP`;
- ORION V показывает это через существующий `F2/Thermal`;
- hostile follow-up меняется по `thermal`, а не по station/protocol или RCS fuel.

## Definition of Done

Этап считается завершённым, когда:
1. hostile/combat step оставляет отдельный thermal след;
2. ORION V показывает thermal след как факт подсистемы;
3. hostile follow-up path меняется по thermal ограничению;
4. Docker-proof и runtime-proof зелёные.

## Фактическое закрытие

Этап закрыт через `thermal.nodes`:
- truth-source: `thermal.nodes[*].warned/tripped`;
- выбранный узел сценария: `pdu`;
- hostile follow-up уходит в `deferred/resource` по `COMBAT_ENTRY_THERMAL_WARN`;
- ORION V показывает `pdu` в `F2/Thermal` как warned node.
