# TASK: Bot Sensor Reasoning Contract

**ID:** TASK_20260329_bot_sensor_reasoning_contract  
**Status:** done  
**Owner:** Codex  
**Date created:** 2026-03-29  

## Goal

Убрать разрыв между raw sensor ingest и reasoning внутри `q_core_agent`: ввести один truth-backed sensor snapshot для non-radar sensor logic без ломки текущего radar/guard path.

## Operator Scenario (visible outcome)

- Кто выполняет: operator / developer
- Что должно стать визуально/поведенчески понятнее в ORION:
  QIKI больше не отвечает так, будто IMU/другие telemetry-backed сенсоры “отсутствуют”, когда они реально есть в canonical telemetry contour.
- Ограничение: один цикл = один новый операционный сценарий.
  Первый сценарий: `attitude stabilize` / IMU-backed reasoning.

## Reproduction Command

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps
```

## Before / After

- Before:
  `q_core_agent` получает `SensorData`, сохраняет `latest_sensor_data` и кладет payload в `bot_core`, но `context.world_snapshot` после ingest перезаписывается radar-only snapshot из `q_core_agent.core.world_model`. QIKI-код уже пытается читать `sensor_plane.*` из `world_snapshot`, что делает non-radar sensor reasoning частично разорванным.
- After:
  `q_core_agent` имеет отдельный bot-facing `sensor_snapshot` owner для telemetry-backed subsystem/sensor truth. Radar path остается в `world_model`, а IMU-first QIKI reasoning читает sensor truth из правильного snapshot.
  Дополнительно live merged telemetry path теперь различает `fresh`, `stale`, `absent` для отдельных telemetry-backed sections вместо неявного доверия последнему кэшу.

## Impact Metric

- Метрика: число QIKI decision paths, которые используют truth-backed non-radar sensor state без ложного `NO_DATA`
- Baseline:
  `1` path already attempts it (`attitude stabilize`), but the data contract is inconsistent
- Target:
  `1` fully corrected path (`attitude stabilize`) on the canonical contour
- Actual (после внедрения):
  `1` path migrated in this loop: `attitude stabilize` now accepts a separate bot-facing `sensor_snapshot`

## Scope / Non-goals

- In scope:
  - подтвердить текущий sensor ingest / reasoning contract в `q_core_agent`
  - ввести единый owner для bot-facing non-radar sensor snapshot
  - перевести `attitude stabilize` path на новый snapshot
  - сохранить текущий radar guard / track pipeline без функциональных изменений
  - добавить targeted tests для нового snapshot path
- Out of scope:
  - полная переработка всех sensor-driven QIKI paths
  - перевод всех сенсоров в gRPC `SensorReading`
  - ORION UI redesign
  - cleanup/удаление `ShipCore` в этом цикле
  - sensor fusion / perception overhaul

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Related docs/code:
  - `docs/qiki_sensor_audit.md`
  - `TASKS/TASK_20260202_sensor_plane_parameter_map.md`
  - `src/qiki/services/q_core_agent/core/agent.py`
  - `src/qiki/services/q_core_agent/core/world_model.py`
  - `src/qiki/services/q_core_agent/core/bot_core.py`
  - `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
  - `src/qiki/services/q_sim_service/core/world_model.py`

## Plan (steps)

1) Prove the current split explicitly.
   - Confirm with code and one targeted test note that:
   - `latest_sensor_data` and `bot_core` ingest all fetched sensor payloads.
   - `world_model` only reasons over `RADAR`.
   - `qiki_orion_intents_service` already expects `sensor_plane.imu` in at least one path.

2) Introduce one bot-facing sensor snapshot owner.
   - Add a focused module in `q_core_agent/core/` for telemetry-backed sensor/subsystem truth.
   - Keep it narrow: `attitude`, `sensor_plane`, and only the minimum metadata needed for reasoning.
   - Do not fold radar tracks into this owner.

3) Extend `AgentContext`.
   - Add `sensor_snapshot` as a separate field from `world_snapshot`.
   - Preserve current `world_snapshot` semantics for radar/guards.

4) Wire population on refresh/tick.
   - Populate `sensor_snapshot` from the authoritative provider-side truth for the canonical contour.
   - If provider truth is absent, record explicit absence instead of silently synthesizing values.

5) Migrate one QIKI path only.
   - Update `_build_attitude_stabilize_response()` to read IMU/attitude truth from `sensor_snapshot`.
   - Keep all other paths unchanged in this cycle.

6) Add targeted tests.
   - Positive path: IMU telemetry present -> no false `IMU_STATE_NO_DATA`.
   - Negative path: IMU telemetry absent -> deferred/trust response remains explicit and correct.
   - Regression: radar guard path behavior remains unchanged.

7) Validate on canonical contour.
   - Run Docker-first checks for the narrow slice.
   - Record exact commands and outputs in this dossier.

8) Decide next expansion only after proof.
   - If successful, choose one next sensor-backed QIKI path (radiation or star tracker).
   - Do not expand scope in the same loop.

## Definition of Done (DoD)

