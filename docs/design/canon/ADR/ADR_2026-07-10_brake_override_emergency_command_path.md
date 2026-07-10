# ADR: BRAKE OVERRIDE — аварийный короткий путь одобрения (не второй источник команд)

**Status:** ACCEPTED (design-only; реализация gated)
**Date:** 2026-07-10
**Decision owner:** оператор (рамки делегированы CLI-агенту, `_support/CLARIFICATION_REPLY_002.md`)

## Context

- Канон пакета playable фиксирует гэп G4: «BRAKE OVERRIDE („большой
  красный") — потенциально единственный кандидат на прямой аварийный путь
  мимо диалога. В v1 не делается; требует отдельного ADR»
  (`docs/design/operator_console/orion_playable_f1_f5_v1/06_COMMAND_SURFACE_CONTROL_PATH.md`, «Исключения»).
- Авторский замысел уже записан в лоре: Safety Plane содержит «FDIR:
  обнаружение/изоляция отказов, **Brake override при угрозе**» и режим
  `Brake` в Mode Manager (`bot_gdd.md`, Safety Plane) — аварийное
  торможение задумано как штатная способность тела, не как хак пульта.
- QIKI Body canon: safe-brake — штатная функция RCS; «Manual override
  отдельных RCS-сопел может существовать только как debug-only…
  не обычная игровая кнопка»; «RCS-команды должны проходить через command
  gating» (`01_BODY_CANON.md` §12, REQ `02_REQUIREMENTS.md`).
- Инварианты контура: исполнение достигает тела только через пломбу
  `CommandDecision` (P3, `01_PLAYABLE_CANON.md`); lifecycle команды —
  request → validation → allowed/rejected → publish → ACK → effect →
  audit (IF-CMD, `06_INTERFACE_CONTROL.md` §18); Safe Mode authority =
  Q-Core Agent, dual-source запрещён (`CONTEXT_LOCK_QIKI_DTMP.md` п.5).
- Рамки оператора (REPLY_002 A8): design-only, строго после Блока 0,
  в v1 не реализуется; триггер написания кода — до старта этапа 9
  (контекстные действия Burn/Brake обострят ожидание этого пути).

## Decision

1. **BRAKE OVERRIDE = короткий путь ОДОБРЕНИЯ, не второй источник
   команд.** Он минует диалог/LLM-контур (F5-беседу и цикл
   предложение→подтверждение), но НЕ минует пломбу `CommandDecision`,
   legality-гейт и аудит.
2. Один жест оператора (выделенная кнопка/команда) порождает готовый
   intent класса `BRAKE` с preset-параметрами и сразу проводит его через
   пломбу: ступени propose/commit сливаются в один шаг **только для
   этого класса**; сам жест удовлетворяет `CMD_CONFIRMATION_REQUIRED`.
3. Исполнение — штатный RCS safe-brake через command gating (SoC_cap,
   PDU, thermal, SAFE и пр., §12). Если gating отклоняет — оператор
   видит честный `rejected + reason_code`; форс-пути мимо тела нет.
4. Safe Mode authority остаётся у Q-Core Agent: override не создаёт
   конкурирующего органа безопасности.
5. Это НЕ manual override сопел (тот остаётся debug-only по §12).
6. Класс команд короткого пути — ровно один: `BRAKE`. Расширение
   списка требует нового ADR.

## Consequences

Positive:
- Аварийный стоп за одно действие вместо 7+ вводов диалога — критерий
  операторской значимости в hardcore-пульте выполнен.
- Инвариант «одобрено = исполнено» и аудит-след сохраняются даже в
  аварийном пути; спуф-тесты пломбы (m5) покрывают и его.

Negative / costs:
- Ещё один UI-affordance с single-owner обязательствами.
- Соблазн «а давайте так же для X» — заблокирован п.6 намеренно.

## Alternatives considered

1) **Прямой путь мимо пломбы/гейта** — отвергнут: нарушает P3 и
   `CONTEXT_LOCK` п.5 (dual-source), убивает доверие к аудиту.
2) **Оставить только диалоговый путь** — отвергнут: аварийность через
   цикл беседы противоречит замыслу Safety Plane (FDIR) и критерию
   значимости; этап 9 сделает разрыв видимым.
3) **Manual override RCS-сопел как аварийный путь** — отвергнут:
   прямой запрет `01_BODY_CANON.md` §12 (debug-only).

## Пересечения (сверка «задним числом»)

- Этап 9 (контекстные действия Burn/Brake): штатное действие Brake и
  override — один intent-класс, две точки входа; кнопка override НЕ
  дублирует владельца действия (single-owner: рейл действий владеет
  выбором, override — аварийным входом).
- Пломба/спуф-тесты: инварианты не меняются — override добавляет
  источник intent, не источник исполнения.
- ORION evidence (§18.7): allowed/published/ACK/effect видимы и для
  override — без исключений.
- Триггер реализации: после закрытия Блока 0 (этапы 1–3), до старта
  этапа 9. До того — только этот документ.
