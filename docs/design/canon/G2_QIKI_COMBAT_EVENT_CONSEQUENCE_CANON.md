# Канон G2: боевое событие и последствие после hostile-решения

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Назначение

Этот этап начинается после честного закрытия:
- `G2-QIKI-005` — tactical state shift после combat-entry

Система уже умеет:
- объяснять hostile block/allow/resource/tactical state;
- готовить и подтверждать первый combat-entry;
- менять следующий допустимый ход по новому тактическому состоянию.

Следующий незакрытый кусок `G2`:
- последствие hostile-решения должно существовать не только как UI-текст, но и как отдельное боевое событие/следствие.

## Имя этапа

`G2-QIKI-006: Combat Event + Consequence Visibility`

## Цель

Сделать первый законченный hostile contour, где:
- hostile action уже меняет tactical state;
- ORION V получает отдельный боевой event/consequence signal;
- оператор видит не только решение QIKI, но и зафиксированное боевое последствие.

## Definition of Done

Этап считается завершённым, когда:
1. после hostile/combat шага появляется отдельный боевой event/consequence signal;
2. ORION V показывает его как отдельный факт, а не только как текст QIKI;
3. Docker-proof и runtime-proof зелёные.

Фактическое закрытие:
- после подтверждения `hostile_rcs_intercept_burst` ORION V публикует отдельный event `qiki.events.v1.operator.combat`;
- event имеет `event_type=COMBAT_ENTRY_CONFIRMED` и `reason_code=COMBAT_EVENT_INTERCEPT_BURST_CONFIRMED`;
- `F3` показывает этот event как отдельный факт мира через общий event-store, а не через блок `QIKI`;
- unit proof и live runtime-proof зелёные.
