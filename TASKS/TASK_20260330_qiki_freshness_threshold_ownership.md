# TASK: QIKI freshness-threshold ownership hardening

**ID:** TASK_20260330_qiki_freshness_threshold_ownership  
**Status:** in_progress  
**Owner:** Codex / sonra44  
**Date created:** 2026-03-30  

## Goal

Вынести freshness-threshold ownership для QIKI reasoning из разрозненных service-local констант/`os.getenv(...)` в один явный canon/config contour без смены текущей игровой семантики.

## Operator Scenario (visible outcome)

- Кто выполняет: developer
- Что должно стать визуально/поведенчески понятнее в ORION:
  QIKI одинаково и предсказуемо трактует `fresh/stale/absent` для IMU, comms и station-track trust; следующий агент не гадает, какие пороги где зашиты.
- Ограничение: один цикл = один новый операционный сценарий.
  Сценарий этого цикла: один ownership pass для freshness thresholds, без расширения sensor gameplay.

## Reproduction Command

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_qiki_orion_intents_service.py -k \
  'attitude_stabilize or station_hail or current_reasoning_snapshot or merge_reasoning_snapshot'
```

## Before / After

- Before:
  freshness semantics уже работают, но ownership разнесён:
  `_COMMS_STALE_AFTER_S`, `_COMMS_EXPIRE_AFTER_S`, `_IMU_STALE_AFTER_S`, `_IMU_EXPIRE_AFTER_S`, `_RESUME_OBJECTIVE_STALE_AFTER_S` живут в `qiki_orion_intents_service.py`, а station-track trust использует отдельный `QIKI_SENSOR_MAX_AGE_S` из env.
- After:
  есть один явный ownership path для freshness thresholds этого slice; текущие значения и их роль описаны в canon/config и используются без скрытых локальных сюрпризов.

## Impact Metric

- Метрика: число freshness-gated QIKI paths в текущем slice с явным единым ownership path
- Baseline:
  `0` единых ownership entries; thresholds разнесены между inline constants и env reads
- Target:
  `3` path groups (`IMU`, `comms`, `station track / approach`) с одним явным ownership contour
- Actual (после внедрения):
  TBD

## Scope / Non-goals

- In scope:
  - inventory текущих freshness thresholds в QIKI reasoning
  - выбор одного ownership path для текущего slice
  - перенос без смены игровой семантики и без widening sensor model
  - targeted tests + doc sync
- Out of scope:
  - новый sensor-driven gameplay contour
  - provider/proto refactor
  - radar world-model redesign
  - broad config-system overhaul

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `TASKS/TASK_20260329_bot_sensor_reasoning_contract.md`
  - `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
  - `tests/unit/test_qiki_orion_intents_service.py`
  - `docs/design/canon/INDEX.md`
  - `DOCUMENTATION_UPDATE_PROTOCOL.md`

## Plan (steps)

1) Prove the current threshold split.
2) Choose one explicit ownership path for this slice.
3) Move or normalize thresholds without changing current pass/fail gameplay semantics.
4) Run narrow Docker-first regression proof.
5) Sync docs/board/memory.

## Definition of Done (DoD)

- [ ] Current threshold split is documented with evidence
- [ ] One explicit ownership path exists for IMU/comms/station freshness thresholds in this slice
- [ ] Docker-first checks passed (commands + outputs recorded)
- [ ] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` (if behavior changed)
- [ ] Операционный сценарий воспроизводится по команде из `Reproduction Command`
- [ ] Есть измеримый `Impact Metric` (baseline -> actual)
- [ ] Repo clean (`git status --porcelain` is expected)

## Evidence (commands → output)

- `rg -n "STALE_AFTER|EXPIRE_AFTER|QIKI_SENSOR_MAX_AGE_S|QIKI_SENSOR_MIN_QUALITY|freshness" src/qiki/services/q_core_agent/qiki_orion_intents_service.py`

## Notes / Risks

- Главный риск: создать второй canon/config owner вместо одного явного ownership path.
- Второй риск: незаметно изменить игровую семантику stale/deferred вместо чистого ownership hardening.

## Next

1) После этого шага выбрать, нужен ли следующий sensor-driven path вообще.
2) Не расширять `sensor_snapshot` в новый truth owner без отдельного доказательного цикла.
