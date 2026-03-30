# q_bios_service Liveness/Readiness Doc Hardening

Date: 2026-03-25

## Goal

Clarify the canonical semantics of `q_bios_service` without changing runtime behavior:
- `/healthz` is process liveness only;
- readiness and payload freshness require different checks;
- `/bios/status` is a cached support-tier snapshot surface.

## Active docs/runbooks hardened

1. [docs/ops/STATE_HEALTH_RUNBOOK.md](/home/sonra44/QIKI_DTMP/docs/ops/STATE_HEALTH_RUNBOOK.md)
- Added an explicit boundary under Docker preflight that `qiki-bios-phase1 healthy` means only that the HTTP process answers `/healthz`.
- Added post-check interpretation for:
  - process liveness;
  - dependency-sensitive `/bios/status`;
  - cached freshness behavior with publish enabled vs disabled.

2. [docs/RESTART_CHECKLIST.md](/home/sonra44/QIKI_DTMP/docs/RESTART_CHECKLIST.md)
- Added a dedicated BIOS HTTP semantics section.
- Explicitly separates:
  - `healthz` = process liveness only
  - `/bios/status` = cached payload surface
  - readiness/freshness = must be inferred from `/bios/status`, smoke, logs, and dependent services.

3. [docs/design/q-core-agent/bios_design.md](/home/sonra44/QIKI_DTMP/docs/design/q-core-agent/bios_design.md)
- Strengthened the factual MVP section:
  - `/healthz` does not guarantee q-sim readiness, NATS readiness, or payload freshness;
  - `/bios/status` freshness is bounded by publisher refresh when publish is enabled;
  - with publish disabled, cached HTTP snapshot may remain sticky until reload/recompute.

4. [docs/design/operator_console/ORION_OS_VALIDATION_CHECKLIST.md](/home/sonra44/QIKI_DTMP/docs/design/operator_console/ORION_OS_VALIDATION_CHECKLIST.md)
- Added a note so `q-bios-service healthy` is not over-read as BIOS freshness or dependency readiness.

## Supporting dossier note

- [TASK_OUT/qbios_contract_and_resilience.md](/home/sonra44/QIKI_DTMP/TASK_OUT/qbios_contract_and_resilience.md)
  now explicitly states that `/healthz` and `/bios/status` are not equivalent surfaces.

## Clarified semantics

### 1. Process liveness

- `GET /healthz` only means the `q_bios_service` HTTP process is alive and answering.
- It does not prove:
  - current q-sim readiness;
  - current NATS publishability;
  - fresh BIOS payload recomputation.

### 2. Dependency readiness

- Readiness for real BIOS usefulness depends on more than process liveness:
  - q-sim must be reachable enough for the BIOS-derived snapshot path to remain meaningful;
  - if observers rely on BIOS events, NATS must also be working;
  - downstream checks should use `/bios/status`, smoke probes, and dependent service checks, not `/healthz` alone.

### 3. Payload freshness

- `/bios/status` is backed by cached `_last_payload`.
- With `BIOS_PUBLISH_ENABLED=1` in canonical contour:
  - HTTP freshness is usually bounded by the next publisher refresh interval;
  - default bound is `BIOS_PUBLISH_INTERVAL_SEC` (`5s` unless configured otherwise).
- With `BIOS_PUBLISH_ENABLED=0`:
  - HTTP snapshot may remain sticky until `POST /bios/reload` or another recomputation path refreshes `_last_payload`.

## Runtime behavior

No runtime/API behavior was changed:
- no changes to `q_bios_service` handlers;
- no changes to payload fields;
- no changes to healthcheck semantics;
- no new tests or architecture added for this pass.

## Done check

- active docs/runbooks no longer imply that `/healthz` is stronger than process liveness;
- cached freshness semantics for `/bios/status` is described honestly;
- service behavior remains unchanged.
