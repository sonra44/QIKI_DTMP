# 07. Критерии приёмки (формат anti-loop gate)

Статус: target spec. Каждый кодовый этап из `09_WORK_SEQUENCE.md` обязан
нести досье `TASKS/TASK_*.md` с секциями, чьи заголовки **посимвольно**
совпадают с требуемыми `scripts/ops/anti_loop_gate.sh`:

```
## Operator Scenario (visible outcome)
## Reproduction Command
## Before / After
## Impact Metric
```

Ниже — приёмочные карточки. В досье этапа копируется соответствующая
карточка (или её часть) с фактическими baseline/actual.

---

## A. Радар честен (Блок 0.1 + 0.2 + 0.9; этап 2)

## Operator Scenario (visible outcome)
Оператор на F1 открывает страницу РАДАР при живом контакте на шине и видит
трек (пеленг/дальность/риск), а не «0 целей». После рестарта мозга трек
возвращается без ручных действий.

## Reproduction Command
```bash
bash scripts/prove_orion_v_radar_track_visible.sh
# новый prove-скрипт: сеет трек в qiki.radar.v1.tracks, рестартует intents,
# headless-pilot читает страницу РАДАР
```

## Before / After
- Before: после рестарта мозга ~2/3 refresh-циклов без радарных данных;
  «0 целей» при живом контакте; кадр любого сенсора сносит все треки.
- After: трек виден не позднее 2 циклов refresh; пустой эфир — честная
  строка «эфир чист | охват 360°».

## Impact Metric
- Метрика: доля refresh-циклов мозга с радарными данными; случаев
  «0 целей при живом контакте» за 30-мин smoke.
- Baseline: ~33%; >0 случаев.
- Target: ≥95%; 0 случаев.
- Разнос по этапам (by design, раунд 003): долю циклов ≥95% закрывает
  этап 2 юнит/смоком; строка «0 случаев за 30 мин» честно закрывается
  только 30-мин гейтом этапа 11 — в досье task-0036 §A фиксируется
  частично, это не долг.

---

## B. Контекстные действия F1 (этап 9)

## Operator Scenario (visible outcome)
В состоянии docked оператор стрелками выбирает «Расстыковка», жмёт ENTER —
на F5 появляется кандидат с предпросмотром; после `q confirm` телеметрия
стыковки переходит в undocked, консоль показывает Consequence Confirmation.

## Reproduction Command
```bash
bash scripts/prove_orion_v_f1_context_action_release.sh
# обвязка поверх существующего tools/orion_v_qiki_release_dock_smoke.py
```

## Before / After
- Before: ряд 3 — пять фиксированных учебных действий; команда/интент не
  формируется; исполнение только ручным текстом `q: …`.
- After: действия зависят от сцены; выбор публикует intent; исполнение —
  только через пломбу F5.

## Impact Metric
- Метрика: шагов оператора от намерения до подтверждённого эффекта.
- Baseline: 7+ ручных текстовых вводов.
- Target: 3 (выбор, ENTER, `q confirm`).

---

## C. F2/пороги — один владелец (этап 4)

## Operator Scenario (visible outcome)
Чип PWR на F1 и страница ПИТ на F2 показывают одинаковый статус одного
и того же поля при любом значении заряда/напряжения.

## Reproduction Command
```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev \
  bash -lc "pytest tests/unit/test_orion_power_thermal_textual_dashboard.py tests/unit/ -k 'threshold' -q"
```

## Before / After
- Before: `modules/power.py` — 30%/24В против shared 20%/22В; F1 и F2
  могут расходиться в статусе.
- After: пороги импортируются только из `qiki/shared`; расхождение
  воспроизвести невозможно (unit-тест на эквивалентность).

## Impact Metric
- Метрика: число локальных копий порогов в консоли.
- Baseline: 4 места (power.py, cockpit.py, collector.py, operator_state.py).
- Target: 0.

---

