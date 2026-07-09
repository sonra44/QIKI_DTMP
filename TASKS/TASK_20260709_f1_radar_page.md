# TASK: Страница РАДАР на F1 — живые треки, derived-риск, честная пустота

**ID:** TASK_20260709_F1_RADAR_PAGE
**Status:** in_progress
**Owner:** Claude (CLI-агент), этап 6 пакета `orion_playable_f1_f5_v1`
**Date created:** 2026-07-09

## Goal

Страница «radar» левого MFD показывает живые треки
`пеленг | дальность | скорость | IFF | качество | риск(derived)` и честное
«эфир чист | охват 360° | режим: НАВИГАЦИЯ» при пустом эфире (Z4 + G5).

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что видно глазами: на F1 левый MFD «РАДАР» — строка на каждый живой контакт
  с шестью полями и риском сближения (t_cpa, помечен derived); пустой эфир —
  честная строка вместо чужой выжимки статусов. Раньше страница «radar» на F1
  вообще не получала треков (показывала «Общий статус»/«Инциденты»).
- Ограничение: один цикл = один сценарий (страница; PPI-канва — RFC-трек,
  вне этапа).

## Reproduction Command

```bash
bash scripts/prove_orion_v_f1_radar_page.sh
```

## Before / After

- Before: cockpit.set_state не получал `_latest_radar_tracks` — страница
  «radar» рисовала вырезку чужих секций body_text; systems-путь рисовал
  `label|range|bearing|q|age` без скорости/IFF/риска, пусто → «живых
  радар-треков нет»; LOST-эвикция консоли сравнивала строку «LOST», а на
  проводе status=int 3 → мёртвые треки не выселялись никогда.
- After: единый владелец страницы `radar_page_view_model.py` (оба рендер-пути);
  риск — shared-владелец `qiki/shared/radar_risk.py` (зеркало формулы
  radar_situation_engine: closing=max(0,−vr), t_cpa=range/closing; пороги
  20/8/150/5 = env-дефолты движка); wire-енумы нормализуются (int И str);
  `is_lost_status` чинит эвикцию; пусто →
  «эфир чист | охват 360° | режим: НАВИГАЦИЯ» + честная строка
  «режим — target-only метка (q-sim не отдаёт)».

## Impact Metric

- Метрика: поля трека на странице РАДАР F1; треки доходят до F1.
- Baseline: 0 полей (треки не доходили); systems-путь 4 поля без риска.
- Actual: 6 полей + t_cpa + derived-пометка на обоих путях; live-smoke
  подтверждает полную строку.

## Scope / Non-goals

- In scope: view-model + shared-риск + проводка cockpit/mfd_page_content +
  фикс LOST-эвикции + смок/prove.
- Out of scope: PPI/канва (RADAR_VISUALIZATION_RFC); унификация env-порогов
  `radar_situation_engine` на shared (движок не тронут — отдельный хвост);
  refresh-на-каждый-трек (страница обновляется телеметрическим тиком —
  осознанно, против шторма); источник режима восприятия R.L.S.M.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/design/operator_console/orion_playable_f1_f5_v1/03_F1_COCKPIT_SPEC.md` (Z4)
  - `docs/design/operator_console/F1_GAME_FIELD_REWORK.md` (G-B, G5)
  - `src/qiki/services/q_core_agent/core/radar_situation_engine.py` (референс формулы)

## Plan (steps)

1) RED-тесты (`tests/unit/test_f1_radar_page.py`, 10 шт.). [сделано]
2) `qiki/shared/radar_risk.py` + `orion_v/radar_page_view_model.py`. [сделано]
3) Проводка: app→cockpit.set_state(radar_tracks), ветка radar в
   `_compose_left_mfd_text`, делегат `_radar_track_lines`. [сделано]
4) Фикс LOST-эвикции (`is_lost_status`). [сделано]
5) Живой смок + prove + досье + гейты + main. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита этапа

## Evidence (commands → output)

1. RED: ModuleNotFoundError → по мере модулей 10/12 → 12/12; смежные пины
   зелёные (mfd_page_content_pack, mfd_page_router, radar_empty_state,
   f1_first_playable_loop — 26 passed); полный `tests/unit`: **0 FAILED**;
   ruff: 5==5 pre-existing (дифф чист).
2. Живой prove (`scripts/prove_orion_v_f1_radar_page.sh`, живой NATS/стек):

```
[smoke] STOPPED: «эфир чист | охват 360° | режим: НАВИГАЦИЯ» ✓
[smoke] трек на странице РАДАР: #1 ALLY-SMK001 | пеленг 042° | дальн 1200 м |
        скор -12.0 м/с | IFF FRND | кач 0.91 | риск WARN t_cpa=100с (derived)
[smoke] LOST(status=3) выселил трек — эвикция жива ✓
[smoke] Этап 6 PASS: страница РАДАР честна на живом стеке
```

3. Ловушка среды, обойдённая в смоке (задокументирована): рядом живёт консоль
   оператора с durable JetStream-consumer'ом — второй инстанс с тем же durable
   глохнет («consumer is already bound»); смок ставит `RADAR_TRACKS_DURABLE=""`
   (эфемерный consumer) и очищает буфер от истории стрима перед проверкой
   пустого эфира.
4. Осознанная смена (риск из плана): пустая строка делегата
   «живых радар-треков нет» → «эфир чист | охват 360°» — затрагивает и
   target/sensors-вызовы; пинов на старую строку не было.
