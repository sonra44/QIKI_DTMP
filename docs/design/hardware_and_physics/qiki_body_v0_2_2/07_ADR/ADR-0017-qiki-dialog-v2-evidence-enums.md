# ADR-0017 — Enum'ы runtime_claim_status и source_type для конверта QIKI-диалога v2

## Status

Accepted.

## Date

2026-07-04

## Context

План F5 (`docs/design/operator_console/F5_QIKI_DIALOG_SYSTEM_DESIGN.md` §4, §8.4)
требует до кода M4/M5 зафиксировать одним ADR словари для
`QikiChatResponseV2.evidence.runtime_claim_status` и `evidence.source_type`.

RAG-gate выполнен 2026-07-04 (обязателен для канон-выводов):

- **Канон говорит** (`06_INTERFACE_CONTROL.md`, проверено и в RAG-индексе, и в repo —
  расхождений нет):
  - §15.5: словарь доверия фиксирован — `trusted / degraded / conflicting / blind /
    stale / missing / local_reconstruction / hypothesis` (+ принятый консолью
    `fixture_only`). Расширять НЕ требуется и НЕ разрешается этим ADR.
  - §19.4: `source_type` — обязательное поле evidence-фида ORION; словарь его
    значений канон не фиксирует (уровень реализации/ADR).
  - §18.4 + ADR-0015: жизненный цикл команды разделён (validation / publish /
    ACK / effect / audit), ACK ≠ effect confirmation; §19.5 знает
    `ORION_EFFECT_UNCONFIRMED`.
- **Код говорит**:
  - `orion_v/evidence_claim.py`: `source_type` сегодня —
    `telemetry | derived | calculation | target-only | event | command`.
  - `runtime_claim_status` уже живёт одним значением
    `local_ui_loop_no_runtime_command`
    (`cockpit_playable_view_model.py:533,630`, `app.py:881`).
- Rebase-фильтр дизайна §4: `seed_only` / `provider_candidate` НЕ вводить;
  `source_type=provider` — только через ADR+RAG (этот ADR и есть тот случай).

## Decision

### runtime_claim_status (enum v1 для конверта v2)

Статус УТВЕРЖДЕНИЯ О RUNTIME, которое несёт ответ QIKI. Не дублирует ступени
CommandDecision — классифицирует, чем ответ является по отношению к телу:

| Значение | Смысл |
|---|---|
| `local_ui_loop_no_runtime_command` | UI-петля; никакой команды в runtime не было (живое значение, сохраняется как есть) |
| `candidate_only` | ответ — кандидат провайдера/политики; runtime не тронут и не будет тронут этим ответом |
| `runtime_command_pending` | CommandDecision создан, ступени §18.4 не завершены |
| `runtime_effect_unconfirmed` | publish/ACK есть, effect confirmation НЕТ (ADR-0015; сопровождается `ORION_EFFECT_UNCONFIRMED`) |
| `runtime_effect_confirmed` | эффект подтверждён телеметрией/аудитом |

Запрещённые значения (rebase-фильтр §4): `seed_only`, `provider_candidate`.

### source_type (расширение словаря evidence_claim)

К существующим `telemetry | derived | calculation | target-only | event | command`
добавляется ровно одно значение:

| Значение | Смысл |
|---|---|
| `provider` | утверждение произведено LLM-провайдером через QIKI Gateway (CaMeL-карантин: данные, не control flow); trust такого утверждения не может быть `trusted` без независимого подтверждения телом |

### Словарь доверия

`trust_status` остаётся строго §15.5 (+`fixture_only`). Этот ADR его НЕ расширяет.

## Rejected alternatives

- `seed_only` / `provider_candidate` как runtime_claim_status — отклонено
  rebase-фильтром §4 (дублируют `candidate_only` и путают словарь).
- Расширение словаря §15.5 новыми trust-значениями «под LLM» — отклонено:
  происхождение утверждения выражается `source_type=provider`, а не порчей
  канонического словаря доверия.
- Кодирование ступеней validation/publish/ack/effect внутри
  runtime_claim_status — отклонено: ступени живут в CommandDecision (M5),
  схлопывание запрещено ADR-0015.

## Consequences

- M4 (`QikiChatResponseV2.evidence`) использует эти enum'ы как строгую схему.
- Любой ответ, прошедший через провайдера, обязан нести `source_type=provider`
  и не может быть показан ORION как `trusted` без подтверждения.
- Существующие три места с `local_ui_loop_no_runtime_command` уже соответствуют
  enum'у — миграции не требуется.
- Расширение любого из словарей — только новым ADR + RAG-gate.

## Related requirements

REQ-SENSOR-003; REQ-ORION-*.

## Related interfaces

IF-SENSOR-TELEM-001 §15.5; IF-ORION-EVIDENCE-001 §19.4/§19.5; IF-COMMAND §18.4.

## Related ADRs

ADR-0014 (evidence station); ADR-0015 (ACK ≠ effect confirmation).