## D. F4 — голая `q` и аффорданс (этапы 4, 8)

## Operator Scenario (visible outcome)
Оператор в командном режиме вводит `q` — получает подсказку, а не мгновенное
закрытие консоли; `help` показывает полный сгруппированный список команд;
f5/f8 переключаются текстом.

## Reproduction Command
```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev \
  bash -lc "pytest tests/unit/test_orion_v_last_line_hygiene.py tests/unit/test_orion_v_action_bar.py -q && python tools/orion_v_top_zone_smoke.py"
# + новый unit: голая q → подсказка; quit → подтверждение
```

## Before / After
- Before: `q` в роутере = `action_quit` (`app.py:1478-1481`) — консоль
  закрывается посреди игры; f5/f8 недоступны текстом; help неполон.
- After: `q` → подсказка; выход — `quit`/`exit` с подтверждением; f5/f8 в
  переключателе; help сверен с роутером.

## Impact Metric
- Метрика: аварийных выходов консоли за 30-мин smoke.
- Baseline: воспроизводится одним нажатием.
- Target: 0.

---

## E. F5 — лента и pending (этап 4)

## Operator Scenario (visible outcome)
Лента диалога монотонна по времени через границу суток; счётчик P
не остаётся навсегда завышенным после завершённого/просроченного ожидания.

## Reproduction Command
```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev \
  bash -lc "pytest tests/unit/test_orion_v_qiki_dialog_f5.py tests/unit/test_qiki_voice_full_text_w1.py -q"
# + новый unit: синтетические записи 23:59/00:01 → порядок по ts
```

## Before / After
- Before: сортировка по строке `HH:MM:SSZ` (qiki_dialog.py:94) —
  через полночь лента перемешивается; `_pending_ack_command_id` не
  сбрасывается.
- After: сортировка по полному timestamp; pending сбрасывается по
  resolve/timeout.

## Impact Metric
- Метрика: инверсий порядка в ленте за прогон через смену суток; разница
  счётчика P и фактических ожиданий.
- Baseline: >0; растёт монотонно.
- Target: 0; 0.

---

## F. RCS — движение с последствиями (этап 10)

## Operator Scenario (visible outcome)
После подтверждённого manoeuvre-intent (`sim.rcs.fire` через F5-контур)
позиция/скорость бота в телеметрии изменяются; «Наведение» показывает
фазу полёта Burn/Coast/Brake.

## Reproduction Command
```bash
bash scripts/prove_orion_v_rcs_motion.sh
# новый prove-скрипт: fire → сравнение position/speed до/после N тиков
```

## Before / After
- Before: тяга/топливо считаются, position/speed/attitude не интегрируются
  (`world_model.py:2356-2484` vs `1878-1894`) — движение без последствий.
- After: интеграция в тике; смещение видно в телеметрии и на F1.

## Impact Metric
- Метрика: |Δposition| после стандартного impulse за N тиков.
- Baseline: 0 (не меняется).
- Target: расчётное значение > 0 (формула — из QIKI Body v0.2.2
  calculation frame; выдумывать константы запрещено).

---

## G. 30-минутный runtime-гейт (этап 11)

## Operator Scenario (visible outcome)
Полный стек работает 30+ минут: консоль жива, треки не исчезают при
живом контакте, лента монотонна, память не растёт монотонно, ни одного
unhandled exception.

## Reproduction Command
```bash
bash scripts/prove_orion_v_runtime_30min.sh
# ORIONV_SMOKE_DURATION_S=1800 (полный) / 120 (CI-режим)
```

## Before / After
- Before: гейт отсутствует; P5 из 01_PLAYABLE_CANON не доказан.
- After: скрипт зелёный на 1800 с; DoD G1 (LOG.MD:483) закрыт с evidence.

## Impact Metric
- Метрика: минут стабильного прогона без падений/утечек/рассинхрона.
- Baseline: не измерялось.
- Target: ≥30 мин.
