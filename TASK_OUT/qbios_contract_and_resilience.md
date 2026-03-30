# q_bios_service: contract and resilience in canonical contour

Current baseline note:
- This file reflects the current post-closure support-tier baseline for `q_bios_service` on the canonical `docker-compose.phase1.yml` contour.
- As of 2026-03-25 UTC, the earlier ORION BIOS projection drift around `components` vs `post_results` is fixed and retained here only as historical/resolved context, not as a current next task.
- Current related baseline artifacts:
  - [TASK_OUT/orion_bios_projection_alignment.md](/home/sonra44/QIKI_DTMP/TASK_OUT/orion_bios_projection_alignment.md)
  - [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md)

## 1. Runtime role

`q_bios_service` is a support-tier BIOS/status sidecar in the canonical `docker-compose.phase1.yml` contour, not an owner of physical truth and not an owner of intents or legality.

Its runtime role is:
- read the configured hardware profile from `bot_config.json`;
- probe only `q-sim-service` liveness via gRPC `HealthCheck`;
- build a derived BIOS/POST-style support status payload;
- expose that payload over HTTP;
- periodically publish the same payload to NATS for observers.

It does not:
- own simulator truth;
- own command policy or legality;
- mutate sim state;
- gate startup of downstream services through its own business logic.

Canonical implementation and startup paths:
- entrypoint: `python -m qiki.services.q_bios_service.main`
- canonical contour: `docker-compose.phase1.yml`
- main files:
  - `src/qiki/services/q_bios_service/main.py`
  - `src/qiki/services/q_bios_service/config.py`
  - `src/qiki/services/q_bios_service/handlers.py`
  - `src/qiki/services/q_bios_service/health_checker.py`
  - `src/qiki/services/q_bios_service/bios_engine.py`
  - `src/qiki/services/q_bios_service/nats_publisher.py`

Evidence observed in live contour on 2026-03-24 UTC:
- `docker compose -f docker-compose.phase1.yml ps` showed `q-bios-service`, `q-sim-service`, and `nats` up and healthy.
- `GET http://127.0.0.1:8080/healthz` returned `{"ok": true}`.
- `GET http://127.0.0.1:8080/bios/status` returned live BIOS payload with 29 `post_results`, `all_systems_go=true`, `event_schema_version=1`, `source=q-bios-service`, and `subject=qiki.events.v1.bios_status`.

## 2. Inputs / outputs

### Inputs

Config/env sourcing from `BiosConfig`:
- `BIOS_LISTEN_HOST`, `BIOS_LISTEN_PORT`
- `BOT_CONFIG_PATH`
- `SIM_GRPC_HOST`, `SIM_GRPC_PORT`, `SIM_HEALTH_CHECK_TIMEOUT`
- `NATS_URL`, `NATS_EVENT_SUBJECT`
- `BIOS_PUBLISH_ENABLED`, `BIOS_PUBLISH_INTERVAL_SEC`
- `LOG_LEVEL`

Runtime reads:
- `BOT_CONFIG_PATH` default: `/workspace/src/qiki/services/q_core_agent/config/bot_config.json`
- gRPC health probe to `q-sim-service:50051` via `HealthCheck`

No inbound NATS subjects are consumed by `q_bios_service`.

### Outputs

HTTP:
- `/healthz`
- `/bios/status`
- `/bios/component/<id>`
- `POST /bios/reload`

NATS:
- periodic publish to subject `qiki.events.v1.bios_status` by default

Derived payload fields actually emitted by service:
- `bios_version`
- `firmware_version`
- `hardware_profile_hash`
- `post_results`
- `timestamp`
- computed `all_systems_go`
- `event_schema_version`
- `source`
- `subject`

### Dependencies by canonical role

- `bot_config.json`: runtime configuration source for expected hardware rows and hardware profile hash.
- `q-sim-service`: liveness dependency only; BIOS does not read sim telemetry truth, only `HealthCheck`.
- `nats`: distribution dependency for BIOS status events; not required for local HTTP handler to run.
- downstream observers:
  - `q_core_agent` fetches BIOS via HTTP, not via BIOS NATS event.
  - ORION consumes `qiki.events.v1.bios_status` as an event stream / boot indicator.

