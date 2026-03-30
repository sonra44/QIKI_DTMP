# ORION pre-comparison diagnostic

## 1. Current ORION comparison path

Resumed contour path in ORION V is:

1. `_on_track()` stores live `qiki.radar.v1.tracks` payloads in `_latest_radar_tracks`.
2. `_execute_qiki_pending_action()` resolves the active resumed objective, then calls `_live_observation_track_snapshot(...)`.
3. `_live_observation_track_snapshot(...)` chooses the comparison track in this order:
   - active objective `track_id`
   - fallback q-core procedure `observation_track_id`
4. `_execute_qiki_pending_action()` writes the returned snapshot back into `result_parameters`.
5. `_build_resume_observation_result(...)` performs the final predicate:
   - `signature_changed` only when `previous_track_id == comparison_track_id`
   - and both labels are non-empty
   - and labels differ
6. Otherwise ORION returns `reconfirmed`.

Current code points:

- `src/qiki/services/operator_console/orion_v/app.py`
  - `_on_track()`
  - `_live_observation_track_snapshot()`
  - `_build_resume_observation_result()`
  - `_execute_qiki_pending_action()`

## 2. Live cache sources

ORION live cache is local to `OrionVApp`:

- `_latest_radar_tracks: dict[str, dict[str, Any]]`
- filled only by `_on_track()` from NATS `qiki.radar.v1.tracks`
- deleted when incoming `status == LOST`

Current objective / resume state used by comparison:

- `_active_observation_objective`
  - updated in `_on_event()` from `qiki.events.v1.operator.objectives`
- q-core fallback procedure parameters
  - `observation_track_id`
  - `observation_track_label`
  - `observation_track_range_m`
  - `observation_track_quality`

Important detail:

- ORION comparison is not against q-core world snapshot directly.
- ORION compares the active contour payload against either:
  - live `_latest_radar_tracks[track_id]`, or
  - fallback procedure parameters when live cache cannot provide usable data.

## 3. Added pre-comparison diagnostics

Minimal diagnostic logging was added only in `src/qiki/services/operator_console/orion_v/app.py`.

### 3.1 Live cache enrichment

`_on_track()` now stores:

- `_orion_source_timestamp_unix_s`
  - parsed from track payload / envelope timestamp when available
- `_orion_received_at_unix_s`
  - local ORION receive time

### 3.2 Snapshot log before comparison

`_live_observation_track_snapshot()` now logs:

- `objective_id`
- `request_id`
- `target`
- `previous_track_id`
- `previous_label`
- `qcore_track_id`
- `qcore_label`
- `live_track_id`
- `live_label`
- `source`
- `source_ts`
- `freshness_s`
- `label_source`

Branches are now distinguishable:

- `source=fallback_missing_track_id`
- `source=fallback_live_track_missing`
- `source=live_cache`

Empty-label behavior is now visible:

- if live track exists but label is empty, ORION keeps `source=live_cache` and records `label_source=fallback_parameters`

### 3.3 Final comparison log

`_build_resume_observation_result()` now logs directly before decision:

- `objective_id`
- `request_id`
- `target`
- `previous_track_id`
- `previous_label`
- `comparison_track_id`
- `comparison_label`
- `comparison_source`
- `comparison_label_source`
- `comparison_source_ts`
- `comparison_freshness_s`
- `result_candidate`
- `fallback_reason`

`fallback_reason` values now isolate why ORION did not choose `signature_changed`:

- `missing_previous_track_id`
- `missing_comparison_track_id`
- `track_id_mismatch`
- `missing_previous_label`
- `missing_comparison_label`
- `label_unchanged`
- `not_applicable` for the `signature_changed` branch

Decision rule itself was not changed.

## 4. Evidence from run(s)

### 4.1 Proven comparison evidence from earlier resumed contour run

Existing live evidence from the same day remains the latest completed resumed-contour comparison evidence:

- objective:
  - `objective_id=observation-267401b9-317d-4f65-95ac-098852d43fd1`
  - `target=ALLY-0F4107`
- previous contour payload:
  - `track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `track_label=ALLY-0F4107`
- ORION snapshot evidence:
  - `live_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `live_label=missing`
  - source fell back to previous/q-core label
