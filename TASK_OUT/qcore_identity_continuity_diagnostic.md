# q-core identity continuity diagnostic

## 1. Current resumed-selection path

`resume_observation` contour state is preserved in `latest_observation_objectives` inside [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L3493). `operator_actions_handler()` applies follow-up updates by copying the existing objective payload in `_build_observation_follow_up_update()` and only changing follow-up fields, so the stored `track_id` / `track_label` from the earlier observation payload stay attached to the same contour update ([qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L238)).

When a later `safe observation ...` request arrives, q-core-intents does not create a new seed if a resumable contour exists. The request path is:

1. `handler()` detects safe observation and calls `_find_resumable_observation_objective(...)` ([qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L3530)).
2. `_find_resumable_observation_objective(...)` filters only `objective_type=observation` and `follow_up_status=resume_observation`, but matches by `target_designator`, not by previous `track_id` ([qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L201)).
3. `handler()` then warms the snapshot with `_refresh_agent_snapshot_until_target_track(...)`, passing `preferred_track_id=resumable_objective.track_id` and `previous_track_label=resumable_objective.track_label` ([qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L3273)).
4. `_build_safe_observation_response(...)` selects the runtime track again and injects `observation_track_id` / `observation_track_label` into the proposed ORION procedure via `_observation_track_snapshot(...)` ([qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L1950), [qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L719)).

Conclusion for the current code path: q-core-intents does try to preserve the previous contour `track_id` as the primary runtime identity during resumed safe observation, but only after the resumable contour has already been selected by `target_designator`.

## 2. Identity sources used by q-core-intents

There are three different identity inputs in the resumed path:

- Contour identity in the stored objective payload:
  `track_id`, `track_label`, `target_designator`, plus contour keys such as `objective_id`, `request_id`, `proposal_id` are carried forward in objective updates ([qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L238)).
- Runtime target selection in q-core-intents:
  `_select_target_track_for_resume(...)` tries `preferred_track_id` first and falls back to `target_designator` if that lookup fails ([qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L688)).
