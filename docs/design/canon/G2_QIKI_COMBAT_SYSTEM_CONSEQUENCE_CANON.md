# Канон G2: системное отражение боевого последствия

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Назначение

Этот этап начинается после честного закрытия:
- `G2-QIKI-006` — боевое событие и отдельная видимость последствия

Система уже умеет:
- объяснять hostile block/allow/resource/tactical state;
- готовить и подтверждать первый combat-entry;
- публиковать отдельный `combat` event после подтверждённого hostile шага.

Но следующий обязательный пункт `LOG.MD` ещё не доказан полностью:
- влияние боя на `EPS/Thermal/Propulsion/Comms` как реальные ограничения.

## Имя этапа

`G2-QIKI-007: Combat System Consequence Reflection`

## Цель

Сделать следующий законченный hostile-контур, где:
- отдельное combat event уже появилось;
- хотя бы одна бортовая система отражает этот боевой факт как ограничение или стоимость;
- ORION V показывает эту системную цену боя отдельно от текста QIKI;
- следующий hostile follow-up меняется по этой системной цене.

## Канонический следующий сценарий

Тот же hostile контур вокруг `UNBT9999`, но после подтверждённого `hostile_rcs_intercept_burst`
система должна показать не только combat event, но и реальное системное следствие:
- например по `propulsion`, `thermal`, `power` или `comms`;
- затем QIKI должна учитывать это следствие в следующем решении.

## Definition of Done

Этап считается завершённым, когда:
1. подтверждённый боевой шаг оставляет отдельный системный след в телеметрии/ограничениях;
2. ORION V показывает его как факт подсистемы, а не только как текст боевого события;
3. hostile follow-up path меняется по этой системной цене;
4. Docker-proof и runtime-proof зелёные.

Фактическое закрытие:
- `QSimService`/`WorldModel` теперь публикуют реальную цену RCS-импульса в `propulsion.fuel_pct`, `propulsion.fuel_total_g`, `propulsion.fuel_rate_gs`, `propulsion.remaining_fuel_g`;
- ORION V уже умел читать эти поля через `hardware_view_model`, поэтому `F2/Propulsion` начал показывать системную цену hostile burst без нового UI-контура;
- deterministic smoke с начальным `propellant_kg=2.05` проходит через `prepared -> confirmed -> fuel spent visible -> blocked/resource`;
- следующий hostile follow-up меняется по текущей телеметрии `propulsion.rcs.propellant_kg`, без скрытого state-store.