## 3. HTTP contract

Actual HTTP handler is implemented in `src/qiki/services/q_bios_service/handlers.py`.

### `GET /healthz`

Behavior:
- always returns HTTP 200 with `{"ok": true}` if the process is alive.

Important semantic boundary:
- this is liveness only;
- it does not verify `q-sim-service`;
- it does not verify NATS publishability;
- it does not guarantee a fresh BIOS payload exists.

### `GET /bios/status`

Behavior:
- returns HTTP 200 and the current BIOS payload.

Observed live payload shape on 2026-03-24 UTC:
```json
{
  "bios_version": "1.0",
  "firmware_version": "virtual_bios_mvp",
  "hardware_profile_hash": "sha256:207b234a4f1529867ad3cf1499ace66247b8ee5c79ee5578d35175f9fff8759b",
  "post_results": [
    {
      "device_id": "lidar_front",
      "device_name": "lidar",
      "status": 1,
      "status_message": "OK"
    }
  ],
  "timestamp": "2026-03-24T21:04:07.549591Z",
  "all_systems_go": true,
  "event_schema_version": 1,
  "source": "q-bios-service",
  "subject": "qiki.events.v1.bios_status"
}
```

Contract notes:
- `all_systems_go` is not stored separately by the engine; it is a computed field of the shared `BiosStatus` model.
- `status` in `post_results[*]` is numeric:
  - `0` unknown
  - `1` ok
  - `2` degraded
  - `3` error

Caching behavior:
- `get_status_payload()` returns cached `_last_payload` if present.
- In canonical contour this cache is refreshed by the publisher loop every `BIOS_PUBLISH_INTERVAL_SEC` (default 5s).
- With publishing disabled, the first computed HTTP snapshot becomes sticky until `POST /bios/reload` clears the cache.
- So `/healthz` and `/bios/status` must not be read as equivalent:
  - `/healthz` proves process liveness only;
  - `/bios/status` is the dependency-sensitive cached snapshot surface.

### `GET /bios/component/<id>`

Behavior:
- HTTP 200 with:
  - `ok=true`
  - `device`
  - `timestamp`
  - `bios_version`
  - `hardware_profile_hash`
- HTTP 404 with:
  - `ok=false`
  - `error=component_not_found`
  - `device_id=<requested>`

Live check on 2026-03-24 UTC:
- `GET /bios/component/lidar_front` returned the matching row with `status=1`.

### `POST /bios/reload`

Behavior:
- clears cached `_last_payload`;
- returns `{"ok": true, "reloaded": true}`.

Important boundary:
- it does not push config into other services;
- it does not change NATS subject or semantics;
- it does not force a publish itself;
- it only causes the next fetch / publisher iteration to recompute.

Live check on 2026-03-24 UTC:
- `POST /bios/reload` returned `{"ok": true, "reloaded": true}`.

## 4. NATS contract

### Canonical subject

- `qiki.events.v1.bios_status`

Canonical schema reference:
- `schemas/asyncapi/qiki.events.v1.bios_status/v1/README.md`
- `schemas/asyncapi/qiki.events.v1.bios_status/v1/payload.schema.json`

### Real emitted payload

Publisher path:
- `BiosService._publisher_loop()` computes payload
- adds:
  - `event_schema_version = 1`
  - `source = "q-bios-service"`
  - `subject = cfg.nats_subject`
- publishes JSON to NATS every `BIOS_PUBLISH_INTERVAL_SEC`, default `5.0`

Schema consistency observed:
- `tools/bios_status_smoke.py` validates `event_schema_version`, `source`, `subject`, `timestamp`, `bios_version`, `firmware_version`, optional `hardware_profile_hash`, `post_results`, and optional `all_systems_go`.
- live smoke succeeded on 2026-03-24 UTC when run with canonical `NATS_URL=nats://nats:4222`.

### Who uses BIOS NATS downstream

Proven direct downstream usage in code:
- ORION event ingestion classifies `qiki.events.v1.bios_status` as `bios` event type.
- ORION boot sequence reads:
  - `all_systems_go`
  - `post_results`
