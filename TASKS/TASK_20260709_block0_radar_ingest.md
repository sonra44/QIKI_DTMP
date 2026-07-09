# TASK: Блок 0 «радар» — refresh-ротация, per-sensor треки, гейт GetRadarFrame

**ID:** TASK_20260709_BLOCK0_RADAR_INGEST
**Status:** in_progress
**Owner:** Claude (CLI-агент), этап 2 пакета `orion_playable_f1_f5_v1`
**Date created:** 2026-07-09

## Goal

Радар честен для мозга (дефекты 0.1 / 0.2 / 0.9): refresh не теряет радар в
ротации сенсоров, кадр одного радара не сносит треки другого, внешнее чтение
кадра гейтится состоянием сима.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что стало честнее: «Наблюдение» (P2) живо — мозг видит радарные треки на
  (почти) каждом refresh, после рестарта мозга трек возвращается сам; при
  STOPPED/обесточенном радаре контактов не бывает; на паузе — замороженный
  последний кадр, не свежая генерация.
- Ограничение: один цикл = один сценарий (этот — радарный ingest; страница
  РАДАР на F1 — этап 6).

## Reproduction Command

```bash
bash scripts/prove_orion_v_radar_track_visible.sh
```

## Before / After

- Before: refresh мозга получал одно чтение из ротации [LIDAR→RADAR→IMU] с
  очередью=1 (~2/3 refresh без радара; «0 целей» при живом контакте); пустой
  кадр любого радара сносил ВСЕ треки (глобальный `_frame_derived_track_ids`);
  sensor_id радара в симе = uuid4 на кадр («каждый кадр — новый радар»);
  GetRadarFrame отдавал свежие контакты от остановленного/выключенного/
  обесточенного сима.
- After: refresh дочитывает ротацию до радара (≤3 чтений, ранний выход);
  владение треками ключуется по сенсору при глобальном матчинге (кросс-
  сенсорная непрерывность идентичности — спуф-контракт — сохранена, с
  переносом владения); sensor_id радара стабилен между кадрами и рестартами
  (uuid5-константа); GetRadarFrame: STOPPED/выкл/обесточен →
  FAILED_PRECONDITION, пауза → последний опубликованный кадр.

## Impact Metric

- Метрика: доля refresh-циклов с радарными данными; «0 целей при живом
  контакте».
- Baseline: ~33%; случаи есть (доказано аудитом живым прогоном).
- Target: ≥95%; 0 случаев (полный 30-мин замер — этап 11, разнос by design,
  раунд 003).
- Actual (выборка live-смока, 12 циклов при конкуренции с живым мозгом):
  **100% (12/12), радар за 2-3 чтения, «0 треков при контакте» = 0**.

## Scope / Non-goals

- In scope: 0.1 (`agent._ingest_sensor_data`), 0.2
  (`q_core_agent/core/world_model.py` + стабильный `_radar_sensor_id` сима),
  0.9 (`radar_frame_for_external_read` + gRPC-гейт); live-смок + prove-скрипт.
- Out of scope: страница РАДАР F1 (этап 6), derived-риск (этап 6), range_band
  gRPC-кадров и JetStream-инфра (out-of-scope Блока 0), 30-мин гейт (этап 11),
  0.6-0.8/0.11 (этап 3). Pre-existing красные вне scope (см. Evidence 6).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/design/operator_console/orion_playable_f1_f5_v1/02_BLOCK0_DEFECT_BASELINE.md` (0.1/0.2/0.9)
  - `docs/design/operator_console/orion_playable_f1_f5_v1/08_VERIFICATION_PLAN.md` (этап 2)
  - `docs/design/operator_console/orion_playable_f1_f5_v1/_support/CLARIFICATION_REPLY_003.md` (A12: стек = phase1.yml)
  - `docs/dev/AUDIT_2026-07-09_GLOBAL.md` (радарный след дня)

## Plan (steps)

1) RED-тесты контракта (`tests/unit/test_block0_radar_ingest.py`, 7 шт.) —
   подтверждено 6 failed + 1 пин. [сделано]
2) Фиксы 0.1/0.2/0.9 + адаптация пина `test_agent.py` (call_count==3). [сделано]
3) Live-смок `tools/orion_v_radar_track_visible_smoke.py` +
   `scripts/prove_orion_v_radar_track_visible.sh` (phase1-стек, A12). [сделано]
4) Досье + гейты + коммит + PR. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье; канон не менялся)
- [x] Операционный сценарий воспроизводится по команде из `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean (`git status --porcelain`) — после коммита этапа

## Evidence (commands → output)

Docker `qiki-dev-phase1`, живой стек `docker-compose.phase1.yml` (+operator),
2026-07-09.

1. RED (до фиксов): `6 failed, 1 passed` —
   `test_empty_frame_from_other_sensor_does_not_wipe_tracks`,
   `test_cross_sensor_rematch_transfers_ownership`,
   `test_sim_radar_sensor_id_stable_across_frames_and_restarts`,
   `test_refresh_reads_rotation_until_radar`,
   `test_radar_frame_external_read_gated_by_sim_state`,
   `test_grpc_get_radar_frame_fails_precondition_when_gated`.

2. GREEN после фиксов: `7 passed`; спуф-контракт цел:
   `test_radar_guards.py` `12 passed` (кросс-сенсорная непрерывность
   идентичности трека сохранена — матчинг глобальный, снос per-sensor).

3. Полный `tests/unit`: зелёный (118 passed).

4. Live prove (`scripts/prove_orion_v_radar_track_visible.sh`, EXIT=0),
   после `docker restart qiki-sim-phase1 qiki-qcore-intents-phase1`
   (код монтируется, процессы подхватили фиксы):

```
[smoke] сим STOPPED: GetRadarFrame честно отвечает FAILED_PRECONDITION (гейт 0.9 ✓)
[smoke] sim.start (канонная операторская команда) ...
[smoke] RUNNING: кадр отдаётся (гейт открылся) ✓
[smoke] sensor_id стабилен между кадрами: e46bc6f6-b33d-5ee4-a4ee-ae47bf13509c ✓
[smoke] циклов с радаром: 12/12 (100%); чтений до радара: [2,2,3,3,3,3,2,3,2,3,3,3]
[smoke] «0 треков при живом контакте»: 0
[smoke] Этап 2 PASS: радарный ingest честен на живом стеке
```

   После прогона мир возвращён в канонное STOPPED (`sim.stop`).

5. Живая консоль (HERDR pane `w1:pW`) после рестарта operator-console:
   `M LIVE | CMD ok | P 0 | ACT standby | INC none` — без трейсбеков
   (заодно живое подтверждение этапа 1: счётчик P не завышен).

6. Pre-existing (падают на чистом 64dbe0c, проверено stash-прогоном; вне
   scope): `test_agent.py::test_qcoreagent_run_tick_updates_context` (BIOS
   proto), `test_agent.py::test_neural_engine_generates_no_proposal_when_disabled`,
   `test_radar_generation.py::test_radar_sr_threshold_env_override`,
   `test_sim_events_publishing.py::test_qsim_publishes_minimal_sim_events`.
   Кандидаты в аудит-хвосты; их починка — не этап 2.

7. Ruff по изменённым файлам: `All checks passed!`

8. Адаптация пина `test_agent.py:94` (get_sensor_data call_count 1→3) —
   следствие контракта 0.1 (фикстура отдаёт только LIDAR → полная ротация),
   аналогично адаптациям стабов этапа 1.
