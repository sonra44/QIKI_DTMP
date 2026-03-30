# Minimal Regression Pack Wrapper

## Goal

Provide one repeatable canonical minimal regression entry for the current post-closure resumed-observation slice, without changing ORION/q-core/bridge business semantics.

## Single entrypoint

Current canonical regression entry for this slice:

Run:

```bash
bash scripts/run_minimal_regression_pack.sh
```

The wrapper executes, in order:

1. Targeted unit regression pack.
2. Canonical resumed observation smoke.
3. BIOS live support-tier smoke.

Boundary:
- this wrapper is the canonical minimal regression entry for the current slice;
- it is not the full validation path, not the broad acceptance suite, and not a historical blocker-proof replay bundle.
- failure severity interpretation is mapped separately in [TASK_OUT/regression_failure_severity_map.md](/home/sonra44/QIKI_DTMP/TASK_OUT/regression_failure_severity_map.md), so a red step is not automatically treated as reopened P0.

## Canonical environment details embedded in the wrapper

- Canonical live contour assumption:
  - `docker-compose.phase1.yml` + `docker-compose.operator.yml`
  - expected running services: `nats`, `qiki-dev`, `q-sim-service`, `q-core-intents`, `faststream-bridge`, `q-bios-service`, `operator-console`
- Canonical ORION procedure loading path for the resumed smoke:
  - `ORIONV_PROCEDURES_DIR=/workspace/config/orion_v/procedures`
- BIOS smoke container-side NATS address:
  - `NATS_URL=nats://nats:4222`
- Resumed smoke route assumption:
  - `QIKI_OBSERVATION_STYLE=slow`
  - `QIKI_RESUME_XPDR_MODE=SPOOF`

## Commands wrapped

### 1. Targeted unit regression pack

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_qiki_loop.py::test_resumed_safe_observation_records_signature_changed_result_on_same_objective \
  tests/unit/test_orion_v_qiki_loop.py::test_live_observation_track_snapshot_logs_public_identity_without_format_noise \
  tests/unit/test_qiki_orion_intents_service.py::test_find_resumable_observation_objective_logs_qcore_and_public_identity \
  tests/unit/test_orion_v_procedure_engine.py \
  src/qiki/services/q_bios_service/tests/test_service_contract.py \
  src/qiki/services/registrar/tests/test_main_contract.py
```

- This targeted unit slice also preserves the maintained resumed-path observability surface:
  - contour/objective identity
  - q-core identity
  - public-track identity
  - comparison label
  - result candidate

### 2. Canonical resumed observation smoke

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc \
  'ORIONV_PROCEDURES_DIR=/workspace/config/orion_v/procedures QIKI_OBSERVATION_STYLE=slow QIKI_RESUME_XPDR_MODE=SPOOF python tools/orion_v_qiki_observation_objective_seed_smoke.py'
```

Required proof markers:

- `INITIAL_TARGET_SOURCE=orion_live_radar_cache`
- `RESUME_ACTION=resume_observation`
- `CONTINUATION_RESULT=signature_changed`
- `FINAL_QIKI_STATUS=confirmed`

### 3. BIOS live support-tier smoke

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc \
  'NATS_URL=nats://nats:4222 python tools/bios_status_smoke.py'
```

Required proof markers:

- `OK: received bios status on qiki.events.v1.bios_status`
- successful payload contract validation for `source`, `subject`, `event_schema_version`, `timestamp`, `bios_version`, `firmware_version`, `post_results`

## Failure behavior

- Wrapper starts with a preflight for the canonical stack and fails immediately if one of the required services is not running.
- Each step streams live output and is also written to a temp log directory.
- On failure the wrapper prints:
  - which step failed;
  - saved log path;
  - last log lines for quick triage.
- For both smoke steps the wrapper also fails if required proof markers are absent even when the process itself exits `0`.

## Why this meets the goal

- There is now one simple way to run the whole minimal pack.
- The runner no longer depends on remembering separate commands or container-specific env details.
- The output is fail-loud and points directly to the broken slice: unit regression, resumed contour smoke, or BIOS support-tier smoke.
- For the current canonical slice, `bash scripts/run_minimal_regression_pack.sh` should be treated as the default regression entry before broader validation is considered.
