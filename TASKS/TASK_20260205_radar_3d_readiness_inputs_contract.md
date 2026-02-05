# TASK: Radar 3D readiness — inputs + frame contract (no-mocks)

**ID:** TASK_20260205_radar_3d_readiness_inputs_contract  
**Status:** in_progress  
**Owner:** codex  
**Date created:** 2026-02-05  

## Goal

Prepare “3D radar” work by defining a single explicit **data/frame/unit contract** and proving which keys exist in Phase1 telemetry/track payloads, so future rendering is honest (no invented z/attitude).

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

- TBD

## Notes / Risks

- Termius/tmux mouse behavior is not a valid acceptance dependency; proofs must remain headless/Docker-first.
- Don’t start 3D rendering work before the contract is locked, or we will ship “pretty lies”.

## Next

1) Locate the Phase1 producer(s) of radar track payloads (code + NATS subject), and record the payload key schema used today.