- ORION comparison evidence:
  - `comparison_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `comparison_label=ALLY-0F4107`
  - `result_candidate=reconfirmed`
- final contour update:
  - `observation_result_status=reconfirmed`

This evidence is already summarized in:

- `TASK_OUT/qcore_vs_orion_truth_comparison.md`

### 4.2 Upstream corroboration from q-core logs

Current q-core logs still show resumed selection staying on unchanged label for the contour key:

- `Resume objective lookup`
  - `objective_id=observation-267401b9-317d-4f65-95ac-098852d43fd1`
  - `previous_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `previous_label=ALLY-0F4107`
- `Resume warmup settled`
  - `selected_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `refreshed_label=ALLY-0F4107`
  - `label_changed=False`
- `Resume track selection`
  - `selected_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `refreshed_label=ALLY-0F4107`

### 4.3 Current verification run in this pass

What was executed now:

- unit:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_orion_v_qiki_loop.py`
  - result: passed
- live smoke:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev env QIKI_OBSERVATION_STYLE=slow QIKI_RESUME_XPDR_MODE=SPOOF python tools/orion_v_qiki_observation_objective_seed_smoke.py`
  - result: failed before ORION comparison with
    `timeout while waiting for live radar track with public designator in q_core world snapshot`
- dedicated resumed-contour probe:
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev python tools/orion_v_resume_precomparison_probe.py`
  - result: reached `_build_resume_observation_result(...)` and captured exact inputs on the resumed contour

Fresh resumed-contour evidence from the dedicated probe:

- objective:
  - `objective_id=observation-495c9e72-1a95-4f9d-91b9-b1e60f3f7ce3`
  - `request_id=495c9e72-1a95-4f9d-91b9-b1e60f3f7ce3`
  - `target=ALLY-0F4107`
  - `follow_up_status=resume_observation`
- contour state entering comparison:
  - `previous_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `previous_track_label=ALLY-0F4107`
- ORION live cache state for the contour key:
  - `live_cache_entry_for_previous_track=null`
  - ORION log: `source=fallback_live_track_missing`
- pending action before execute:
  - `observation_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `observation_track_label=ALLY-0F4107`
  - `observation_track_range_m=3500.3571246374277`
  - `observation_track_quality=1.0`
- exact parameters entering `_build_resume_observation_result(...)`:
  - `observation_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `observation_track_label=ALLY-0F4107`
  - `observation_track_range_m=3500.3571246374277`
  - `observation_track_quality=1.0`
  - `source=null`
  - `label_source=null`
  - `source_timestamp_unix_s=null`
  - `freshness_s=null`
- ORION final comparison log:
  - `comparison_track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `comparison_label=ALLY-0F4107`
  - `comparison_source=parameters`
  - `comparison_label_source=parameters`
  - `comparison_source_ts=missing`
  - `comparison_freshness_s=missing`
  - `result_candidate=reconfirmed`
  - `fallback_reason=label_unchanged`
- final objective:
  - `reason_code=OBJECTIVE_RESUMED_OBSERVATION_RECONFIRMED`
  - `observation_result_status=reconfirmed`
  - `track_id=ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - `track_label=ALLY-0F4107`

So this pass proves:

- the new ORION diagnostics are in code
- unit-level ORION comparison logic still passes
- the canonical smoke is still flaky before comparison because of q-core target pickup
- despite that flake, the dedicated probe produced a fresh resumed-contour comparison with the new `comparison_freshness_s` and `fallback_reason` fields

## 5. Why ORION selected `reconfirmed` instead of `signature_changed`

Evidence-backed answer from the last completed resumed comparison:

