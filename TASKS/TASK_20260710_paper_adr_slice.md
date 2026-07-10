# TASK: «Бумажный» срез — 3 ADR по зоне пробелов (BRAKE OVERRIDE / identity Layer-07 / владелец тика)

**ID:** TASK_20260710_PAPER_ADR_SLICE
**Status:** done
**Owner:** Claude (CLI-агент), срез task-0054 (решение оператора id=5161 + переосмысление id=5163)
**Date created:** 2026-07-10

## Goal

Закрыть дизайн-фазу «тяжёлого пути» дёшево и обратимо: три
decision-only ADR фиксируют направление по трём невынесенным
канон-решениям (аварийный путь команды; владелец идентичности целей
Layer-07; владелец тика/решений), с восстановлением авторского замысла
исследованием (канон+лор+код) вместо интервью и сверкой пересечений,
чтобы решения задним числом не ломали смежное.

## Operator Scenario (visible outcome)

- Кто выполняет: operator (читатель канона) / будущие срезы
- Что честнее: зона пробелов перестаёт быть устной — три решения
  записаны как канон с основаниями file:line и канон-цитатами; этап 9
  получает формальный гейт (BRAKE OVERRIDE ADR существует до его
  старта), этап 9b — двухключевой контракт intent (S1-мини) как гейт;
  K4 получает критерий приёмки. «Кодить фундамент вслепую» больше
  невозможно: направление зафиксировано до кода.

## Reproduction Command

```bash
ls docs/design/canon/ADR/ADR_2026-07-10_*.md && \
rg -l "2026-07-10" docs/design/canon/ADR/README.md docs/design/canon/INDEX.md
```

## Before / After

- Before: владелец Layer-07 fusion канонически не назначен
  (SENSOR_OBS_0001 Non-goals) — три живых радар-матчинга с разными
  порогами + сырой proto-путь в FSM (N7) + транслятор-налог в intents
  (N8, 19 упоминаний); владелец тика не закреплён — два мозга гоняют
  один конвейер (S2), в мосте спит второй intent-исполнитель на одной
  env-строке (N2); BRAKE OVERRIDE — только рамки в REPLY_002, ADR нет,
  этап 9 без гейта.
- After: три ACCEPTED design-only ADR в `docs/design/canon/ADR/`,
  зарегистрированы в ADR README + canon INDEX; каждое решение обосновано
  канон-источниками (01_BODY_CANON §12, IF-CMD §18, SENSOR_OBS_0001,
  bot_gdd Safety Plane, CONTEXT_LOCK п.5, compose-признание) и
  код-фактами (world_model:243, radar_track_store:73-74,
  ship_fsm_handler:414-443, intents-транслятор); секции «Пересечения»
  фиксируют, что НЕ ломается (SENSOR_OBS-граница, radar_v1 контракт,
  пин P2, F5-владение intents, пауза мира).

## Impact Metric

- Baseline: 0 ADR по трём пробелам; 2 ADR в каталоге; кодовые следствия
  пробелов: ≥3 идентичности на одну цель, 2 конвейера-дублёра.
- Target/Actual: **3 ADR ACCEPTED** (5 в каталоге), оба индекса
  обновлены; гейты этапов 9/9b формализованы; RAG-грунт выполнен
  (SENSOR_OBS_0001, 01_BODY_CANON, 06_INTERFACE_CONTROL, bot_gdd,
  06_COMMAND_SURFACE, 01_PLAYABLE_CANON) + спот-чек кода живьём.

## Scope / Non-goals

- [x] ADR BRAKE OVERRIDE (design-only, реализация gated «после Блока 0,
  до этапа 9»).
- [x] ADR идентичность целей / Layer-07 (мозг-владелец, мост-транспорт,
  транспондер-якорь, S1-мини как гейт 9b; K2-код после пакета).
- [x] ADR владелец тика (qiki-dev; intents-проекция; N2 нештатный;
  K4 после K2).
- Non-goals: НИКАКОГО кода в этом срезе; Layer-08 sensor trust
  (отдельное будущее решение); переименование fsm_state (N3, гигиена
  за пакетом); механика доставки мозговых track_id в NATS (внутри
  K2-кода).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Карта аудита: `docs/dev/AUDIT_2026-07-10_STRUCTURE.md` (S1/S2/N2/N6-N9)
- Рамки оператора: `docs/design/operator_console/orion_playable_f1_f5_v1/_support/CLARIFICATION_REPLY_002.md`
- Канон-основания: `docs/design/hardware_and_physics/qiki_body_v0_2_2/*`
  (§12, §18), `SENSOR_OBS_0001_OBJECTIVE_TO_SENSOR_BOUNDARY.md`

## Plan (steps)

1) RAG-грунт трёх зон + спот-чек кода (Serena/grep живьём). [сделано]
2) Три ADR + регистрация в README/INDEX. [сделано]
3) Досье + гейты + коммит + ff-merge main + push + борд + чекпоинт.
   [этот шаг]

## Definition of Done (DoD)

- [x] RAG canon-gate выполнен (каждый канон-вывод грунтован
  qiki-rag → doc/chunk → repo-check)
- [x] Docs updated (3 ADR + README + INDEX + это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence

```
RAG: SENSOR_OBS_0001 Non-goals → Layer-07/08 (владелец fusion не назначен)
     01_BODY_CANON §12: safe-brake штатный, manual override debug-only,
     RCS через command gating; IF-CMD §18 lifecycle+reason codes
     bot_gdd Safety Plane: «FDIR: Brake override при угрозе» (замысел)
Код: world_model.py:243 (2500/12/8/250) vs radar_track_store.py:73-74
     (12/15) vs ship_fsm_handler.py:414-443 (raw proto, N7);
     intents public_track_id — 19 упоминаний (N8);
     compose env intents: «не владеет FSM-правдой» (S2)
```
