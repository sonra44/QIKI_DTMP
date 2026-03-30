# Канон G2: тепловое или энергетическое ограничение после боевого действия

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Назначение

Этот этап начинается после честного закрытия:
- `G2-QIKI-007` — системная цена hostile burst по propulsion

Система уже умеет:
- показать отдельный combat event;
- показать отдельную propulsion-цену hostile burst;
- менять hostile follow-up по потере ресурса RCS.

Но следующий обязательный пункт `LOG.MD` ещё не закрыт достаточно полно:
- влияние боя на `EPS/Thermal/Propulsion/Comms` как реальные боевые ограничения.

## Имя этапа

`G2-QIKI-008: Thermal/Power Combat Constraint`

## Цель

Сделать следующий законченный hostile-контур, где:
- hostile/combat action уже оставляет propulsion-цену;
- одна дополнительная система (`thermal` или `power`) тоже отражает цену боя;
- QIKI учитывает уже не только RCS resource, но и второй системный контур ограничения.

## Реализованный сценарий

Выбран путь `power`, а не `thermal`.

Тот же hostile контур вокруг `UNBT9999`, но после подтверждённого hostile шага:
- hostile burst переводит power contour в `pdu_overcurrent`;
- ORION V показывает это через `F2/Power` и `shed_reasons`;
- hostile follow-up меняется по `COMBAT_ENTRY_POWER_OVERCURRENT`.

## Definition of Done

Этап считается завершённым, когда:
1. hostile/combat step оставляет отдельный тепловой или энергетический след;
2. ORION V показывает его как факт подсистемы;
3. hostile follow-up path меняется по этому ограничению;
4. Docker-proof и runtime-proof зелёные.

## Фактическое закрытие

Этап закрыт через `power`-ветку:
- truth-source: `power.load_shedding`, `power.shed_reasons`, `power.pdu_throttled`, `power.throttled_loads`;
- reason_code: `COMBAT_ENTRY_POWER_OVERCURRENT`;
- ORION proof: `F2/Power` показывает `pdu_overcurrent`;
- hostile follow-up уходит в `blocked/resource`.
