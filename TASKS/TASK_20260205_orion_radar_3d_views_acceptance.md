**ID:** TASK_20260205_orion_radar_3d_views_acceptance  
**Status:** done  
**Owner:** codex  
**Date created:** 2026-02-05  

## Goal

Produce deterministic acceptance proofs that ORION radar 3D views are consistent with the locked Phase1 coordinate contract:

- Side/Front/ISO projections respond to `z` (not a flat “3D”).
- ISO camera yaw convention matches the bearing contract (clockwise from +Y).

## Canon references

- Coordinate-frame contract (locked + real-data proof): `TASKS/TASK_20260205_radar_3d_readiness_inputs_contract.md`
- Sim-truth non-zero Z/elevation: `TASKS/TASK_20260205_radar_3d_sim_truth_nonzero_z.md`

## What changed

- `src/qiki/services/operator_console/radar/projection.py`:
  - `iso_camera_basis()` now treats `yaw_deg` as clockwise from +Y (0°=+Y, 90°=+X), matching the Phase1 radar contract.

## Proof (tests)

Unit proof:
- `tests/unit/test_orion_radar_projection_contract.py`
  - Asserts `iso_camera_basis(yaw=0,pitch=0)` yields `right≈+X`, `up≈+Z`.
  - Asserts `side/front/iso` projections change when `z` changes, while `top` does not.

Command:
- `bash scripts/quality_gate_docker.sh`

Evidence (git):
- commit: `4cfda64` (pushed)