- [x] Current split between raw sensor ingest, radar world model, and QIKI reasoning is documented with evidence
- [x] A single bot-facing `sensor_snapshot` owner exists in `q_core_agent`
- [x] `AgentContext` keeps `sensor_snapshot` separate from radar `world_snapshot`
- [x] `attitude stabilize` QIKI path uses the new snapshot
- [x] Targeted tests cover IMU-present and IMU-absent behavior
- [x] Targeted tests cover stale-vs-fresh behavior for at least one comms path and one IMU path
- [x] Radar world model / guard path remains behaviorally unchanged for the migrated slice
- [x] Docker-first checks passed (commands + outputs recorded)
- [x] Docs updated per `DOCUMENTATION_UPDATE_PROTOCOL.md` if behavior/contract changed
- [ ] Repo clean (`git status --porcelain` is expected)

## Evidence (commands → output)

- Initial proof commands to record in this task:
  - `rg -n "latest_sensor_data|world_snapshot|sensor_plane|ingest_sensor_data" src/qiki/services/q_core_agent -S`
  - `pytest -q src/qiki/services/q_core_agent/tests/test_grpc_data_provider_truth_absence.py`
  - targeted unit tests for the migrated QIKI path
- This loop:
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps`
    - canonical stack was up; `qiki-dev`, `q-sim-service`, `q-core-intents`, `operator-console`, `nats`, and support services were running
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py -k attitude_stabilize`
    - `5 passed`
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py -k 'station_hail or merge_reasoning_snapshot or attitude_stabilize'`
    - `9 passed`
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py -k 'current_reasoning_snapshot or merge_reasoning_snapshot or station_hail or attitude_stabilize or safe_observation or slow_observation'`
    - `16 passed`
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py -k 'station_hail or attitude_stabilize or current_reasoning_snapshot or merge_reasoning_snapshot or safe_observation or slow_observation'`
    - `18 passed`
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py -k 'run_orion_intents_loop_station_hail or station_hail or attitude_stabilize'`
    - `11 passed`
    - includes a narrow live-loop proof: stale `SYSTEM_TELEMETRY` makes `hail station` return `COMMS_STATE_STALE`, then fresh telemetry flips the same path to `COMMS_CHANNEL_READY`
  - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml exec -T qiki-dev pytest -q tests/shared/test_sensor_converters.py tests/unit/test_qiki_orion_intents_service.py -k 'sensor_timestamp or update_sensor_snapshot_records_imu_timestamp_metadata or attitude_stabilize or run_orion_intents_loop_station_hail or station_hail'`
    - `13 passed`
    - proves raw sensor timestamp preservation through proto conversion and storage in `sensor_snapshot`

## Notes / Risks

- Main risk: introducing a second truth owner instead of a narrow reasoning snapshot.
- `ShipCore` is present in the repo but should be treated as legacy/support for this cycle, not as the canonical owner of current QCore sensor truth.
- If provider-side telemetry truth is not already available at the agent boundary, the task may need a small provider contract extension before the reasoning patch.
- Current implementation in this loop is intentionally IMU-first and uses a bot-facing `sensor_snapshot` filled from truthful raw IMU `SensorData`; it does not yet introduce a full telemetry-snapshot provider contract for all non-radar subsystems.
- Follow-up risk discovered during double-check: live `safe/slow observation` originally computed `reasoning_snapshot` before radar warmup, which could leave those responses on stale merged state. Fixed in this loop by recomputing a fresh reasoning snapshot after warmup before builder execution.
- Freshness contract added in this loop:
  - `station hail / comms` now defers on stale telemetry instead of treating old comms data as current truth.
  - `attitude stabilize / IMU` now defers on stale telemetry instead of treating old IMU data as current truth.
  - The contract uses existing fields only: `ts_unix_ms`, `timestamp`, `last_seen_ts`, `age_s`.
  - Raw IMU path is no longer timestamp-blind: `SensorData` now carries `timestamp`, proto<->pydantic conversion preserves it, and `sensor_snapshot` writes `timestamp`, `ts_epoch`, `ts_unix_ms`, and `sensor_plane.last_seen_ts`.
  - Critical review follow-up fixed the remaining false-trust gap:
    - raw `sensor_snapshot` no longer writes a frozen `sensor_plane.age_s=0.0`;
    - freshness now prefers timestamps over cached age fields and treats missing freshness evidence as `absent`, not `fresh`;
    - missing proto sensor timestamps now normalize to Unix epoch instead of `now()`, so absent freshness evidence degrades trust instead of fabricating a fresh reading;
    - `_build_attitude_stabilize_response()` now merges partial `sensor_snapshot` over `world_snapshot` instead of discarding richer world attitude fields.

## Critical review closeout (2026-03-29)

- Hard review found that the first timestamp fix was necessary but insufficient:
  - `sensor_snapshot` still stored a static `age_s=0.0`, which kept old IMU snapshots permanently fresh.
  - missing proto timestamps were being converted to `datetime.now()`, which falsely marked missing freshness evidence as current data.
  - partial `sensor_snapshot` payloads could override richer `world_snapshot` attitude state.
- Follow-up fix in this loop closed those three issues and added regression coverage for each.
- Current state after the fix:
  - comms freshness path remains green;
  - raw IMU freshness now degrades correctly from timestamps;
  - partial raw sensor snapshots no longer erase world attitude fields.

## Next

1) Decide whether to move freshness thresholds out of service-local constants into canon/config ownership.
2) If another sensor-driven path is needed, prefer a narrow telemetry-native path with operator value instead of widening raw `sensor_snapshot`.
3) Keep `world_model` radar-owned; do not widen `sensor_snapshot` into a second canon or start a provider/proto refactor before more proof exists.
