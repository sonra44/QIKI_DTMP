# TASK: Радар-честность-2 — гейт ротации, LRU-эвикция, чистое владение

**ID:** TASK_20260709_RADAR_HONESTY_2
**Status:** in_progress
**Owner:** Claude (CLI-агент), срез 2 карты `AUDIT_2026-07-09_POSTFIX.md`
**Date created:** 2026-07-09

## Goal

Закрыть радарные MED пост-фикс аудита до этапа 6 («страница РАДАР»):
M4 — ротация сенсоров кормила мозг радаром у остановленного/обесточенного
сима; M6 — эвикция сенсоров в мозге была FIFO и выселяла живой сенсор под
флудом; LOW — пустой кадр своего сенсора оставлял висячие id во владении.

## Operator Scenario (visible outcome)

- Кто выполняет: operator
- Что честнее: до `sim.start` (и при обесточке радара) мозг не видит
  контактов ВООБЩЕ — ни через GetRadarFrame (это был этап 2), ни через
  GetSensorData-ротацию (закрыто здесь); при флуде «плавающих» sensor_id
  живой контакт не мерцает (нет разрыва идентичности трека и перевыпуска
  гвардов).
- Ограничение: staleness-механизм треков (M5) и field_sources→телеметрия
  (M8) — следующие срезы карты.

## Reproduction Command

```bash
docker exec qiki-dev-phase1 python -m pytest tests/unit/test_radar_honesty_2.py -q
```

## Before / After

- Before: `tick()` при STOPPED/PAUSED гоняет `step(0.0)` «keep sensor data
  alive», и ветка RADAR ротации проверяла только `radar_enabled` — контакты
  текли в мозг у остановленного и обесточенного сима (доказано живым
  прогоном аудитора); эвикция сенсоров — FIFO по первой вставке: сенсор с
  дрейфующим контактом (кадры не перематчиваются) вечно сидел в голове
  словаря и выселялся флудом (у аудитора — на 15-м раунде); после пустого
  своего кадра набор владения хранил висячие id и занимал слот кэпа.
- After: `_radar_rotation_allowed()` = radar_enabled ∧ _sim_running ∧
  radar_allowed — радарный слот ротации при гейте отдаёт LIDAR-чтение
  (пауза радар НЕ глушит: мир заморожен, timestamp стоит — потребители
  честно видят несвежесть, согласовано с external-read); владение сенсора
  снимается pop'ом целиком перед перевставкой — LRU-позиция освежается
  каждым кадром, пустой кадр освобождает слот, висячие id не переживают
  кадр.

## Impact Metric

- Метрика: RED-тесты контракта (`test_radar_honesty_2.py`).
- Baseline: 4 failed + 1 пин (STOPPED/обесточка кормили ротацию; live-сенсор
  ловил разрывы идентичности под флудом; висячий слот).
- Target/Actual: **5 passed**; смежные радарные (block0_radar_ingest,
  radar_guards, radar_generation) — зелёные; полный `tests/unit` 0 FAILED.

## Scope / Non-goals

- In scope: M4 (`q_sim_service/service.py`), M6+LOW
  (`q_core_agent/core/world_model.py`), синхронная адаптация
  `test_generate_sensor_data_produces_radar_when_enabled` (RUNNING по гейту).
- Out of scope: M5 (staleness/TTL треков — требует канона свежести), M8,
  LOW-пакет карты; флак длинного прогона live-смока (см. Evidence 4).

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/dev/AUDIT_2026-07-09_POSTFIX.md` (M4/M6/LOW, порядок починки)
  - `TASKS/TASK_20260709_block0_radar_ingest.md` (этап 2 — первая половина 0.9)

## Plan (steps)

1) RED-тесты (5 шт.; M6 — через ассерт непрерывности live-контакта под
   флудом, финальный «жив ли» маскировал разрыв). [сделано]
2) Фиксы: гейт ротации + pop-перевставка владения. [сделано]
3) Живой тест + досье + гейты + коммит + main. [этот шаг]

## Definition of Done (DoD)

- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (это досье)
- [x] Операционный сценарий воспроизводится по `Reproduction Command`
- [x] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean — после коммита среза

## Evidence (commands → output)

1. RED: `4 failed, 1 passed`; GREEN после фиксов: `5 passed`; спуф-контракт
   и этап-2 контракты целы (block0_radar_ingest 7 + radar_guards 12 +
   radar_generation зелёные); полный `tests/unit`: **0 FAILED**; ruff чист.
2. Живой тест M4 (рестарт sim+intents на новый код, канонный STOPPED):

```
[live] типы чтений при STOPPED: [1, 2, 1, 1, 1] | RADAR = 6
[live] M4: остановленный сим не кормит мозг радаром ✓
[live] GetRadarFrame при STOPPED: FAILED_PRECONDITION ✓
```

3. Живой позитивный путь (RUNNING): смок `orion_v_radar_track_visible_smoke`
   3/3 цикла с радаром (чтения [3,3,2]), «0 треков при живом контакте» = 0;
   мир возвращён в STOPPED (FAILED_PRECONDITION подтверждён).
4. Флак среды (зафиксирован, вне scope): длинный прогон смока (12 циклов)
   дважды умер с EXIT=137 без вывода (не OOM: 11 GB available, OOMKilled
   false); короткий (3 цикла) стабильно PASS. Расследовать отдельно.