- ORION first-load announcement on the current baseline also reads:
  - `all_systems_go`
  - `post_results` for device count

Historical note:
- earlier pre-fix ORION code tried `components` for count instead of `post_results`
- that projection drift is fixed on the current post-fix baseline and documented in [TASK_OUT/orion_bios_projection_alignment.md](/home/sonra44/QIKI_DTMP/TASK_OUT/orion_bios_projection_alignment.md)

Non-usage boundary:
- `q_core_agent` does not consume BIOS over NATS in the canonical path; it fetches BIOS over HTTP from `BIOS_URL + /bios/status`.

## 5. Startup behavior

### Canonical contour startup

`docker-compose.phase1.yml` sets:
- `depends_on nats: service_healthy`
- `depends_on nats-js-init: service_completed_successfully`
- `depends_on q-sim-service: service_healthy`

So in canonical compose order, `q_bios_service` is normally started after NATS and q-sim are already available.

### Service process startup

Actual sequence in `main.py`:
1. load env into `BiosConfig`
2. configure logging
3. instantiate `BiosService`
4. start publisher thread
5. start stdlib `ThreadingHTTPServer`

Important startup semantics:
- the process does not block on a successful BIOS POST before binding HTTP;
- the process does not block on a successful NATS publish before binding HTTP;
- the container healthcheck uses only `/healthz`, so container health does not mean BIOS freshness or NATS health.

### Normal canonical startup behavior

In the supported contour on 2026-03-24 UTC:
- service started cleanly (`INFO:q_bios_service:Starting q-bios-service on 0.0.0.0:8080`);
- `/bios/status` was available;
- BIOS NATS event was received by smoke probe on canonical subject.

## 6. Degradation behavior

### Scenario: q-sim unavailable

Checked directly by calling `check_qsim_health()` against an unreachable port inside `qiki-dev`.

Observed result:
- `check_qsim_health(...).ok == False`
- built BIOS payload had `all_systems_go == False`
- first row became explicit `q-sim-service` error row with `status=3`
- hardware rows remained present but were marked degraded (`status=2`)

Implication:
- service degrades semantically instead of fabricating green data;
- HTTP contract stays available;
- BIOS status becomes degraded/error, not absent.

### Scenario: q-sim restarts / comes back

Checked directly by rebuilding payload once with failing health and once with live `q-sim-service:50051`.

Observed result:
- failed check produced `all_systems_go == False`
- next successful check produced `all_systems_go == True`
- the explicit `q-sim-service` error row disappeared on recovery

Canonical recovery behavior:
- recovery is non-sticky at compute level;
- in canonical contour, visible recovery is bounded by the next publisher refresh interval because HTTP usually serves cached `_last_payload`;
- default bound is about 5 seconds.

### Scenario: NATS temporarily unavailable

Code-backed behavior from `_publisher_loop`:
- BIOS payload is computed before publish attempt;
- `_last_payload` is updated even if publish then fails;
- publish failures are caught and logged as warning;
- loop continues and retries next interval;
- successful recovery logs `NATS publish recovered`.

Therefore:
- HTTP path should remain available even when NATS is temporarily unavailable;
- NATS outage degrades distribution, not local BIOS computation.

Important ambiguity:
- `NatsJsonPublisher._connect()` uses the NATS client with reconnect settings that may be noisy or slower than the nominal loop interval during initial outage conditions;
- in ad hoc negative probing, the library produced repeated connection errors;
- this does not contradict the service-level intent, but it means outage timing/jitter is library-shaped and not fully bounded by the outer loop alone.

### Scenario: bot config unreadable

Checked directly by calling `build_bios_status()` with a missing file path.

Observed result:
- payload returns `hardware_profile_hash = null`
- `post_results` becomes a single explicit error row for `bot_config`
- `all_systems_go == False`

Implication:
- service does not invent device rows when config truth is absent.

## 7. Drift / ambiguity

### Code vs docs drifts

