# TASK: Staleness радар-треков (M5) + пауза↔xpdr один мир + честный возраст на консоли

**ID:** TASK_20260709_RADAR_STALENESS
**Status:** in_progress
**Owner:** Claude (CLI-агент), срез task-0044 (конвейерная часть карты `AUDIT_2026-07-09_POSTFIX.md`)
**Date created:** 2026-07-09

## Goal

Закрыть три родственные дыры честности возраста радарных данных:
M5 карты — треки замолчавшего сенсора в мозговой WorldModel бессмертны
(фантом в guard-зоне держит вечный critical-гвард); MED пост-ревью —
на паузе ротация сенсоров и внешнее радар-чтение отдавали РАЗНЫЕ миры
(свежая генерация с живым xpdr против замороженного кадра); MED пост-ревью —
консольные `_latest_radar_tracks` вечно живые до LOST (после sim.stop
страница РАДАР показывает призраков как живые контакты).

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что видно: контакт, по которому перестали приходить данные, через 5с
  получает пометку «уст Nс» прямо в строке трека; через 30с он исчезает из
  рядов с честным футером «скрыто устаревших: N (нет данных > 30с)» — и
  страница НЕ врёт «эфир чист» (данных нет ≠ целей нет). На паузе смена
  режима транспондера не «просачивается» в замороженный мир: мозг и внешние
  потребители видят один кадр.
- Что честнее под капотом: critical-гвард фантома умершего сенсора
  снимается эвикцией и на чистом чтении гвардов (путь agent.py), не только
  при новом ingest'е.

## Reproduction Command

```bash
bash scripts/prove_orion_v_radar_staleness.sh
```

## Before / After

- Before: у мозговой WorldModel не было времени приёма трека — контакт
  замолчавшего сенсора жил вечно (аудиторский «призрак пережил 1000
  кадров»); ротация `generate_sensor_data` звала `generate_radar_frame()`
  напрямую, минуя паузную ветку `radar_frame_for_external_read` — на паузе
  после `sim.xpdr.mode SPOOF` ротационный кадр нёс SPOOF-id, внешнее чтение
  — старый ALLY-id (живой прогон ревью); консольный view-model не знал
  возраста приёма (wire `age_s` — всегда 0.0, дефолт модели) — треки после
  sim.stop оставались «живыми» до LOST, который уже не придёт.
- After: пороги свежести — единый shared-владелец
  `qiki/shared/radar_freshness.py` (stale 5с / dead 30с — зеркало дефолтов
  `sensor_runtime.freshness`, канон-грунт RAG: BODY_CANON §17 требует
  freshness/stale data, численный TTL — инженерный); мозг штампует
  `_track_last_ingest_ts` и выселяет мёртвые треки во всех читающих точках
  (snapshot/active_radar_tracks/guard_results/most_critical_guard + ingest)
  с пересчётом гвардов; ротация читает кадр через
  `radar_frame_for_external_read()` — пауза для всех потребителей одна;
  консольный view-model считает возраст по `_orion_received_at_unix_s`:
  stale → «| уст Nс», dead → скрыт + счётчик, «эфир чист» — только когда
  контактов не было вообще; `mfd_page_content._radar_track_lines` передаёт
  `now_unix_s` (без него свежесть была бы мертва на systems/target/sensors).

## Impact Metric

- Метрика: RED-тесты контракта (`tests/unit/test_radar_staleness.py`).
- Baseline: 8 failed (ротация на паузе несла свежий кадр с живым xpdr;
  мозговые треки бессмертны; консоль не помечала и не скрывала устаревшее).
- Target/Actual: **12 passed** (включая гвард фантома: стоял → умер с
  треком); смежные пины (f1_radar_page 18 + mfd_page_content_pack +
  radar_honesty_2 + radar_guards q_core) зелёные; полный `tests/unit`
  **0 FAILED**; ruff чист; live prove **EXIT=0**.

## Scope / Non-goals

- In scope: `qiki/shared/radar_freshness.py` (новый владелец),
  `q_core_agent/core/world_model.py` (M5), `q_sim_service/service.py`
  (ротация → external-read), `radar_page_view_model.py` +
  `mfd_page_content.py` (консоль), смок + prove.
- Out of scope: LOW-пакет радарной зоны (консольный FIFO-кэп по вставке,
  `_on_track` без refresh, «охват 360°» на target/sensors, смок-допущение
  FAILED_PRECONDITION=STOPPED) — следующий срез; UI P2/P3; M8
  (field_sources → телеметрия); env-ручки порогов свежести (константы
  сознательно без env до реальной нужды).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/dev/AUDIT_2026-07-09_POSTFIX.md` (M5, рекомендация «конвейерные»)
  - `TASKS/TASK_20260709_post_review_polish.md` (источник MED-находок)
  - RAG-грунт: BODY_CANON §17 (freshness/stale data), bot_gdd.md (трекинг)

## Plan (steps)

1) RAG-гейт канона свежести + разведка владельцев (sensor_runtime,
   radar_fusion.max_age_s, radar_pipeline «immortal targets»). [сделано]
2) RED-тесты (8 failed зафиксированы) → фиксы → 12 GREEN + смежные. [сделано]
3) Live prove + досье + гейты + коммит + main. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence (commands → output)

1. RED: 8 failed / GREEN: 12 passed; полный `tests/unit` 0 FAILED; ruff
   «All checks passed!».
2. Live prove (qiki-sim-phase1 рестартован на новый код, канонный STOPPED
   на входе и выходе):

```
[smoke] ПАУЗА: ротация и внешнее чтение несут один замороженный кадр ['', 'ALLY-FCE99B'] ✓
[smoke] xpdr SPOOF на паузе НЕ просочился в кадры (рассинхрон закрыт) ✓
[smoke] мир возвращён в STOPPED (FAILED_PRECONDITION) ✓
[smoke] консоль: свежий трек ALLY-STALE1 на странице РАДАР ✓
[smoke] живое устаревание (> 5с): 1 ALLY-STALE1 | пеленг 010° | ... | риск OK | уст 5с ✓
[smoke] dead-трек скрыт: «скрыто устаревших: 1», без ложного «эфир чист» ✓
```

3. Пометка «уст 5с» получена ЧЕСТНЫМ ожиданием (реальные 5+ секунд без
   данных); dead-ветка — прозрачный бэкдейт `_orion_received_at_unix_s`
   (не ждать 30с в смоке; сам порог покрыт юнитами).
