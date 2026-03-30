# Regression Pack Canonization

Date: 2026-03-25

## 1. Current regression entry

The canonical minimal regression entry for the current post-closure resumed-observation slice is:

```bash
bash scripts/run_minimal_regression_pack.sh
```

This entrypoint is for the canonical contour:
- `docker-compose.phase1.yml` + `docker-compose.operator.yml`
- ORION V on the current Phase1/operator stack
- the resumed-observation / `signature_changed` closeout slice with support-tier BIOS sanity

## 2. What it covers

The wrapper runs exactly three steps:

1. Targeted unit regression pack
- resumed identity continuity and `signature_changed`
- resumed live-snapshot logging/noise regression guard
- ORION procedure engine baseline
- BIOS service contract sanity
- registrar contract sanity

2. Canonical resumed observation smoke
- canonical resumed-observation route on the live Phase1 contour
- ORION procedure loading from `/workspace/config/orion_v/procedures`
- review -> hold -> resume continuity
- same-contour `signature_changed` closeout

3. BIOS live support-tier smoke
- live BIOS event contract on `qiki.events.v1.bios_status`
- payload sanity for `source`, `subject`, `event_schema_version`, `timestamp`, `bios_version`, `firmware_version`, `post_results`

## 3. What it does not cover

- full-stack validation beyond this narrow slice
- broad ORION acceptance or cutover rehearsal
- legacy ORION paths
- historical blocker-proof reruns for earlier failed `signature_changed` investigations
- general quality gate / full test suite / CI-wide validation

## 4. Required environment assumptions

- Docker is available locally.
- The canonical stack is already running on:
  - `docker-compose.phase1.yml`
  - `docker-compose.operator.yml`
- Required running services:
  - `nats`
  - `qiki-dev`
  - `q-sim-service`
  - `q-core-intents`
  - `faststream-bridge`
  - `q-bios-service`
  - `operator-console`
- ORION procedures for the resumed smoke are loaded from:
  - `/workspace/config/orion_v/procedures`
- BIOS smoke runs inside `qiki-dev` with:
  - `NATS_URL=nats://nats:4222`

## 5. Proof markers

Required resumed-smoke markers:
- `INITIAL_TARGET_SOURCE=orion_live_radar_cache`
- `RESUME_ACTION=resume_observation`
- `CONTINUATION_RESULT=signature_changed`
- `FINAL_QIKI_STATUS=confirmed`

Required BIOS-smoke marker:
- `OK: received bios status on qiki.events.v1.bios_status`

Operational note:
- the wrapper enforces these markers itself and fails even if the underlying process exits `0` without them

## 6. Small drift fixes made

- In [TASK_OUT/minimal_regression_pack_wrapper.md](/home/sonra44/QIKI_DTMP/TASK_OUT/minimal_regression_pack_wrapper.md), clarified that the wrapper is the canonical minimal regression entry for the current slice and is not the full validation/acceptance path.
- In [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md), removed stale wording that still treated the wrapper script as optional future work and replaced it with current canonical-entry wording.
- In [docs/ORION_V_RUNBOOK.md](/home/sonra44/QIKI_DTMP/docs/ORION_V_RUNBOOK.md), added a narrow operational note telling the next agent when to run the minimal regression entry and what boundary it has.
- In [scripts/run_minimal_regression_pack.sh](/home/sonra44/QIKI_DTMP/scripts/run_minimal_regression_pack.sh), tightened the help text so it names itself as the canonical minimal regression entry and explicitly says it is not the full validation suite.

## 7. Canonical usage recommendation

Use `bash scripts/run_minimal_regression_pack.sh` as the default first regression check when a change touches the current canonical resumed-observation slice or one of its included support-tier contract surfaces.

If this wrapper passes, that means the narrow current slice remains green at the intended minimal regression level. Broader validation should be added only when the specific task scope requires it; do not conflate this entry with full acceptance, cutover validation, or historical blocker-proof replay.
