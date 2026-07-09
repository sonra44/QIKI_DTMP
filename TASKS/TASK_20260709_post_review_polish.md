# TASK: Пост-ревью полировка — honesty-фиксы страницы РАДАР + UI/UX P1

**ID:** TASK_20260709_POST_REVIEW_POLISH
**Status:** in_progress
**Owner:** Claude (CLI-агент), срез после этапа 6 (`task-0042`)
**Date created:** 2026-07-09

## Goal

Закрыть находки двойного субагент-ревью проделанной работы (запрос
оператора: «проверка с субагентами + подправить дизайн CSS и UI UX»):
адверсариальный код-ревьюер прошёл диффы этапов 4-6 и пост-аудитных срезов,
UI/UX-ревьюер — живой рендер консоли. Применён пакет: 2 HIGH, честность
риска без кинематики, UI P1.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что видно: страница РАДАР на F1 больше не «серая» — строки треков
  подсвечиваются семантически (IFF FOE — crit-красный, FRND — ok, UNK —
  warn; полные слова WARNING/CRITICAL тоже красятся); трек с нулевым
  пеленгом/качеством показывает честные «пеленг 000°»/«кач 0.00», а не
  «—»; трек без кинематики показывает «риск —» (неизвестно), а не ложный
  OK; F2 активная MFD-кнопка снова видна (heavy-рамка съедала строку);
  подписи рамок MFD раздельные («страницы: [» слева, «страницы: ]»
  справа), кнопки по-русски.
- Что честнее под капотом: `sim.pause` из STOPPED отвергается (не
  «оживляет» мир для ротации радара); неконечные range/vr не рождают
  риск-вердикт.

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest \
  tests/unit/test_f1_radar_page.py tests/unit/test_ui_polish.py \
  tests/unit/test_radar_honesty_2.py tests/unit/test_f1_decompress.py -q
