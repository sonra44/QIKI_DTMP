# TASK: Radar 3D readiness — inputs + frame contract (no-mocks)

**ID:** TASK_20260205_radar_3d_readiness_inputs_contract  
**Status:** in_progress  
**Owner:** codex  
**Date created:** 2026-02-05  

## Goal

Prepare “3D radar” work by defining a single explicit **data/frame/unit contract** and proving which keys exist in Phase1 telemetry/track payloads, so future rendering is honest (no invented z/attitude).

## Contract (axes / units / projections)

### Units

- Distances: meters (`*_m`)
- Angles: degrees (`*_deg`)
- Velocities: meters/second (`*_mps`)

### Coordinate frame (Phase1)

We treat radar track vectors as a right-handed local frame:
- `position.x` (meters): horizontal axis used as **U** in `view=top` and `view=side`.
- `position.y` (meters): horizontal axis used as **V** in `view=top` and **U** in `view=front`.
- `position.z` (meters): vertical axis used as **V** in `view=side` and `view=front`.

Evidence (code):
- ORION projection mapping: `src/qiki/services/operator_console/radar/projection.py` `project_xyz_to_uv_m()`:
  - `top` → `(x, y)`
  - `side` → `(x, z)`
  - `front` → `(y, z)`
  - `iso` → dot with `iso_camera_basis(right/up)`
- Existing polar→cartesian conventions differ by pipeline stage:
  - ORION Unicode/bitmap renderers (fallback from polar): `x = r * sin(bearing)`, `y = r * cos(bearing)` (bearing clockwise from +Y).
  - FastStream TrackStore `_polar_to_cartesian`: `x = r*cos(elev)*cos(bearing)`, `y = r*cos(elev)*sin(bearing)`, `z = r*sin(elev)` (bearing reference differs).

### Bearing/elevation conventions (must be locked)

Current state (needs one canon choice before 3D work):
- In ORION UI (charts + unicode_ppi fallback), `bearing_deg` is interpreted as degrees **clockwise from +Y**:
  - `x ~ sin(bearing)`, `y ~ cos(bearing)`.
- In TrackStore conversion, `bearing_deg` is interpreted with `x ~ cos(bearing)`, `y ~ sin(bearing)` and includes `elev_deg`.

**Decision required:** pick ONE canonical definition of `bearing_deg` relative to `(x,y)` (and document it here), then align the outlier (ORION fallback or TrackStore).

## Scope / Non-goals

- In scope:
  - Define axes, units, and view projections that ORION uses for radar tracks (x/y/z, bearing conventions, iso yaw/pitch semantics).
  - Audit which keys exist in real payloads (telemetry + radar frames/tracks) and document what is **missing**.
  - Specify `N/A/—` behavior for missing 3D inputs.
- Out of scope:
  - Implementing a true 3D renderer (OpenGL/Web/etc).
  - Any web sidecar visualization.

## Canon links

- Priority board (canonical): `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- Control contract: `docs/design/operator_console/SIMULATION_CONTROL_CONTRACT.md`
- No-mocks matrix: `docs/operator_console/REAL_DATA_MATRIX.md`
- Radar roadmap: `docs/radar_phase2_roadmap.md`
- Current renderer: `src/qiki/services/operator_console/radar/unicode_ppi.py`

## Plan (steps)

1) Identify “source of truth” payload shapes:
   - Radar frames / track payloads: find producer + schema (NATS subject + JSON keys).
   - Telemetry snapshot model keys (Phase1): `src/qiki/shared/models/telemetry.py`.
2) Write the contract (single page) inside this dossier:
   - Axes: what +X/+Y/+Z mean.
   - Bearing conventions: degrees clockwise from +Y (confirm in code).
   - Views: Top/Side/Front/ISO projections and required inputs.
3) Prove what exists (Docker-first):
   - Subscribe to the real NATS subjects and capture one sample payload per stream (no mocks).
   - Record which keys are present / absent.
4) Define “honest rendering” rules:
   - If z or velocity z is missing → show `N/A/—` and disable 3D-only overlays.
5) Add a minimal drift-guard test or doc link (only if needed) to prevent future “silent contract changes”.

## Definition of Done (DoD)

- [ ] Contract section filled with explicit axes/units and view mapping
- [ ] Evidence captured from real payloads (commands + short outputs)
- [ ] No-mocks behavior explicitly defined for missing 3D inputs
- [ ] Committed/pushed if repo changes are made

## Evidence (commands → output)

### NATS subjects (Phase1)

Producers:
- `q_sim_service` publishes radar frames (detections) to:
  - `qiki.radar.v1.frames` (union frame)
  - `qiki.radar.v1.frames.lr`
  - `qiki.radar.v1.tracks.sr` (SR detections stream; naming legacy but payload is a `RadarFrameModel`)
- `faststream_bridge` consumes `qiki.radar.v1.frames` from JetStream stream `QIKI_RADAR_V1` and publishes tracks to:
  - `qiki.radar.v1.tracks` (payload: `RadarTrackModel`)

### Payload keys (real sample, Docker-first)

Command used (inside `qiki-dev`): publish `sim.start` then subscribe and print keys only; then `sim.stop`.

Radar frame (`qiki.radar.v1.frames`) sample keys:
```json
{"subject":"qiki.radar.v1.frames","keys":["detections","frame_id","schema_version","sensor_id","timestamp","ts_event","ts_ingest"],"detections_item0_keys":["bearing_deg","elev_deg","id_present","range_band","range_m","rcs_dbsm","snr_db","transponder_id","transponder_mode","transponder_on","vr_mps"]}
```

Radar track (`qiki.radar.v1.tracks`) sample keys (3D inputs exist):
```json
{"subject":"qiki.radar.v1.tracks","missing":false,"keys":["age_s","bearing_deg","elev_deg","id_present","iff","miss_count","object_type","position","position_covariance","quality","range_band","range_m","rcs_dbsm","schema_version","snr_db","status","timestamp","track_id","transponder_id","transponder_mode","transponder_on","ts_event","ts_ingest","velocity","velocity_covariance","vr_mps"],"position_keys":["x","y","z"],"velocity_keys":["x","y","z"]}
```

## Notes / Risks

- Termius/tmux mouse behavior is not a valid acceptance dependency; proofs must remain headless/Docker-first.
- Don’t start 3D rendering work before the contract is locked, or we will ship “pretty lies”.
 - The project currently has two polar→cartesian mappings; until unified, 3D visualizations can be rotated/mirrored.

## Next

1) Lock the coordinate-frame contract: define what +X/+Y/+Z mean and how `bearing_deg` relates to `{x,y}` (must match current renderer convention).
