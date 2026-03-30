# q_bios_service contract/doc cleanup

Date: 2026-03-24 UTC

## Scope

Narrow cleanup for `q_bios_service` only:
- HTTP endpoints
- `qiki.events.v1.bios_status`
- startup / reload behavior
- docs / comments / config-default clarity

No API rewrite, no ownership change, no q-sim / q-core / ORION refactor.

## Role statement

`q_bios_service` is a **support-tier derived BIOS/status layer**.
It derives status from:
- `bot_config.json`
- `q-sim-service` health check

It is **not**:
- owner of physical/runtime truth
- owner of intents
- owner of policy

## Drift found

1. `docs/design/q-core-agent/bios_design.md` listed only part of the real HTTP surface in the factual MVP section.
2. Startup and reload behavior were under-specified in docs:
   - first payload is computed on demand, not precomputed at boot
   - `POST /bios/reload` only invalidates cached derived payload in MVP
3. Canonical event contract vs config override was implicit:
   - AsyncAPI schema says v1 subject is fixed as `qiki.events.v1.bios_status`
   - code/config allowed `NATS_EVENT_SUBJECT` override without an explicit “non-canonical/dev-only” note
4. Code comments/docstrings did not explicitly restate the service role as support-tier derived status projection.

## Changes made

### Code / comments

- `src/qiki/services/q_bios_service/main.py`
  - added service-level role docstring
  - added comment that payload is derived from bot config + q-sim health and does not own runtime truth/intents
  - added startup log line that explicitly states service role

- `src/qiki/services/q_bios_service/config.py`
  - added config docstring
  - documented that default subject `qiki.events.v1.bios_status` is the canonical v1 contract
  - documented that `NATS_EVENT_SUBJECT` override is non-canonical/dev wiring only

- `src/qiki/services/q_bios_service/handlers.py`
  - clarified HTTP handler role
  - documented actual `POST /bios/reload` MVP semantics as cache invalidation for next recompute

### Docs / config clarity

- `docs/design/q-core-agent/bios_design.md`
  - factual MVP section now includes all real endpoints
  - explicitly states support-tier derived role and non-ownership
  - documents startup behavior, reload behavior, and current config defaults

- `schemas/asyncapi/qiki.events.v1.bios_status/v1/README.md`
  - explicitly states support-tier derived role
  - clarifies canonical subject vs non-canonical override
  - documents relation between event contract and HTTP `/bios/status`
  - documents reload behavior without inventing new semantics

- `docker-compose.phase1.yml`
  - added one comment beside `NATS_EVENT_SUBJECT` to keep default contract intent explicit in runtime config

## Minimal contract verification

### Live checks

- Stack status:
  - `docker compose -f docker-compose.phase1.yml ps`
  - `q-bios-service` was `Up ... (healthy)` on `127.0.0.1:8080`

- HTTP contract:
  - `curl -sS http://127.0.0.1:8080/healthz`
  - result: `{"ok": true}`
  - `curl -sS http://127.0.0.1:8080/bios/status`
  - returned live BIOS payload with `bios_version`, `hardware_profile_hash`, `post_results`
  - `curl -sS -X POST http://127.0.0.1:8080/bios/reload`
  - result: `{"ok": true, "reloaded": true}`

### Tests added

- `src/qiki/services/q_bios_service/tests/test_service_contract.py`
  - verifies status payload carries canonical contract fields:
    - `event_schema_version == 1`
    - `source == "q-bios-service"`
    - `subject == "qiki.events.v1.bios_status"`
  - verifies reload behavior:
    - payload remains cached until `/bios/reload` semantics are triggered
    - after reload, next status read recomputes from current config file
  - verifies publisher loop emits payload on configured subject and closes publisher cleanly

### Docker test evidence

- Command:
  - `docker compose -f /home/sonra44/QIKI_DTMP/docker-compose.phase1.yml exec -T qiki-dev pytest -q src/qiki/services/q_bios_service/tests`
- Result:
  - `...................                                                      [100%]`

## Done check

- docs/config/comments no longer contradict the current code for endpoints, subject, startup, and reload
- role of `q_bios_service` is explicitly stated as support-tier derived status layer
- minimal contract confirmation exists via live HTTP checks and Docker unit tests