1. `docs/design/q-core-agent/bios_design.md`
- section 0.1 says current real HTTP API is only `GET /healthz` and `GET /bios/status`
- but current code also exposes `GET /bios/component/<id>` and `POST /bios/reload`

2. `TASKS/TASK_20260123_OS_ARCH_REFERENCE_AND_ALIGNMENT_PLAN.md`
- says current handler has only `/bios/status`
- current code has the additional component and reload routes

3. same BIOS design doc still contains a target payload example with:
- `status: "ready" | "error"`
- `components: {...}`
- actual runtime payload uses:
  - `all_systems_go: bool`
  - `post_results: list[...]`

4. Historical ORION BIOS first-load projection drift
- pre-fix ORION first BIOS-loaded message tried to count `components`
- actual event payload has `post_results`
- pre-fix result: the message could miss component count even though the BIOS payload was valid
- current status: fixed on the post-2026-03-25 baseline; current ORION projection counts from `post_results`

5. `protos/bios_status.proto` is not the real contract for canonical `q_bios_service`
- proto contains fields such as `bios_uuid`, `health_score`, `last_checked`, `uptime_sec`, device `status_code`, `device_type`
- HTTP/NATS payload emitted by `q_bios_service` does not expose those fields
- canonical live BIOS status path currently follows shared JSON/Pydantic model plus AsyncAPI schema, not that proto

### Contract boundary clarifications

1. `q_bios_service` is not truth owner
- `bot_config.json` is config truth for expected hardware profile
- `q-sim-service` remains simulator truth owner
- BIOS status is a derived support projection

2. `q_bios_service` is not policy owner
- it does not decide legality, trust, or operator action admissibility
- policy remains upstream of BIOS, chiefly in bridge / agent layers, not here

3. `/healthz` is weaker than operator expectations might imply
- it reports process liveness only
- not readiness of q-sim
- not readiness of NATS
- not freshness of BIOS payload

4. HTTP freshness depends on publisher thread in canonical contour
- because `_last_payload` is cached, HTTP freshness is indirectly coupled to periodic publishing
- with publishing disabled, HTTP can serve stale status until reload

### Real downstream field usage

Fields proven used downstream:
- `post_results`
  - ORION boot visualization
  - q-core HTTP model ingestion
  - q-core `all_systems_go` computed meaning
- `all_systems_go`
  - ORION BIOS boot status / event log
  - q-core safety and tick logic
- `hardware_profile_hash`
  - q-core preserves it when processing BIOS status
  - ORION shows hardware profile hash from telemetry, not from BIOS event
- `bios_version`, `firmware_version`
  - q-core HTTP model accepts them
  - smoke/schema validates them
- `subject`
  - ORION uses it to classify BIOS events
- `event_schema_version`, `source`, `timestamp`
  - validated by BIOS smoke tooling

Fields not proven used downstream from the BIOS event:
- any `components` map, because runtime payload does not emit one
- any richer proto-only fields such as `bios_uuid`, `health_score`, `uptime_sec`

## 8. Status of previously identified follow-ups

1. Docs/code alignment
- This file now reflects the current HTTP/NATS contract and the `/healthz` vs `/bios/status` semantic split.
- Older BIOS design/task references mentioned in section 7 remain legacy drift candidates when those specific documents are next touched, but they are not current blocker work.

2. ORION BIOS projection drift
- Completed/resolved.
- The old `components` vs `post_results` mismatch is no longer a current next task for this slice.
- Current baseline reference: [TASK_OUT/orion_bios_projection_alignment.md](/home/sonra44/QIKI_DTMP/TASK_OUT/orion_bios_projection_alignment.md).

3. Liveness vs readiness wording
- Completed/resolved in the current active docs/runbooks baseline.
- `/healthz` is process liveness only; dependency freshness/readiness stays documented separately via `/bios/status` semantics.

4. Cached recovery semantics
- Kept as an active contract note in this document, not as a new engineering task.
- The important current truth is that HTTP freshness depends on the cached payload refresh path.

5. NATS outage timing
- Kept as evidence/reference only.
- It should only be re-probed if BIOS distribution behavior is questioned again; it is not part of the current cleanup baseline.
