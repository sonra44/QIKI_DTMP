# TASK: C5 cap-унификация — одна шкала готовности суперкапа (владелец supercap_gate)

**ID:** TASK_20260710_C5_CAP_UNIFICATION
**Status:** done
**Owner:** Claude (CLI-агент), срез task-0055 (карта AUDIT_2026-07-10 C5, хвост task-0051)
**Date created:** 2026-07-10

## Goal

Убить вторую шкалу суперкапа: контур блокировок команд
`power_thermal_view_model._peak_state` держал локальные пороги 20/70,
а владелец `qiki/shared/supercap_gate` (чип PWR) — канонные 60/30
(T_boost/T_hold, спека Z2). Один физический SoC_cap обязан давать
один вердикт готовности к пику.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что честнее: при SoC_cap 61–69% чип PWR в F1 говорит «▸БУСТ»
  (готов к пику) — и карточка Power/Thermal на F2 теперь говорит
  «peak=ready», а не «limited»; при 20–29% обе поверхности говорят
  «блок» (stab/blocked + CAP_LOW), раньше карточка держала «limited».
  Физически невозможный SoC (вне 0..100) теперь честный unknown
  (наследует guard владельца из аудита 0052), а не «ready».

## Reproduction Command

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev \
  pytest -q tests/unit/test_supercap_scale_honesty.py -p no:warnings
```

## Before / After

- Before: `_peak_state` — локальные `< 20` / `< 70`
  (blocked/limited/ready) против владельца boost≥60 / hold 30–60 /
  stab<30; зона расхождения 20–29% (blocked vs limited у владельца —
  наоборот: stab vs limited) и 60–69% (limited vs boost). Докстринг
  владельца честно называл унификацию «отдельным срезом».
- After: `_peak_state` выводится из `classify_cap_gate` владельца:
  boost→ready, hold→limited (PEAK_LIMITED), stab→blocked (CAP_LOW),
  None→unknown (POWER_TELEM_MISSING). Числовых порогов в консоли не
  осталось; семантика blocked_commands/reason_codes сохранена.
  Устаревший пин (61%→limited) обновлён на канонную шкалу с
  комментарием; докстринг владельца фиксирует унификацию.

## Impact Metric

- Baseline: RED — **3 из 5 красные** (boost-зона 61%→limited;
  stab-зона 25%→limited; границы не совпадают с владельцем).
- Target/Actual: **5 passed** (новый пакет) + пакет дашборда 11 passed;
  полные скоупы: tests/unit **1238 passed**, src-деревья **808 passed**,
  0 FAILED (Docker, qiki-dev).

## Scope / Non-goals

- [x] `_peak_state` → шкала владельца (boost/hold/stab/None).
- [x] RED-тест `tests/unit/test_supercap_scale_honesty.py`
  (зоны + границы ровно по константам владельца + unknown).
- [x] Обновление устаревшего пина старой шкалы (61→ready, limited=45).
- Non-goals: `CAP_LOW` в `shared/models/rcs.py:161` и симовые
  NBL/SAFE_CAP_LOW (`world_model.py`) — там семантика «кап пуст»
  (`<= 0.0`), не шкала готовности; K1 snapshot-контракт (дальше по
  дорожке); пороги bus_v.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Владелец: `src/qiki/shared/supercap_gate.py` (канон §13 BODY_CANON,
  T_boost/T_hold — bot_gdd Power Plane; числа — спека Z2 пакета)
- Карта: `docs/dev/AUDIT_2026-07-10_STRUCTURE.md` (C5)

## Plan (steps)

1) Разведка обеих шкал + поиск третьих копий (нет: rcs/сим — другая
   семантика). [сделано]
2) RED-тест → фикс `_peak_state` через владельца → GREEN + полные
   скоупы. [сделано]
3) Досье + гейты + коммит + ff-merge main + push + рестарт консоли +
   борд + STATUS-чекпоинт. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated (докстринг владельца + это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence

```
RED:   3 failed, 2 passed (test_supercap_scale_honesty.py, до фикса)
GREEN: 5 passed + dashboard 11 passed (16 passed суммарно)
tests/unit:                     1238 passed in 196.12s
src/qiki/services src/qiki/core: 808 passed in 64.54s
```
