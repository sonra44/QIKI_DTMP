# Канон G2: связь и боевой follow-up

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Назначение

Этот этап начинается после честного закрытия:
- `G2-QIKI-009` — thermal follow-up constraint

Уже доказано:
- propulsion-cost hostile burst;
- power-gate hostile follow-up;
- thermal-gate hostile follow-up.

Пока не доказано:
- что hostile/combat loop честно учитывает ограничение по `comms/target link` как отдельный follow-up контур.

## Имя этапа

`G2-QIKI-010: Comms Combat Constraint`

## Цель

Сделать следующий hostile-контур, где:
- hostile step уже прошёл через propulsion/power/thermal;
- связь или target-link становится отдельным боевым ограничением;
- QIKI меняет hostile follow-up по состоянию `comms`, а ORION V показывает это как факт подсистемы.

## Канонический следующий сценарий

Тот же hostile контур вокруг `UNBT9999`, но в таком состоянии мира, где:
- hostile follow-up требует устойчивого канала связи/target-link;
- `comms` не готов или деградирован;
- ORION V показывает это через существующий `F2/Comms`;
- hostile follow-up меняется по `comms`, а не по station/power/thermal.

## Definition of Done

Этап считается завершённым, когда:
1. hostile/combat follow-up имеет отдельный `comms` truth-source;
2. ORION V показывает этот `comms`-след как факт подсистемы;
3. QIKI меняет hostile follow-up path по этому ограничению;
4. Docker-proof и runtime-proof зелёные.
