# signature_changed blocker investigation

Historical note:
- This artifact records the pre-closure blocker investigation state.
- It is superseded by the 2026-03-24 canonical live proof, the follow-up seed-smoke alignment fix, and the current hardening baseline.
- Do not read this file as the current blocker status; keep it only as historical diagnosis context.

## 1. Current confirmed path

### 1.1 Schema / projection / tests inventory

- Schema supports `observation_result_status=reconfirmed|signature_changed` in [payload.schema.json](/home/sonra44/QIKI_DTMP/schemas/asyncapi/qiki.events.v1.operator.objectives/v1/payload.schema.json).
- Schema README documents the same minimal continuation-result contract in [README.md](/home/sonra44/QIKI_DTMP/schemas/asyncapi/qiki.events.v1.operator.objectives/v1/README.md).
- ORION comparison logic exists in [_build_resume_observation_result()](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py) and `_live_observation_track_snapshot()` in [app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py).
- Cockpit projection exists in [cockpit.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/screens/cockpit.py).
- Systems/F1 projection exists in [systems.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/screens/systems.py).
- Smoke harness path exists in [tools/orion_v_qiki_observation_objective_seed_smoke.py](/home/sonra44/QIKI_DTMP/tools/orion_v_qiki_observation_objective_seed_smoke.py).
- Task dossier exists in [TASK_20260313_g3_qiki_second_observation_result_signature_changed.md](/home/sonra44/QIKI_DTMP/TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md).

### 1.2 Confirmed interservice chain from code

1. Operator resumes the contour:
   `hold_for_recheck -> resume_observation` is translated by `q-core-intents` into a follow-up objective update on the same contour in [qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py).
2. Operator issues resumed `safe observation <target>`.
3. `q-core-intents`:
   - finds the latest resumable objective via `_find_resumable_observation_objective()`;
   - refreshes snapshot via `GrpcDataProvider` + `QCoreAgent._ingest_sensor_data()`;
   - builds `qiki.responses.qiki` with `ORION_PROCEDURE safe_pause_resume`;
   - injects `observation_track_id/label/range/quality` from `_observation_track_snapshot(resumed_track)`.
4. ORION receives the procedure, executes it, then calls `_live_observation_track_snapshot()` against its live `qiki.radar.v1.tracks` cache.
5. ORION decides result locally in `_build_resume_observation_result()`:
   - `signature_changed` only if:
     - previous `track_id` == resumed `track_id`
     - previous `track_label` is non-empty
     - resumed `track_label` is non-empty
     - previous `track_label` != resumed `track_label`
   - otherwise result falls back to `reconfirmed`.
6. ORION publishes the final `qiki.events.v1.operator.objectives` update on the same contour.
7. Cockpit/systems projection reads that canonical payload and renders `signature_changed` if present.

### 1.3 What is proved by code

- `signature_changed` is not UI-only. It is a contract value in schema, produced in ORION logic, and rendered by cockpit/systems.
- Resumed `safe observation` does not create a new objective seed when `resume_observation` is already active; it reuses the same contour identity.
- ORION owns the final comparison and final objective update for `reconfirmed` vs `signature_changed`.
- `q-core-intents` supplies procedure parameters from its own refreshed snapshot before ORION execution.

### 1.4 What is proved by unit tests