- ORION compared the resumed contour against the same `track_id`
  - `previous_track_id == comparison_track_id == ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
- ORION did not have a changed non-empty live label for that key
- comparison label resolved to the old contour/q-core label
  - `comparison_label=ALLY-0F4107`
- fresh dedicated probe proves the same thing with the new diagnostics:
  - `comparison_source=parameters`
  - `comparison_label_source=parameters`
  - `fallback_reason=label_unchanged`
- therefore the final predicate reduced to:
  - same id
  - non-empty previous label
  - non-empty comparison label
  - labels equal
- result:
  - `reconfirmed`

On the newly instrumented code, that exact case will now log:

- `result_candidate=reconfirmed`
- `fallback_reason=label_unchanged`

## 6. Is there stale/empty/fallback behavior?

### 6.1 Empty label case

Yes, empty-label handling exists in ORION-local code.

- If live cache entry exists but `transponder_id/id/callsign` resolves to empty string, ORION falls back to procedure label.
- This is now explicit through:
  - `source=live_cache`
  - `label_source=fallback_parameters`

So an empty live label can mask a live cache hit and still collapse to `reconfirmed`.

What the fresh dedicated probe showed:

- this run did not hit the empty-label branch
- it hit `fallback_live_track_missing`
- `live_cache_entry_for_previous_track=null`

So empty-label fallback is possible in code, but it was not the active blocker in the completed resumed probe.

### 6.2 Stale/live cache case

Potentially yes, and it is now measurable.

- Before this patch, ORION had no explicit freshness output at the comparison point.
- Now each comparison can expose:
  - `comparison_source_ts`
  - `comparison_freshness_s`

Current evidence does not yet prove stale cache as the blocker.

- The strongest proved behavior so far is not stale data by itself.
- The strongest proved behavior is that ORION did not receive a changed non-empty label on the contour key it used for comparison.

What the fresh dedicated probe showed:

- ORION did not compare against a live cache snapshot at all
- `comparison_source=parameters`
- `comparison_source_ts=missing`
- `comparison_freshness_s=missing`

So for the completed resumed probe, a stale live snapshot was not the direct blocker shape. The direct blocker shape was missing live cache for the contour key, which forced ORION onto fallback procedure parameters.

### 6.3 Live snapshot mismatch vs resumed contour

Yes, this is the main proven blocker shape.

Current evidence shows:

- ORION compares using the contour key from `_active_observation_objective`
- if live cache for that key is missing or unusable, ORION falls back to q-core procedure parameters
- the earlier completed run ended with old label on the same key, not with a changed label
- the fresh dedicated probe reproduced the same shape with explicit runtime values:
  - contour key `ba9d1423-61f0-55bd-aeaf-d5eaa225a010`
  - no ORION live cache entry for that key
  - fallback q-core parameters still carrying `ALLY-0F4107`
  - final `fallback_reason=label_unchanged`

### 6.4 Changed label overwritten before comparison

No ORION-local overwrite was found in the current path.

What code proves:

- `_live_observation_track_snapshot()` reads live cache and returns a snapshot
- `_execute_qiki_pending_action()` copies that snapshot into `result_parameters`
- `_build_resume_observation_result()` compares directly against those parameters

There is no separate ORION-local transformation that rewrites a changed non-empty comparison label back to the old value after snapshot creation.

So the current ORION-local conclusion is:

- ORION can fall back
- ORION can mask empty live labels via fallback
- ORION does not appear to overwrite a valid changed label before comparison
- on the completed resumed probe, ORION-local cause is localized to `fallback_live_track_missing -> parameters -> label_unchanged`, not to stale live-cache comparison and not to an internal label rewrite

## 7. Minimal next fix task candidates

1. Run one resumed contour again with the new ORION diagnostics and capture:
   - `Resume live snapshot`
   - `Resume comparison`
   - the final `qiki.events.v1.operator.objectives` payload

2. Correlate one wall-clock window across:
   - q-core `Resume objective lookup / Resume warmup settled / Resume track selection`
   - bridge track publication logs
   - ORION `Resume live snapshot / Resume comparison`

3. If the next run shows:
   - `fallback_reason=track_id_mismatch`
   then the blocker is upstream identity discontinuity, not ORION decision logic.

4. If the next run shows:
   - `comparison_label_source=fallback_parameters`
   or very large `comparison_freshness_s`
   then stale/empty ORION-local input remains in play and should be isolated narrowly at cache ingestion / live track publication.

5. If the next run shows:
   - same `track_id`
   - non-empty changed live label
   - but still `reconfirmed`
   then and only then treat ORION-local comparison logic as suspect.
