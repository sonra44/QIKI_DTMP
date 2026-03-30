# q-core vs ORION truth comparison

## 1. q-core truth point

The q-core side truth point for resumed observation is the refreshed `world_snapshot` track selected during resumed safe observation preparation.

- Resumable contour lookup happens in [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L201), where `_find_resumable_observation_objective(...)` chooses a `resume_observation` contour by `target_designator` and logs `objective_id/request_id/previous_track_id/previous_label`.
- Runtime target selection happens in [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L688), where `_select_target_track_for_resume(...)` tries `preferred_track_id` first and then falls back to `target_designator`.
- Procedure parameters are built from the selected refreshed track in [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L719) and injected by `_build_safe_observation_response(...)` in [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L1950).
- Warmup visibility is provided by `_refresh_agent_snapshot_until_target_track(...)` in [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L3273), which logs `previous_track_id`, `previous_label`, selected runtime `track_id`, refreshed label, selection source, and whether label change was observed.

For this investigation, the q-core truth point is therefore:

- previous contour identity from the objective payload: `track_id/track_label`
- selected refreshed track from q-core `world_snapshot`
- procedure parameters `observation_track_id/observation_track_label` emitted from that selection

## 2. ORION truth point

The ORION side truth point is its live radar cache lookup plus the final same-contour comparison.

