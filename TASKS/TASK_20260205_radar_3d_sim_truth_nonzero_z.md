**ID:** TASK_20260205_radar_3d_sim_truth_nonzero_z  
**Status:** done  
**Owner:** codex  
**Date created:** 2026-02-05  

## Goal

Make Phase1 radar streams carry **real non-zero Z / elevation** so ORION `side/front/iso` can be accepted honestly (no “flat 3D”).

## What changed (sim truth)

- `q_sim_service` now emits radar detections using the locked Phase1 coordinate contract:
  - `bearing_deg` is clockwise from +Y (0°=+Y, 90°=+X).
  - `range_m` is full 3D range `sqrt(x^2+y^2+z^2)`.
  - `elev_deg` is derived from `(x,y,z)` (degrees up from XY).
- A deterministic non-zero Z target is introduced via `RADAR_SIM_TARGET_Z_M` (default `50.0` m).
  - At rest (`hypot(x,y) < 1`), the target is placed at a stable forward offset (`y = 0.7 * sr_threshold`) to avoid 0/0 bearing.

Code:
- `src/qiki/shared/radar_coords.py`: added `xyz_to_polar` helpers (single source-of-truth).
- `src/qiki/services/q_sim_service/service.py`: `generate_radar_frame()` now uses `xyz_to_polar` + non-zero Z target.

## Proof (integration, Docker-first)

Integration test:
- `tests/integration/test_radar_3d_sim_truth_nonzero_z.py`

Command:
- `bash scripts/run_integration_tests_docker.sh -k radar_3d_sim_truth_nonzero_z`

Expected:
- At least one real `qiki.radar.v1.frames` detection has `elev_deg != 0`.
- At least one real `qiki.radar.v1.tracks` message has `position.z != 0` and `elev_deg != 0`.

## Notes

- This is sim-truth (not UI mocks). ORION is still required to render `N/A/—` when 3D inputs are missing in other contexts.
