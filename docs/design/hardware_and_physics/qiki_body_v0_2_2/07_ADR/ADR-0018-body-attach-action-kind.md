# ADR-0018 — Action kind `BODY_ATTACH`: команда телу исполняется локальным body-конвейером, не шиной

## Status

Accepted.

## Date

2026-07-05

## Context

Геймплейный долг F5 (`F5_QIKI_DIALOG_SYSTEM_DESIGN.md` §9): мост M7-M9
(`bridge_decision_to_body`) протестирован изолированно и не подключён к живому
контуру консоли. Для подключения одобренное решение должно доехать до
СУЩЕСТВУЮЩЕГО конвейера тела (`run_attach_pipeline`, живой владелец —
`BodyStructureInteractiveController`, тот же путь, что клавиша `b`).

`QikiProposedActionV1.kind` — строгий Literal `NATS_COMMAND | ORION_PROCEDURE`.
Ни один не подходит:

- `NATS_COMMAND` публикуется в `qiki.commands.control` (шина) — тело живёт в
  локальном контуре консоли, publish на шину был бы ложью о транспорте;
- `ORION_PROCEDURE` — последовательности sim-команд через procedure_engine.

Правило трека (§4 F5-дока): контрактные enum'ы — одним ADR до кода.

RAG-gate выполнен 2026-07-05: канон `06_INTERFACE_CONTROL.md` §6 фиксирует типы
блокировок команды к телу (`power block`, `thermal block`, `passport missing`,
`authorization block`); «Блокировка должна возвращать reason_code. Немой отказ
недопустим». Repo-проверка: мост уже реализует это
(`BRIDGE_POWER_BLOCK`/`BRIDGE_THERMAL_BLOCK`/`BRIDGE_DECISION_NOT_PUBLISHED`,
deferred вместо silent). Расхождений канон/код нет.

## Decision

К `QikiProposedActionV1.kind` добавляется ровно одно значение:

| Значение | Смысл |
|---|---|
| `BODY_ATTACH` | команда установки модуля на тело; исполняется ЛОКАЛЬНЫМ body-конвейером консоли (`bridge_decision_to_body` → `run_attach_pipeline`), НЕ публикуется на шину |

Контракт исполнения `BODY_ATTACH` (живой путь):

1. Полный M5/M6-гейт сохраняется: seal → operator approve → authorize против
   пломбы. Спуф subject/name/params не достигает тела.
2. Предусловия из готовых view-model'ей (новой power/thermal-логики нет):
   `power_blocked` = принятый truth-source G2-QIKI-008
   (`power.load_shedding` / `power.pdu_throttled`); отсутствие power-телеметрии
   в снапшоте = блок (fail-closed: «предусловия недоступны → deferred»);
   `thermal_blocked` = `thermal_status ≠ green` — включая `unknown`
   (fail-closed; `build_power_thermal_console_view_model_from_telemetry`).
3. Блокировка → deferred + reason_code оператору (канон §6: немой отказ
   недопустим); тело не тронуто.
4. Успех/провал ступеней — только через `CommandDecision`
   (validation/publish/ack/effect/audit, ADR-0015: не схлопывать).
5. Трасса решения — аудит-событие (IF-AUDIT-001) с
   `runtime_claim_status` из ADR-0017: `runtime_effect_confirmed` при
   подтверждённом эффекте, `runtime_command_pending` при deferred/блокировке.

`subject` для `BODY_ATTACH` — `orionv.body` (локальный контур, не NATS-стрим);
`name` — `attach.module`.

## Rejected alternatives

- Переиспользовать `NATS_COMMAND` с фильтром по name — отклонено: транспортная
  ложь (команда не идёт на шину) и скрытый спецслучай в execute-пути.
- Оформить attach как `ORION_PROCEDURE` — отклонено: procedure_engine исполняет
  sim-команды, тело в нём не живёт; смешение владельцев правды.
- Публиковать attach на шину и заводить body-consumer — отклонено для фазы
  прототипа: тело канонично живёт в локальном контуре консоли
  (`BodyStructureInteractiveController`), новый body-код запрещён (§7 F5-дока).

## Consequences

- Policy (доверенный продюсер) может предлагать установку модуля как
  `BODY_ATTACH`-кандидат; провайдерский LLM-путь по-прежнему стрипает actions.
- Исполнение `BODY_ATTACH` не добавляет нового пути к шине; RED-тест спуфинга
  обязателен для этого маршрута.
- Расширение kind новыми значениями — только новым ADR.

## Related

ADR-0015, ADR-0017; `06_INTERFACE_CONTROL.md` §6, IF-CMD-BUS-001, IF-AUDIT-001;
`F5_QIKI_DIALOG_SYSTEM_DESIGN.md` §6 (M7-M9), §9.
