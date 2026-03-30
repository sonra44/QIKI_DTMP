# Canonical Runtime Maintenance Runbook

Date: 2026-03-25

## 1. Canonical contour

Current canonical runtime contour for this maintenance layer:
- `docker-compose.phase1.yml` + `docker-compose.operator.yml`
- `q-sim-service`
- `q-core-intents`
- `faststream-bridge`
- `q-bios-service`
- `operator-console` running ORION V
- `nats` as the event/control backbone

Canonical operator path:
- start the stack with the canonical compose pair
- use ORION V as the supported operator surface
- use `./scripts/run_orion_v_live.sh` for a fresh interactive ORION V session under `tmux`

Boundary:
- this runbook is for the current maintenance baseline
- legacy contours are rollback/diagnostic only and are not treated as equal runtime paths here

## 2. Startup sanity check

Bring up the canonical contour:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build
```

Quick sanity commands:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps
curl -s http://localhost:8222/healthz
docker logs --tail=120 qiki-operator-console
```

Optional operator check:

```bash
./scripts/run_orion_v_live.sh
```

What to look for immediately:
- required services are up on the canonical stack
- NATS health endpoint answers successfully
- ORION V is the live operator path, not `docker attach`
- ORION logs do not show a crash loop
- ORION header/connectivity state behaves normally if you open the live session

For BIOS support behavior, remember the semantic split:
- `/healthz` on `q_bios_service` is process liveness only
- `/bios/status` is the cached support snapshot and is the meaningful maintenance surface for BIOS state

## 3. Minimal regression invocation

Default regression gate for this slice:

```bash
bash scripts/run_minimal_regression_pack.sh
```

Use it after changes touching:
- resumed observation / `signature_changed`
- ORION procedure loading on this slice
- resumed-path observability fields
- BIOS support-tier contract surface
- registrar contract sanity included in the pack

Boundary:
- this is the canonical minimal regression entry for the current slice
- it is not the full acceptance suite
- it is not a broad cutover rehearsal
- it is not a historical proof-replay bundle for superseded failure narratives

## 4. Healthy baseline markers

Canonical contour is in the current healthy baseline when:
- stack services are up on `docker-compose.phase1.yml` + `docker-compose.operator.yml`
- ORION V is reachable as the operator path and is not in a crash loop
- minimal regression pack passes

Required minimal regression proof markers:
- resumed smoke:
  - `INITIAL_TARGET_SOURCE=orion_live_radar_cache`
  - `RESUME_ACTION=resume_observation`
  - `CONTINUATION_RESULT=signature_changed`
  - `FINAL_QIKI_STATUS=confirmed`
- BIOS smoke:
  - `OK: received bios status on qiki.events.v1.bios_status`

Healthy interpretation details:
- `signature_changed` remains closed with evidence on the same canonical resumed contour
- ORION procedure loading is working on the canonical resumed smoke path
- BIOS support behavior is healthy when the support-tier smoke passes and BIOS semantics remain truthful
- resumed-path observability remains healthy when contour identity, q-core identity, public-track identity, comparison label, and result candidate stay visible in the maintained logs/tests

## 5. Maintenance-level failure handling

Treat the issue as maintenance-level by default when:
- BIOS smoke fails
- registrar or BIOS contract sanity fails in the targeted unit slice
- a service is simply not up during pack preflight
- logging/diagnostic regressions fail their narrow guard without proving the closed resumed contour is broken
- wrapper/docs/help drift makes maintenance work less clear but does not falsify runtime baseline

Maintenance handling flow:
1. Confirm the issue is on the canonical contour, not a legacy path.
2. Re-run the narrow relevant command or the minimal regression pack.
3. Check saved wrapper logs and the relevant operator/q-core/BIOS logs.
4. Fix the narrow maintenance issue without reverting to blocker-era framing.

Post-closure rule:
- a red step in the minimal pack is not automatically a reopened P0

## 6. When to escalate to blocker-level

Escalate only when fresh evidence shows that the already-closed canonical resumed-observation baseline is broken again.

Blocker-candidate conditions:
- canonical resumed observation smoke cannot execute the intended resumed contour on the current canonical stack
- required resumed-smoke markers are missing, especially:
  - `CONTINUATION_RESULT=signature_changed`
  - `FINAL_QIKI_STATUS=confirmed`
- ORION procedure loading is broken on the exact canonical resumed-smoke path badly enough that the resumed closeout cannot run
- a regression clearly falsifies same-contour resumed `signature_changed` closure, not just auxiliary diagnostics

Do not escalate to blocker-level from:
- BIOS-only smoke failures by themselves
- helper/logging noise by itself
- stack-start accidents without proof of contour regression
- historical artifacts or legacy paths

If severity is ambiguous:
- classify as maintenance-level first
- escalate only after confirming the current canonical resumed-observation path is actually broken

## 7. References to current source-of-truth docs

Primary source-of-truth docs for this maintenance layer:
- [docs/ORION_V_RUNBOOK.md](/home/sonra44/QIKI_DTMP/docs/ORION_V_RUNBOOK.md)
- [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md)
- [TASK_OUT/regression_pack_canonization.md](/home/sonra44/QIKI_DTMP/TASK_OUT/regression_pack_canonization.md)
- [TASK_OUT/regression_failure_severity_map.md](/home/sonra44/QIKI_DTMP/TASK_OUT/regression_failure_severity_map.md)
- [TASK_OUT/qbios_contract_and_resilience.md](/home/sonra44/QIKI_DTMP/TASK_OUT/qbios_contract_and_resilience.md)
- [TASK_OUT/resumed_observability_baseline_lock.md](/home/sonra44/QIKI_DTMP/TASK_OUT/resumed_observability_baseline_lock.md)

Use this runbook as the practical maintenance entrypoint, and use the linked files when you need the narrower contract or evidence details behind a specific maintenance decision.