bash scripts/prove_orion_v_f1_radar_page.sh
```

## Before / After

- Before (находки ревью):
  1. **HIGH falsy-zero**: view-model строил поля falsy-`or`-цепочками
     (`track.get("range") or track.get("distance_m")`) — легальный 0.0
     (пеленг строго на носу, качество 0) выпадал в «данных нет»; NaN/inf
     проходили в рендер и в classify_approach_risk.
  2. **HIGH спуф-смок сломан**: стаб `_wait_for_ack` в
     `orion_v_qiki_decision_spoof_deny_smoke.py` не адаптирован под новую
     сигнатуру (`command_id=`) из hotfix M2 — смок падал TypeError до
     проверяемого контракта (та же дыра в thermal_followup и
     combat_system смоках).
  3. Трек без кинематики получал risk="ok" — ложное успокоение оператора.
  4. UI: '#'-префикс строк треков уводил весь рендер в muted
     bullet-ветку ui_rich (страница серая); `WARN|WARNING` в `_STATUS_RE`
     матчил короткий префикс и boundary-check отбрасывал — полные
     WARNING/CRITICAL нигде не подсвечивались; IFF-коды не имели стиля;
     `.mfd-active` heavy-border съедал height:1 кнопки; общая подпись
     «перекл. страниц: [ / ]» на обеих рамках; derived-пометка дублировалась
     в каждой строке.
  5. `sim.pause` из STOPPED поднимал `_sim_running=True` — край M4.
- After: `_first_num`/`_first_present` (0.0 — данные; None/отсутствие —
  нет данных) + `math.isfinite`-guard в `_num` и в
  `classify_approach_risk` (не-конечное/отрицательное range → ("ok",
  None)); risk_level="none" → «риск —», сортировка crit→warn→none→ok;
  строки без '#', один футер «риск: derived (range/vr)»; `_STATUS_RE`
  `WARNING|WARN` / `CRITICAL|CRIT` + группа `FRND|FOE|UNK`;
  `_style_for_token`: frnd→ok / unk→warn / foe→crit; `.mfd-active` =
  фон/цвет без рамки; `MFD_PAGE_SWITCH_SUBTITLE_LEFT/RIGHT`; кнопки
  «Панель ▲ / Справка H / Панель ▼», «Справка · ON/OFF»; `sim.pause` из
  STOPPED → `return False`; 3 смок-стаба приняли `command_id`.

## Impact Metric

- Метрика: RED/пин-тесты пакета + живой prove этапа 6.
- Baseline: `test_zero_values_render_honestly`,
  `test_missing_kinematics_show_unknown_risk`, `test_ui_polish.py` (4),
  `test_pause_from_stopped_is_rejected` — RED на коде до фиксов;
  спуф-смок падал TypeError.
- Target/Actual: все новые/обновлённые тесты зелёные; спуф-смок (M5)
  живьём PASS; `prove_orion_v_f1_radar_page.sh` **EXIT=0** (после
  канонного `sim.stop`); полный `tests/unit` **0 FAILED**; ruff-дифф чист.

## Scope / Non-goals

- In scope: radar_page_view_model.py, shared/radar_risk.py (guard),
  ui_rich.py, screens/cockpit.py (подписи/кнопки), screens/systems.py
  (.mfd-active), q_sim_service/service.py (pause-из-STOPPED), 3 смок-стаба,
  тесты пакета.
- Out of scope (хвосты, зафиксированы в STATUS/борде): MED пауза↔xpdr
  рассинхрон; MED staleness страницы РАДАР (треки после sim.stop вечно
  «живые» до LOST); LOW `_on_track` без refresh; LOW консольный FIFO;
  LOW «охват 360°» на target/sensors; UI P2 (ACTION RAIL спаны, MFD-CSS
  дедуп, F2 border_title) и P3 (header ANSI, margin, приглушение
  подсказки, глифы); pre-existing фейлы thermal/combat смоков на
  deny-гейте unsolicited (падают до стабов).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/dev/AUDIT_2026-07-09_POSTFIX.md` (карта пост-фикс аудита)
  - `TASKS/TASK_20260709_f1_radar_page.md` (этап 6 — база этого среза)

## Plan (steps)

1) Двойное субагент-ревью (код + UI/UX), сверка находок глазами. [сделано]
2) RED-тесты на HIGH/честность → фиксы → GREEN. [сделано]
3) Живой prove (sim.stop канонной командой → EXIT=0) + досье + гейты +
   коммит + main. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence (commands → output)

1. Юниты пакета: `test_f1_radar_page.py` (18) + `test_ui_polish.py` (2
   теста / 6 ассертов стилей) + `test_radar_honesty_2.py` (6) +
   `test_f1_decompress.py` — зелёные; полный `tests/unit` — 0 FAILED.
2. Спуф-смок M5 после починки стаба — живьём PASS (deny-контракт
   проверяется, а не TypeError).
3. Живой prove этапа 6 (мир был RUNNING — остановлен канонной
   `sim.stop` через `qiki.commands.control`, FAILED_PRECONDITION
   подтверждён):

```
[smoke] STOPPED: «эфир чист | охват 360° | режим: НАВИГАЦИЯ» ✓
[smoke] трек на странице РАДАР: 1 ALLY-SMK001 | пеленг 042° | дальн 1200 м | скор -12.0 м/с | IFF FRND | кач 0.91 | риск WARN t_cpa=100с
[smoke] LOST(status=3) выселил трек — эвикция жива ✓
[smoke] Этап 6 PASS: страница РАДАР честна на живом стеке
```

4. Живой кадр консоли (до prove, мир RUNNING) показал фикс falsy-zero
   глазами: « 1 ALLY-29F73D | пеленг 000° | дальн 3500 м | … | риск OK»
   — нулевой пеленг рендерится «000°», не «—»; футер
   «риск: derived (range/vr)» один на страницу.
