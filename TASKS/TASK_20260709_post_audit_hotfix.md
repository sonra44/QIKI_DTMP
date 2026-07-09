# TASK: Hotfix пост-фикс аудита — ACK-контракт, lock warmup, честные факты

**ID:** TASK_20260709_POST_AUDIT_HOTFIX
**Status:** in_progress
**Owner:** Claude (CLI-агент), срез 1 карты `AUDIT_2026-07-09_POSTFIX.md`
**Date created:** 2026-07-09

## Goal

Закрыть быстрые MED-находки пост-фикс аудита: M1 (fire-and-forget залипает P),
M2 (гонка захвата command_id), M3 (схлопывание фактов недостижимо на боевом
пути + врущие литералы порогов), M7 (ingest в обход lock).

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что честнее: `sim.start` из консоли доводит цикл до исхода — «ACK получен» /
  «Ack timeout», P обнуляется; шаг процедуры не «падает» из-за чужой
  параллельной команды; «Краткие факты» не выдают хвост-подпись за данные и
  не прячут тревожную группу; подписи порогов («crit < 15%», «limit 95°C»)
  берутся из shared-канона (литерал «90°C» врал обеим константам: warn 80 /
  crit 95).
- Ограничение: один срез = быстрые точечные фиксы; M4/M6 (радар-честность-2),
  M5 (staleness), M8 (field_sources→телеметрия) — следующие срезы карты.

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest tests/unit/test_post_audit_hotfix.py -q
```

## Before / After

- Before: `_try_sim_world_command` спавнил publish без ожидания — pending
  никогда не снимался (P залипал; видели живьём весь день); `_wait_for_ack`
  захватывал ОБЩИЙ слот `_pending_ack_command_id` после yield публикации —
  конкурент успевал перезаписать → ложный «нет ack»; details «Кратких фактов»
  всегда несли статический хвост («Нет данных | crit < 15%») → схлопывание
  Z8 не срабатывало никогда (overclaim этапа 5); exception-ветка warmup
  мутировала context в обход lock.
- After: `_publish_sim_command` возвращает command_id; `_wait_for_ack`
  принимает его параметром (id уникален — временное окно не нужно; fallback
  на слот для внешних смоков); fire-and-forget идёт через
  `_publish_sim_command_tracked` (publish → wait → исход в ленту);
  ProcedureEngine прокидывает id шага; `_fact_value_detail` считает деталь
  пустой без ЗНАЧЕНИЯ; ok-группы схлопываются, warn/crit-группы остаются
  видимыми с чистым «Нет данных» (разрешение конфликта Z8 ↔ §19.6);
  подписи порогов из POWER_SOC_CRIT_PCT / THERMAL_CORE_CRIT_C; fallback-ingest
  warmup — под lock.

## Impact Metric

- Метрика: RED-тесты hotfix (`test_post_audit_hotfix.py`).
- Baseline: 5 failed (все четыре дефекта воспроизведены).
- Target/Actual: **6 passed** (с warn-правилом); полный `tests/unit` 0 FAILED.

## Scope / Non-goals

- In scope: M1, M2, M3 (+2 LOW-литерала порогов), M7; синхронная адаптация
  стабов `wait_ack` (5 тест-файлов, 3 смок-тулзы) и литерала «limit 90°C»
  (2 тест-пина — подпись стала честной).
- Out of scope: M4/M5/M6/M8 и LOW-пакет карты; `_publish_world_time_command`
  и execute-путь уже ждали ACK — им добавлен только точный command_id.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/dev/AUDIT_2026-07-09_POSTFIX.md` (карта, порядок починки)
  - `docs/design/operator_console/orion_playable_f1_f5_v1/03_F1_COCKPIT_SPEC.md` (Z8)

## Plan (steps)

1) RED-тесты (5 шт.) → подтверждено 5 failed. [сделано]
2) Фиксы M1/M2/M7/M3 + адаптации стабов и пинов. [сделано]
3) Восстановление после сжатия контекста: сверка дерева, доделаны 2 подвисших
   куска (warn-правило, имя параметра стаба). [сделано]
4) Живой e2e + досье + гейты + коммит + main. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence (commands → output)

1. RED: `5 failed` (M2 TypeError-контракт, M1 ×2, M3 боевые строки, M7 lock).
   GREEN: `6 passed`; полный `tests/unit`: **0 FAILED** (адаптированы стабы
   wait_ack в world_pause/qiki_loop/dock_echo/procedure_engine + 3 смок-тулзах;
   пины «limit 90°C»→«95°C» в cockpit/app_incidents — подпись стала честной).
2. Ruff: 27 ошибок до и после — дифф не добавил ни одной (stash-сверка).
3. Живой e2e (pilot + живой NATS/сим):

```
[live] NATS connected
[live] M1: sim.start отправлена, ACK получен, pending снят (P 0) ✓
[live] last_command_status: acknowledged
[live] Hotfix PASS: живой ACK-цикл честен
```

   Мир возвращён в STOPPED канонной sim.stop.
4. Гейты: см. коммит (branch_policy PASS · anti_loop OK · drift EXIT=0 ·
   quality_gate EXIT=0).
