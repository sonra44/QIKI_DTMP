# Канон G2: тактический сдвиг после combat-entry и новые опции

Статус: complete
Дата: 2026-03-06
Ответственные: user + codex

## Назначение

Этот этап начинается после честного закрытия:
- `G2-QIKI-004` — hostile resource gate

Система уже умеет:
- заблокировать hostile intent;
- открыть hostile-контекст;
- подготовить первый combat-entry step;
- требовать подтверждение оператора;
- резать hostile continuation по ресурсу.

Но пока ещё не доказан следующий пункт `LOG.MD`:
- боевые решения меняют тактическое состояние и дальнейшие опции.

## Имя этапа

`G2-QIKI-005: Tactical State Shift + Conditional Follow-up`

## Цель

Сделать следующий законченный hostile-контур, где:
- первый combat-entry step уже исполнен;
- мир и ORION V показывают новый тактический контекст;
- тот же hostile loop меняет следующий допустимый шаг;
- QIKI объясняет не только причину, но и новую боевую ситуацию.

## Канонический сценарий

Команда остаётся в hostile-контуре вокруг объекта `UNBT9999`, но после подтверждённого
`hostile_rcs_intercept_burst` система должна показать:
- что тактическое состояние уже изменилось;
- что next step уже не тот же самый, что до combat-entry.

## Definition of Done

Этап считается завершённым, когда:
1. после подтверждённого combat-entry ORION V показывает новый tactical state;
2. hostile follow-up path меняется детерминированно;
3. QIKI объясняет, что именно изменилось;
4. Docker-proof и runtime-proof зелёные.

Фактическое закрытие:
- truth-source закреплён через `propulsion.rcs.active/command_pct/time_left_s`;
- тот же hostile запрос меняет path с `COMBAT_ENTRY_PROCEDURE_READY` на `TACTICAL_STATE_INTERCEPT_ACTIVE`;
- ORION V показывает новый next step: дождаться завершения текущего импульса и переоценить ситуацию;
- Docker-proof и runtime-proof зелёные.
