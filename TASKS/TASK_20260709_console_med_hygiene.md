# TASK: Гигиена консоли — голая q, f5/f8, полночь, ACK, кэпы, пороги

**ID:** TASK_20260709_CONSOLE_MED_HYGIENE
**Status:** in_progress
**Owner:** Claude (CLI-агент), этап 4 пакета `orion_playable_f1_f5_v1`
**Date created:** 2026-07-09

## Goal

Консоль не подводит оператора по мелочам (дефекты 0.12–0.17): опечатка не
закрывает сессию, уровни переключаются все, лента не путается в полночь,
счётчик pending честен, память не течёт, пороги — единый shared-канон.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что стало честнее: клавиша/команда «q» даёт подсказку вместо мгновенной
  смерти консоли; `f5`/`f8` работают из командного ввода; диалог F5 не
  переворачивается после полуночи; `P` в ACTION RAIL обнуляется по исходу
  ожидания; карточка «Энергия» на F2 согласована с чипами F1 (канон 20%/22В,
  а не локальные 30%/24В).
- Ограничение: один цикл = один сценарий (этот — console hygiene).

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest tests/unit/test_block0_console_hygiene.py -q
```

## Before / After

- Before: `q` (хоткей И команда) = мгновенный `action_quit`; `f5`/`f8`
  отсутствовали в текстовом переключателе; сортировка ленты по строке
  `HH:MM:SSZ` ломалась через полночь; `_pending_ack_command_id` не
  сбрасывался (`P 1` навсегда — видели живьём), `_publish_sim_command`
  чистил ОБЩУЮ очередь ACK (перетирал чужой pending);
  `_latest_radar_tracks`/`_incident_first_seen`/`DecisionStore` росли без
  предела; пороги питания: локальные 30%/24В в `modules/power.py` против
  канона 20%/22В, копии в `cockpit._energy_block`, топливо сравнивалось с
  батарейным порогом (`operator_state.py`).
- After: «q» → подсказка (оба пути: биндинг `action_show_quit_hint` +
  командный роутер), выход только `quit`/`exit`; `f5`/`f8` в переключателе;
  полуночно-устойчивая сортировка (окно >12ч = перенос через 24ч);
  `_wait_for_ack` сбрасывает pending в `finally` (не трогая чужой новый),
  очередь ACK не чистится — изоляция по command_id + временное окно;
  кэпы: треки 128, инциденты 1024, решения 500 (FIFO-выселение старейших);
  пороги — только `qiki.shared.body_status` (через thresholds-прокси
  Среза 0), топливо — `PROPULSION_FUEL_WARN_PCT`.

## Impact Metric

- Метрика: RED-тесты гигиены (`test_block0_console_hygiene.py`).
- Baseline: 9 failed + 1 пин (все шесть дефектов воспроизведены).
- Target/Actual: **11 passed** (с тестом биндинга); полный `tests/unit`
  зелёный; живой pilot-прогон PASS.

## Scope / Non-goals

- In scope: 0.12–0.17 (`app.py`, `qiki_dialog.py`, `command_decision.py`,
  `modules/power.py`, `cockpit.py`, `operator_state.py`).
- Out of scope: quit-подтверждение диалогом и палитра (этап 8, «сверх
  этапа 4»); смоки `release_dock` (ACK приходит, P=0 — исправлено; падает
  дальше на ожидании ЭФФЕКТА стыковки в телеметрии — отдельный pre-existing
  корень, кандидат этапов 9/10) и `dialog_f5` (pre-existing, отдельный
  корень); 2 pre-existing ruff E501 в app.py (вне моего диффа; мои правки
  сократили счёт с 3 до 2).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/design/operator_console/orion_playable_f1_f5_v1/02_BLOCK0_DEFECT_BASELINE.md` (0.12-0.17)
  - `docs/design/operator_console/orion_playable_f1_f5_v1/08_VERIFICATION_PLAN.md` (этап 4)
  - `src/qiki/services/operator_console/orion_v/hardware_view_model/thresholds.py` (прокси Среза 0)

## Plan (steps)

1) RED-тесты (10 шт.) → 9 failed подтверждено. [сделано]
2) Фиксы 0.12 (роутер + биндинг), 0.13, 0.14, 0.15, 0.16, 0.17; адаптация
   пин-теста `test_publish_sim_command_clears_ack_queue…` → новый контракт
   изоляции (`…isolates_pending_by_command_id`). [сделано]
3) Живой тест. [сделано]
4) Досье + гейты + коммит + консолидация в main. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита этапа

## Evidence (commands → output)

Docker `qiki-dev-phase1` + живой phase1-стек, 2026-07-09.

1. RED: `9 failed, 1 passed`. GREEN после фиксов: `11 passed`.
2. Полный `tests/unit`: зелёный (0 FAILED), включая адаптированный пин
   ACK-изоляции.
3. Живой тест — in-container Textual Pilot (канонный live-формат проекта;
   клавиши извне до Textual не доходят — ограничение herdr/tui-test,
   зафиксировано в памяти):

```
[live] q -> консоль жива, подсказка есть
[live] /f8 -> уровень: f8
[live] /f5 -> уровень: f5
[live] команда q -> консоль жива, подсказка есть
[live] Этап 4 PASS: pilot-прогон на живом коде
```

   Плюс живая консоль в HERDR pane `w1:pW` перезапущена канонным
   `scripts/run_orion_v_live.sh` на код этапа 4 (`M LIVE | P 0`), при
   попутном открытии: после docker restart контейнера pane-вью умирает до
   голого bash — перезапуск вьюхи обязателен.
4. Смок `release_dock`: строка статуса теперь `P 0` (счётчик вылечен);
   остаточное падение — ожидание эффекта стыковки, вне scope (см. Non-goals).
5. Живая иллюстрация 0.15 до фикса: `P 1` в ACTION RAIL висел всю сессию
   (см. STATUS id=5139/5140).
