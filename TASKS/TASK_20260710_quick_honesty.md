# TASK: Срез «Быстрая честность» — один факт = один класс тревоги (C2/C3/C4/C11)

**ID:** TASK_20260710_QUICK_HONESTY
**Status:** done
**Owner:** Claude (CLI-агент), срез task-0053 (карта `docs/dev/AUDIT_2026-07-10_STRUCTURE.md`)
**Date created:** 2026-07-10

## Goal

Закрыть находки C2/C3/C4/C11 аудит-карты: панели консоли обязаны давать
ОДИН класс тревоги на один физический факт, пороги — только из владельца
`qiki/shared/body_status` (через реэкспорт `hardware_view_model/thresholds`),
без локальных литералов. Карта аудита коммитится этим же срезом.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что честнее: при ядре 92°C F1-кокпит больше НЕ кричит КРИТИЧНО, пока
  канон (crit=95) говорит ПРЕДУПРЕЖДЕНИЕ — раньше F1 и F2 расходились в
  полосе 90–94° и оператор видел два разных вердикта об одном ядре;
  SoC ровно на пороге (15% / 20%) даёт одинаковый класс на чипах F1,
  карточке F2 и в shared-каноне (граница = худший класс, консервативно);
  staleness тепла привязана к владельцу `COMMS_AGE_CRIT_S`, а не к
  зашитой тридцатке.

## Reproduction Command

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/unit/test_threshold_honesty.py -p no:warnings
```

## Before / After

- Before: `cockpit._thermal_block` держал литералы 90/80 против канона
  `THERMAL_CORE_CRIT_C=95` / `THERMAL_CORE_WARN_C=80` — в полосе 90–94°
  F1 crit, F2 warn (C2); `cockpit._energy_block` и
  `modules/power.render_summary` сравнивали SoC через `<` против
  канонного `status_by_min` = `<=` — ровно на пороге классы панелей
  расходились (C3, `operator_state` уже был `<=`); staleness тепла в
  `_thermal_evidence_line` — литерал `30.0` мимо владельца (C4);
  в `app.py` жил мёртвый `OrionVApp._telemetry_freshness_seconds` (C11).
- After: термо-пороги и staleness импортируются из владельца
  (`thresholds` → реэкспорт `body_status`, копий нет); SoC-сравнения
  `<=` во всех трёх дериверах; мёртвый метод снесён
  (Serena `safe_delete`, 0 ссылок); RED-тест
  `tests/unit/test_threshold_honesty.py` пинит согласованность классов
  на границах и связь порога с владельцем (monkeypatch константы).

## Impact Metric

- Baseline: RED-прогон — **4 из 6 красные** (C2: 92°→crit вместо warn;
  C3: SoC==15 → warn вместо crit в обоих дериверах; C4: staleness не
  сдвигается за константой).
- Target/Actual: **6 passed** (пакет среза); полные скоупы:
  `tests/unit` **1233 passed**, `src/qiki/services src/qiki/core`
  **808 passed**, оба EXIT=0 в qiki-dev (Docker).

## Scope / Non-goals

- [x] C2 термо-литералы 90/80 → канон-константы.
- [x] C3 SoC `<`→`<=`: `cockpit._energy_block` + `modules/power`.
- [x] C4 staleness 30.0 → `COMMS_AGE_CRIT_S`.
- [x] C11 снос мёртвого `_telemetry_freshness_seconds`.
- [x] Карта `docs/dev/AUDIT_2026-07-10_STRUCTURE.md` в репо этим срезом.
- Не взято (по карте, осознанно): C5 cap-унификация `_peak_state`
  (следующий срез), пороги `bus_v` в `modules/power` (`<` оставлен —
  вне скоупа среза, отдельная сверка с каноном), C1/C6/C13 (уходят в
  K1 snapshot-контракт).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Карта аудита: `docs/dev/AUDIT_2026-07-10_STRUCTURE.md`
- Владелец порогов: `src/qiki/shared/body_status.py`
  (реэкспорт: `orion_v/hardware_view_model/thresholds.py`)

## Plan (steps)

1) Ловушки теста (распаковка `severity, lines`; реальное имя
   `PowerSubsystemModule.render_summary`; ассерт через `tr("crit")`
   — консоль русская). [сделано]
2) RED-прогон → фиксы C2/C3/C4/C11 → GREEN + полные скоупы. [сделано]
3) Досье + гейты + коммит + ff-merge main + push + рестарт консоли
   + борд + STATUS-чекпоинт. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated (это досье + аудит-карта в репо)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence

```
RED:   4 failed, 2 passed (tests/unit/test_threshold_honesty.py)
GREEN: 6 passed
tests/unit:                     1233 passed in 194.37s
src/qiki/services src/qiki/core: 808 passed in 63.93s
```