- Fresh Docker unit run passed on 2026-03-24:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_qiki_orion_intents_service.py tests/unit/test_orion_v_qiki_loop.py tests/unit/test_orion_v_cockpit.py`
- `tests/unit/test_qiki_orion_intents_service.py` proves builder-level behavior:
  a resumable contour can return `safe_pause_resume` with the same `observation_track_id` and a changed `observation_track_label` when the input `world_snapshot` already contains that condition.
- `tests/unit/test_orion_v_qiki_loop.py` proves ORION-level behavior:
  if ORION has an active resumed objective and then receives a live track with the same `track_id` and changed `transponder_id`, it records `observation_result_status=signature_changed`.
- `tests/unit/test_orion_v_cockpit.py` proves projection-level behavior:
  cockpit renders the `signature_changed` continuation-result text.

### 1.5 What unit tests do not prove

- They do not prove that the live stack can honestly produce the prerequisite `same track_id + changed non-empty track_label`.
- They do not prove alignment between:
  - q-core target selection snapshot,
  - faststream-bridge track identity,
  - ORION live radar cache.
- They do not prove live continuity through `sim.xpdr.mode=SPOOF`.

## 2. Live gap

### 2.1 Fresh live evidence on current stack

- Docker stack was live during this pass:
  `nats`, `q-sim-service`, `q-bios-service`, `operator-console`; `qiki-dev` was started for verification.
- Fresh live smoke on 2026-03-24:
  `docker compose -f docker-compose.phase1.yml exec -T qiki-dev env QIKI_OBSERVATION_STYLE=slow QIKI_RESUME_XPDR_MODE=SPOOF python tools/orion_v_qiki_observation_objective_seed_smoke.py`
- Result:
  `AssertionError: signature_changed precondition failed: resumed contour track_id=91d838a2-d6f6-5cb7-a768-2b0d8acd3661 kept label ALLY-0F4107 after sim.xpdr.mode=SPOOF`

### 2.2 Actual localized gap

- The blocker is not schema.
- The blocker is not cockpit/systems projection.
- The blocker is not unit support for ORION comparison.
- The live gap is the missing proof of one exact predicate on the canonical resumed contour:
  `same track_id` and `changed non-empty track_label`.

## 3. Candidate loss points

| Loss point | What is proved by code | What is not proved on live stack |
| --- | --- | --- |
| Sim transponder mutation | `sim.xpdr.mode` is a real command; `q_sim_service` resolves `SPOOF-*` via `_resolve_transponder_id()` in [service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_sim_service/service.py). | That the resumed observation target is the same live contact whose public SR identity actually flips on the contour used for the smoke. |
| Radar truth continuity in q-core | `q-core-intents` refreshes via `GrpcDataProvider` and `QCoreAgent._ingest_sensor_data()`. | That q-core preserves the same target identity across a transponder/signature change. |
| Bridge frame -> track transformation | `faststream_bridge` updates `state.transponder_id` in place for associated tracks; bridge-assigned `track_id` is created once on spawn in [radar_track_store.py](/home/sonra44/QIKI_DTMP/src/qiki/services/faststream_bridge/radar_track_store.py). | That association remains stable through the mutation and that ORION sees the changed label on the same bridge `track_id` at the right time. |
| Target-track selection in q-core-intents | Resume path prefers the resumable objective `track_id`, then falls back to `target_designator` in [qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py). | That the q-core-selected track is the same truth object ORION later compares in its live radar cache. |
| ORION snapshot comparison | ORION compares active objective vs `_latest_radar_tracks[track_id]` and publishes final continuation-result in [app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py). | That ORION ever receives a live track on the same `track_id` whose label actually differs from the stored objective label on this stack. |

## 4. Ranked hypotheses

### 1. q-core target identity is unstable by construction across signature changes

- Probability: highest.
- Service to inspect: `q-core-agent` / `q-core-intents`.
- Code evidence:
  [world_model.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/core/world_model.py) derives `track_id` from `detection.transponder_id`:
  `track_id=uuid5(... f"qiki-radar:{sensor_id}:{track_key}")`, where `track_key = detection.transponder_id or sensor_id:index`.
- Why this matters:
  a real label/signature flip can create a new q-core `track_id`, so q-core resume matching may stop seeing the changed label as the same contour even before ORION runs.
- Observable signs:
  after `sim.xpdr.mode=SPOOF`, q-core world snapshot should either:
  - emit a new `track_id` for the spoof-labelled contact, or
  - keep returning the old `track_id` with old `ALLY-*` label.
- Minimal diagnostic task:
  record consecutive q-core `world_snapshot.radar_tracks` entries around the mode switch for the chosen resumed target and compare `(track_id, transponder_id, sensor_id, timestamp)` before and after the ACK.

### 2. q-core and ORION do not share the same truth identity model

- Probability: high.
- Service to inspect: `q-core-intents` plus `operator-console/orion_v`.
- Code evidence:
  `q-core-intents` refreshes from `GrpcDataProvider` / q-core world model, while ORION compares against `_latest_radar_tracks` fed from `qiki.radar.v1.tracks`.
- Why this matters:
  the response procedure parameters may be built from one identity space, but ORION closes the contour in another identity space.
- Observable signs:
  for the same resumed target and same wall-clock window:
  - q-core shows one `(track_id, label)`,
  - ORION track cache shows another `(track_id, label)`,
  - or one side flips label while the other does not.
- Minimal diagnostic task:
  subscribe/log both sources in parallel for one resumed contour:
  q-core `world_snapshot.radar_tracks` and ORION `qiki.radar.v1.tracks`, keyed by target designator and timestamps.

### 3. Bridge association does not preserve same-track continuity through the mutation window

- Probability: medium.
- Service to inspect: `faststream-bridge`.
- Code evidence:
  bridge track IDs are spawn-time UUIDs and `transponder_id` is updated on associated tracks in place.
- Why this matters:
  if association breaks during the XPDR mutation, a new bridge track can spawn, and ORION will not satisfy `previous_track_id == resumed_track_id`.
- Observable signs:
  around the XPDR switch, `qiki.radar.v1.tracks` should show either:
  - same `track_id`, label changes from `ALLY-*` to `SPOOF-*`, or
  - old `track_id` coasts/lost and a new `track_id` appears with `SPOOF-*`.
- Minimal diagnostic task:
  capture raw bridge-published tracks for one target across the mutation window with `track_id/status/transponder_id/miss_count/range_band`.

### 4. q-sim command changes telemetry truth, but not the observation target’s published SR identity on the needed contour

- Probability: medium.
- Service to inspect: `q-sim-service`.
- Code evidence:
  `_resolve_transponder_id()` can produce `SPOOF-*`, and smoke shows ACK on the command path.
- Why this matters:
  ACK + telemetry truth do not yet prove that the specific resumed observation target receives the changed public SR identity used by downstream track truth.
- Observable signs:
  telemetry reports `SPOOF-*`, but the radar detections / downstream tracks for the chosen target remain `ALLY-*`.
- Minimal diagnostic task:
  capture q-sim-origin radar detections or immediate downstream frames for the target right after ACK and compare `transponder_mode/transponder_id` with telemetry state.

### 5. ORION comparison is correct, but its live input can degrade to fallback/reconfirmed on stale or empty label cases

- Probability: lower, but real.
- Service to inspect: `operator-console/orion_v`.
- Code evidence:
  `_live_observation_track_snapshot()` falls back to the previous label if the live label is empty or the live track is missing.
- Why this matters:
  `OFF`/`SILENT`, temporary loss, or stale cache will never produce `signature_changed`; they collapse into `reconfirmed` behavior.
- Observable signs:
  ORION cache either:
  - never receives a non-empty changed label on the previous `track_id`, or
  - temporarily loses the track and falls back to previous objective data.
- Minimal diagnostic task:
  instrument one resumed run with ORION-side logging of:
  `current objective (track_id, track_label)` vs `_latest_radar_tracks[track_id]` before `_build_resume_observation_result()`.

## 5. Minimal diagnostic tasks

| Diagnostic task | Service | What should confirm it |
| --- | --- | --- |
| Dump q-core world snapshot tracks for one resumed target before/after `sim.xpdr.mode=SPOOF` | `q-core-agent` / `q-core-intents` | either new `track_id` appears with `SPOOF-*`, or old `track_id` remains stuck on `ALLY-*` |
| Capture bridge-published `qiki.radar.v1.tracks` around the same window | `faststream-bridge` | same `track_id` with changed `transponder_id`, or explicit old/new track split |
| Compare q-core snapshot vs bridge stream for the same target and timestamps | `q-core-intents` + `faststream-bridge` + `ORION` | divergence in `track_id` or `track_label` identity spaces |
| Capture q-sim radar truth immediately after ACK | `q-sim-service` | telemetry says `SPOOF-*`; radar truth for the target must either match or expose the mutation gap |
| Log ORION pre-comparison inputs on one resumed run | `operator-console/orion_v` | proves whether ORION is receiving a changed live label and rejecting it, or never receiving it at all |

## 6. Какие сервисы участвуют в закрытии blocker

- `q-sim-service`
  owns the transponder mutation and the sensor truth that must originate the label change.
- `faststream-bridge`
  owns canonical frame -> track continuity for the NATS radar track stream consumed by ORION.
- `q-core-intents` / `q-core-agent`
  owns resumed-target selection and the procedure parameters handed to ORION.
- `operator-console` / `ORION V`
  owns final same-contour comparison and publication of `observation_result_status`.
- `nats`
  is transport, not blocker owner, but it is part of the evidence path and must be present during diagnostics.

## 7. Что нельзя утверждать по текущему evidence

- Нельзя утверждать, что blocker “fixed”.
- Нельзя утверждать, что проблема UI-only.
- Нельзя утверждать, что ORION comparison logic itself сломан; unit proof for that logic is green.
- Нельзя утверждать, что `sim.xpdr.mode=SPOOF` автоматически даёт same-contour `signature_changed`.
- Нельзя утверждать, что live stack already supports `signature_changed` honestly on the canonical resumed contour.
- Нельзя утверждать, что единственный loss point уже доказан; сейчас локализация сузилась до конкретного набора технических гипотез, strongest of which is the q-core identity model / cross-service identity mismatch.
