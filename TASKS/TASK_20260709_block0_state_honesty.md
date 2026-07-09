# TASK: Блок 0 «честность состояния» — FSM enum, актуатор, to_thread, fixture-поля

**ID:** TASK_20260709_BLOCK0_STATE_HONESTY
**Status:** in_progress
**Owner:** Claude (CLI-агент), этап 3 пакета `orion_playable_f1_f5_v1`
**Date created:** 2026-07-09

## Goal

Состояние борта не лжёт (дефекты 0.6 / 0.7 / 0.8 / 0.11): авария не читается
как пауза, провал актуатора не выглядит как «accepted», refresh не вешает
event loop NATS, fixture-константы отличимы от измерений.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что стало честнее: авария борта видна как ERROR (раньше enum-коллизия
  показывала её паузой, а правило «вылечивало» операторскую паузу в IDLE);
  мёртвый актуатор переводит агента в SAFE, а не молчит под видом «accepted»;
  ответы QIKI не подвешивают шину на時間 gRPC-таймаутов; hull=100%/rad=0.0
  в sim-truth помечены как fixture.
- Ограничение: один цикл = один сценарий (этот — state honesty P1/P3/P5).

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest tests/unit/test_block0_state_honesty.py -q
```

## Before / After

- Before: `FsmState.ERROR_STATE(4)` коэрцился в `FsmStateEnum.PAUSED(4)`
  (авария = «пауза»), а PAUSED(4) матчился правилом ERROR_STATE и «лечился»
  в IDLE; `send_actuator_command` глотал RpcError и `accepted=False` → агент
  записывал «accepted», SAFE не срабатывал; `_refresh_agent_snapshot`
  (sync gRPC+HTTP, таймауты до 10 с) и warmup-петля крутились прямо в event
  loop NATS; hull/radiation/temp_external — константы, неотличимые от
  измерений. Плюс регрессия этапа 2: warmup детектил «свежий радар» по смене
  sensor_id, который стал стабильным.
- After: явный маппинг agent↔shared доменов FSM (PAUSED — операторское
  состояние, правила его не трогают); RpcError → ConnectionError,
  отказ → ValueError (обе ветки агента ведут в SAFE/rejected честно);
  `_refresh_agent_snapshot_async` = `asyncio.to_thread` + snapshot_lock во
  всех async-путях (handler, warmup, ingest-fallback); «свежесть» радара —
  по timestamp чтения; `get_state()["field_sources"]` помечает
  hull_integrity/radiation_usvh/temp_external_c как fixture.

## Impact Metric

- Метрика: RED-тесты контракта честности (`test_block0_state_honesty.py`).
- Baseline: 8 failed (коллизия воспроизводится, RpcError глотается, loop
  блокируется, fixture неотличимы).
- Target/Actual: **8 passed**; живые доказательства — см. Evidence.

## Scope / Non-goals

- In scope: 0.6 (`fsm_handler.py`), 0.7 (`grpc_data_provider.py`), 0.8
  (`qiki_orion_intents_service.py` + timestamp-фикс warmup), 0.11
  (`q_sim_service/core/world_model.py`).
- Out of scope: прокид `field_sources` в телеметрию/консоль (потребители —
  этап 4+); разрушительный live-тест актуатора (требует умышленно убить
  q-sim под живым оператором — юниты покрывают); pre-existing «Proposal
  evaluator failed: datetime not JSON serializable» (живёт с 01:03, до
  аудит-фиксов — отдельный хвост); 22 pre-existing ruff E501 в intents.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/design/operator_console/orion_playable_f1_f5_v1/02_BLOCK0_DEFECT_BASELINE.md` (0.6-0.8, 0.11)
  - `docs/design/operator_console/orion_playable_f1_f5_v1/08_VERIFICATION_PLAN.md` (этап 3)
  - `docs/dev/AUDIT_2026-07-09_GLOBAL.md`

## Plan (steps)

1) RED-тесты (8 шт., `tests/unit/test_block0_state_honesty.py`). [сделано]
2) Фиксы 0.6/0.7/0.8/0.11 + timestamp-фикс warmup (регрессия этапа 2,
   обнаружена чтением кода при подготовке 0.8). [сделано]
3) Живой тест на phase1-стеке. [сделано]
4) Досье + гейты + коммит + PR. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита этапа

## Evidence (commands → output)

Docker `qiki-dev-phase1` + живой phase1-стек, 2026-07-09.

1. RED: `8 failed` (все три группы: FSM-коллизия ×3, актуатор ×3,
   to_thread ×1, fixture ×1). GREEN после фиксов: `8 passed`.

2. Полный `tests/unit`: зелёный. Ruff: мои файлы чистые; в intents —
   22 pre-existing E501 (тот же счёт на чистом HEAD, stash-проверено).

3. Живой тест (после `docker restart qiki-qcore-intents-phase1
   qiki-sim-phase1`, sim.start канонной командой):

   - **0.8 быстрый путь**: intent «подготовь медленное наблюдение…» через
     `qiki.intents` → ответ за **0.2 s** («Медленное наблюдение готово»).
   - **0.8 warmup-петля**: intent с несуществующей целью КОНТАКТ-9999 →
     ответ за **11.3 s**, в логах честный
     `Resume warmup timeout ... target=КОНТАКТ-9999 reason=no_match` —
     петля отработала свои 8 с в потоке и завершилась по дедлайну.
   - **0.6 живьём** (лог intents): `BIOS_ERROR: BOOTING → ERROR(5)` затем
     `ERROR_CLEARED: ERROR(5) → IDLE(2)` — авария ложится в ERROR, а не в
     PAUSED; выздоровление честное.
   - Контейнеры healthy, новых traceback'ов нет.

4. Pre-existing (НЕ этап 3): `Proposal evaluator failed: Object of type
   datetime is not JSON serializable` — первое вхождение в логах intents
   **01:03** (код до аудит-фиксов); изолированные прогоны rule/neural engine
   с radar/lidar SensorData проходят — падение в более полном live-контексте,
   требует отдельной локализации. Хвост зафиксирован.

5. Timestamp-фикс warmup: «свежий радар» определялся сменой sensor_id;
   после стабилизации sensor_id (этап 2) детектор ослеп бы навсегда
   (8 с таймаута на каждом slow-observation). Заменён на timestamp чтения
   (уникален на кадр). Обнаружено чтением кода до всплытия в рантайме.