- `_live_observation_track_snapshot(...)` in [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py#L1666) resolves:
  - contour `previous_track_id/previous_label` from the active objective
  - q-core procedure `observation_track_id/observation_track_label` from fallback parameters
  - ORION live cache entry from `_latest_radar_tracks[track_id]`
- `_build_resume_observation_result(...)` in [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py#L1745) decides `signature_changed` only if:
  - previous `track_id == comparison track_id`
  - previous and comparison labels are both non-empty
  - previous label differs from comparison label
- The comparison path is called right before objective publication in [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py#L2163).

For this investigation, the ORION truth point is therefore:

- contour `track_id/track_label` stored on the active objective
- live track snapshot from `_latest_radar_tracks`
- comparison input actually fed into `_build_resume_observation_result(...)`

## 3. Correlation method

Correlation used one resumed contour run on the canonical stack:

- command:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev env QIKI_OBSERVATION_STYLE=slow QIKI_RESUME_XPDR_MODE=SPOOF python tools/orion_v_qiki_observation_objective_seed_smoke.py`
- follow-up ad hoc probe:
  same resumed contour path, but without early abort on the `signature_changed` precondition, so the run could print q-core procedure fields, ORION live snapshot/comparison fields, and the final objective payload.

Correlation keys:

- `objective_id`
- `request_id`
- `target_designator`
- contour `previous_track_id/previous_track_label`
- q-core selected/procedure `track_id/label`
- ORION live cache `track_id/label`

Temporary diagnostics added for this pass only:

- q-core:
  `Resume objective lookup`
  `Resume track selection`
  `Resume warmup settled`
- ORION:
  `Resume live snapshot`
  `Resume comparison`

No objective schema, q-core selection rule, or ORION decision rule was changed.

## 4. Evidence table per resumed contour run

| Run | objective_id | target | previous contour id/label | q-core after SPOOF | q-core procedure response | ORION live/comparison moment | final result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| canonical smoke + ad hoc continuation probe, 2026-03-24 UTC | `observation-267401b9-317d-4f65-95ac-098852d43fd1` | `ALLY-0F4107` | `ba9d1423-61f0-55bd-aeaf-d5eaa225a010 / ALLY-0F4107` | q-core probe after `sim.xpdr.mode=SPOOF`: selected `track_id=815cdf72-668a-5409-b15f-1d76d395c0de`, label still `ALLY-0F4107`, `same_track_id_as_previous=false` | ad hoc pre-execute probe saw `observation_track_id/label = null/null`; ORION execution-path log for the same contour still showed fallback `qcore_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`, `qcore_label=ALLY-0F4107` | ORION log: `live_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`, `live_label=missing`, source=`fallback_live_track_missing`; comparison log: `comparison_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`, `comparison_label=ALLY-0F4107`, candidate=`reconfirmed` | final objective published by ORION: `observation_result_status=reconfirmed` |

Direct evidence excerpts from this run:

- smoke failure:
  `signature_changed precondition failed: resumed contour track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010 kept label ALLY-0F4107 after sim.xpdr.mode=SPOOF`
- q-core warmup trace from the run window:
  `selected_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010 refreshed_label=ALLY-0F4107 ... label_changed=False`
- ORION comparison trace from the continuation probe:
  `previous_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010 previous_label=ALLY-0F4107 comparison_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010 comparison_label=ALLY-0F4107 result_candidate=reconfirmed`

## 5. Alignment / mismatch findings

Answer to the main question: this run does not prove that q-core and ORION are seeing the same target identity on the resumed contour. Evidence points the other way.

Findings:

- ORION kept the contour identity space on `track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`.
- q-core post-SPOOF probe selected a different runtime `track_id=815cdf72-668a-5409-b15f-1d76d395c0de` for the same public designator while keeping the same label `ALLY-0F4107`.
- ORION did not have a live cache record for the contour track at comparison time and therefore fell back to the old contour label.
- The run therefore shows a truth mismatch of identity space, not just a missing label mutation on one shared object.

What is proved:

- q-core and ORION were not aligned on a single observable `same track_id + changed label` object on this run.
- ORION compared the old contour identity against old/fallback label state and honestly returned `reconfirmed`.
- q-core had already drifted to another runtime track identity for the same designator before ORION made the final decision.

What is not proved:

- This does not yet prove whether the different q-core `track_id` is a regenerated identity for the same physical contact or a truly different truth object.
- This run also does not prove bridge as culprit; previous bridge diagnostic already showed the bridge can preserve same UUID across label mutation when association holds.

## 6. Race/timing findings

There is evidence of a timing window, but it is not a simple “same object, different freshness” race.

Observed ordering:

1. Contour before spoof still carries `previous_track_id=ba9d...`, `previous_label=ALLY-0F4107`.
2. After `sim.xpdr.mode=SPOOF` ACK, q-core probe no longer resolves the resumed contour to `ba9d...`; it resolves to `815cdf72...` with unchanged public label.
3. At ORION comparison time, ORION still keys on `ba9d...`, but live cache has no live label for that key and collapses to fallback/previous label.
4. Result becomes `reconfirmed`.

Implication:

- The dominant runtime gap is identity discontinuity before label-change evidence reaches ORION on the contour key.
- There may also be an additional timing issue around q-core procedure parameters versus ORION execute-path fallback, but that is secondary to the stronger mismatch above.

## 7. Most probable mismatch location

Most probable mismatch location:

- boundary between q-core refreshed snapshot identity and ORION live radar cache identity, with q-core-side drift happening before ORION final comparison

More precise localization:

1. q-core resumed selection/fallback path in [qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L688)
   Why: the post-SPOOF probe resolved a different runtime `track_id` than the contour `track_id`.
2. q-core refreshed snapshot truth generation consumed by `_refresh_agent_snapshot_until_target_track(...)` in [qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py#L3273)
   Why: q-core never observed `label_changed=True` on the contour track and instead drifted to another runtime identity.
3. ORION live cache lookup in [app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py#L1666)
   Why: for the contour key `ba9d...`, ORION had no live label at comparison moment and therefore could not satisfy `signature_changed`.

Current best statement with evidence:

- The mismatch is most likely upstream of ORION decision logic and downstream of the resumed contour payload: q-core refreshed identity selection does not stay on the same identity key that ORION later uses from its live track cache.

## 8. Minimal next fix task candidates

These are fix-task candidates only. No fix was applied here.

1. Prove whether q-core regenerated `815cdf72...` from a different local identity source for the same physical contact or actually switched to a different truth object.
   Narrow task:
   capture q-core `world_snapshot` tuples `(track_id, transponder_id, sensor_id, range_m)` around the SPOOF ACK for the same target.

2. Prove whether the bridge still has a same-UUID mutated label for this contour while q-core has already drifted.
   Narrow task:
   capture bridge `bridge_track_update/bridge_track_identity_mutation/bridge_track_published` lines for the exact wall-clock window of `objective_id=observation-267401b9-317d-4f65-95ac-098852d43fd1`.

3. Isolate the transient where ORION execution-path fallback shows old q-core contour identity while the ad hoc pending-action probe saw null procedure parameters.
   Narrow task:
   log the exact `action.parameters` at enqueue time and at `_execute_qiki_pending_action()` entry for the same `request_id`.

4. If candidate 1 confirms q-core local identity regeneration, create a minimal fix task narrowly scoped to preserving resumed contour identity through q-core refreshed snapshot selection.
   Do not change ORION decision rule until that identity continuity proof is complete.