- Runtime world snapshot identity:
  `QCoreAgent._ingest_sensor_data()` stores the latest gRPC sensor payload and rebuilds `context.world_snapshot` from `WorldModel.snapshot()` ([core/agent.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/agent.py#L140)). `GrpcDataProvider.get_sensor_data()` converts either `radar_track` or `radar_frame` into `SensorData` ([core/grpc_data_provider.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/grpc_data_provider.py#L153)).

The critical q-core-local identity rule is in [core/world_model.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/world_model.py#L25):

- If gRPC delivers `sensor_data.radar_track`, q-core keeps the upstream `track.track_id`.
- If gRPC delivers `sensor_data.radar_frame`, q-core synthesizes a local `RadarTrackModel` in `_track_from_detection(...)` with:
  `track_id = uuid5(..., f"qiki-radar:{sensor_id}:{track_key}")`
  and `track_key = detection.transponder_id or f"{sensor_id}:{index}"` ([core/world_model.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/world_model.py#L119)).

That means a public-label change can change q-core-local `track_id` if q-core is ingesting radar frames rather than stable radar tracks.

## 3. Where continuity can be lost

### A. Before runtime lookup: wrong resumable contour selected

`_find_resumable_observation_objective(...)` does not require `track_id` continuity. It selects the newest `resume_observation` objective for the same `target_designator` ([qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L201)). If multiple resumed contours share a designator, q-core can pick the newest one even if it is not the intended truth object.

### B. During runtime lookup: contour-id miss causes fallback / reselection

`_select_target_track_for_resume(...)` preserves continuity only when the current `world_snapshot` still contains a track that matches the previous `track_id`. If not, q-core falls back to `target_designator` lookup ([qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L688)).

That is the first explicit place where q-core can reselect a different runtime track before ORION compares anything.

### C. In world-model identity: local track_id can be regenerated

If q-core is seeing `radar_frame` instead of stable `radar_track`, `_track_from_detection(...)` makes `track_id` depend on `detection.transponder_id` ([core/world_model.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/world_model.py#L119)). After `sim.xpdr.mode=SPOOF`, this can produce:

- old contour `track_id` no longer present in q-core snapshot, or
- a new q-core-local `track_id` with the new label, even if the truth object is the same physical target.

In that case q-core cannot preserve same-track identity through its own local snapshot space.

### D. Between q-core and ORION: label can belong to a different truth object than ORION later compares

Yes, q-core can return `observation_track_label` that is no longer tied to the same truth object ORION later uses.

This can happen if:

- q-core fell back from contour `track_id` to designator matching and selected some other visible track with the same designator;
- q-core regenerated a new local `track_id` from radar-frame detection while ORION later compares against another identity space;
- q-core never sees the changed label and returns the old label on the old track while ORION later sees different live radar state.

So the answer to the key question is precise:

- q-core-intents does use the previous contour `track_id` as its primary runtime identity on the resumed path.
- q-core-intents is still able to lose continuity locally before ORION final comparison because both contour lookup and runtime track lookup have fallback/reselection behavior.

## 4. Added diagnostic points

Temporary trace points were added only in [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py):

- `_find_resumable_observation_objective(...)` now logs:
  `target`, matched candidate count, `objective_id`, `request_id`, previous `track_id`, previous `track_label`.
- `_select_target_track_for_resume(...)` centralizes selection-source classification:
  `direct_by_contour_id`, `fallback_by_designator`, `designator_only`, `missing_after_contour_id`, `missing`.
- `_build_safe_observation_response(...)` now logs:
  `objective_id`, previous `track_id`, previous label, selected runtime `track_id`, refreshed label, selection source.
- `_refresh_agent_snapshot_until_target_track(...)` now logs on settle/timeout:
  `objective_id`, target, previous `track_id`, previous label, selected runtime `track_id`, refreshed label, selection source, radar sensor id, fresh-radar state, and whether label change was observed.

These traces satisfy the requested visibility:

- objective contour id
- previous `observation_track_id`
- selected runtime track id
- previous label
- refreshed label
- source of selection

## 5. Evidence collected

Static code evidence:

- Objective follow-up updates preserve prior contour track fields instead of rewriting them from scratch:
  [qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L238)
- Resumable objective selection is by `target_designator`, not by `track_id`:
  [qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L201)
- Runtime resume lookup prefers prior `track_id` and can fallback to designator:
  [qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L688)
- q-core world snapshot is rebuilt from ingested gRPC sensor data:
  [core/agent.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/agent.py#L140), [core/grpc_data_provider.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/grpc_data_provider.py#L153)
- q-core-local frame ingest can regenerate `track_id` from `transponder_id`:
  [core/world_model.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/world_model.py#L25), [core/world_model.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/world_model.py#L119)

Runtime evidence collected in this pass:

- `python -m py_compile src/qiki/services/q_core_agent/qiki_orion_intents_service.py` passed.
- Supported contour is live:
  `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps` showed `q-core-intents`, `q-sim-service`, `faststream-bridge`, `operator-console`, `nats`, `qiki-dev` all up on 2026-03-24 UTC.
- The existing smoke command is runnable:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev env QIKI_OBSERVATION_STYLE=slow QIKI_RESUME_XPDR_MODE=SPOOF python tools/orion_v_qiki_observation_objective_seed_smoke.py`
- On this pass the smoke failed earlier than resumed comparison:
  `AssertionError: timeout while waiting for live radar track with public designator in q_core world snapshot`

That failure matters because it means this pass did not yet produce live evidence from the new resumed-selection trace points. The next run must capture q-core-intents logs while the resumed contour is actually exercised.

## 6. Most likely q-core-local failure modes

1. `resume_observation` contour is selected correctly, but q-core world snapshot no longer contains the previous `track_id` after XPDR mutation, so q-core falls back to `target_designator` and may select a different runtime track.

2. q-core is ingesting `radar_frame` rather than stable `radar_track`, so `_track_from_detection(...)` regenerates q-core-local `track_id` from `transponder_id`; after `SPOOF-*`, the same truth object becomes a different q-core-local track identity.

3. q-core never sees a public designator at all in its current `world_snapshot`, which is consistent with the smoke failure seen in this pass. In that case resumed identity continuity cannot even be evaluated honestly yet.

4. Multiple resumable objectives may share the same `target_designator`, and `_find_resumable_observation_objective(...)` can pick the newest one without proving it is the same contour intended by the operator.

## 7. Minimal next fix task candidates

These are follow-up task candidates only. No fix was applied in this pass.

1. Run one resumed observation smoke with q-core-intents logs captured and extract the new trace lines:
   `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml logs --since=5m q-core-intents | rg "Resume objective lookup|Resume track selection|Resume warmup"`

2. Prove what q-core actually ingests on the failing contour:
   determine whether the relevant `SensorData` path is `radar_track` or `radar_frame` when the target label changes.

3. If q-core is on `radar_frame`, isolate whether `_track_from_detection(...)` should be treated as the exact q-core-local identity discontinuity point for the resumed contour.

4. If q-core is on stable `radar_track` but still falls back, isolate why the previous contour `track_id` disappears from `world_snapshot` before resumed safe observation.
