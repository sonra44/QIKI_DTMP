# Final Stabilization And Baseline

## 2026-03-29 closeout rerun

- Fresh closeout rerun on the canonical stack is green:
  - `bash scripts/run_minimal_regression_pack.sh` passed all three steps again on `docker-compose.phase1.yml` + `docker-compose.operator.yml`
  - resumed smoke again produced the required markers:
    - `INITIAL_TARGET_SOURCE=orion_live_radar_cache`
    - `RESUME_ACTION=resume_observation`
    - `CONTINUATION_RESULT=signature_changed`
    - `FINAL_QIKI_STATUS=confirmed`
- Fresh ORION V live proof was also recaptured through the canonical tmux path `./scripts/run_orion_v_live.sh`; the captured operator pane showed the same `signature_changed` continuation outcome in the live mission/safety strip.
  - tmux session: `orion_stabilization_proof_20260329`
  - pane: `%17`
  - captured live markers included:
    - `L: F1 Кокпит`
    - `P: RUNNING 1.00x`
    - `Observation continuation outcome подтверждён`
    - `live signature сменилась ... после resume_observation`
- One maintenance-level stabilization fix was required before the rerun passed:
  - `tools/orion_v_qiki_observation_objective_seed_smoke.py` still treated the old cockpit heading `Цель наблюдения:` as a hard gate even though the current live body layout had been compacted.
  - the smoke now gates on contour/result proof rather than stale body-copy wording.

## 1. Current project status

- Canonical runtime contour is stable on the default Phase1/operator stack.
- `signature_changed` is no longer an open blocker. It is closed with live-path evidence on the canonical resumed observation contour.
- The project is now in `hardening / regression / cleanup` mode for this slice, not in `blocker-resolution` mode.
- ORION V remains the canonical operator surface. Legacy/operator-side support surfaces remain available but are not the primary execution path.

## 2. What is now officially closed

- `signature_changed` blocker on the resumed observation contour is closed.
- The blocker is closed on the same canonical objective payload and the same route contour; it was not closed by introducing a new truth source or a redesign.
- The following hypotheses are now removed:
  - procedure loading is not the blocker;
  - generic resumed contour health is not the blocker;
  - seed-smoke instability is not the blocker;
  - the canonical stack does have a reproducible live proof for `signature_changed`.
- Official evidence used in this pass:
  - Docker smoke: `QIKI_OBSERVATION_STYLE=slow QIKI_RESUME_XPDR_MODE=SPOOF python tools/orion_v_qiki_observation_objective_seed_smoke.py`
  - Observed result: `CONTINUATION_RESULT=signature_changed`
  - Observed continuity: same `CONTINUED_OBJECTIVE_ID`, `RESUME_ACTION=resume_observation`, `NEXT_ALLOWED_STEP=safe observation`

## 3. What was cleaned in this pass

- Fixed the `Resume live snapshot` logging-format mismatch in [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py).
- Added a narrow regression test for that logging path in [tests/unit/test_orion_v_qiki_loop.py](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_qiki_loop.py).
- Updated the `signature_changed` dossier status from proof-stage to closed-with-evidence in [TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md](/home/sonra44/QIKI_DTMP/TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md).
- Rebaselined the canonical external board in [/home/sonra44/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md](/home/sonra44/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md).
- Removed one confirmed stale blocker statement from [docs/CUTOVER_PLAN.md](/home/sonra44/QIKI_DTMP/docs/CUTOVER_PLAN.md).

## 4. Remaining diagnostic noise fixed

- Fixed:
  - `Resume live snapshot` no longer emits logging-format/runtime noise on the resumed live-cache path.
  - The log line now records both q-core contour identity and public-track identity explicitly, which makes resumed-path diagnostics usable again.
  - Resumed-path observability is part of the maintained hardening baseline for this slice, not temporary blocker-era instrumentation.
- Verified by:
  - unit test calling `_live_observation_track_snapshot(...)` and forcing `record.getMessage()` to render successfully;
  - live smoke log lines showing clean `Resume live snapshot` output before and after the signature flip.
- Small runtime note:
  - `tools/bios_status_smoke.py` inside `qiki-dev` must use `NATS_URL=nats://nats:4222`, not the host-default `localhost`, when run from the container. This is an execution detail, not a product defect.

## 5. Recommended regression/acceptance pack

Minimal pack to run after future changes touching ORION/QIKI resumed observation, procedure loading, or support-tier contract surfaces:

1. Targeted unit regression pack

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_qiki_loop.py::test_resumed_safe_observation_records_signature_changed_result_on_same_objective \
  tests/unit/test_orion_v_qiki_loop.py::test_live_observation_track_snapshot_logs_public_identity_without_format_noise \
  tests/unit/test_orion_v_procedure_engine.py \
  src/qiki/services/q_bios_service/tests/test_service_contract.py \
  src/qiki/services/registrar/tests/test_main_contract.py
```

- Covers:
  - resumed identity continuity and `signature_changed`;
  - logging-noise regression on resumed live snapshot;
  - ORION procedure directory resolution/loading baseline;
  - BIOS subject/payload contract sanity;
  - registrar radar fan-in/audit fan-out sanity.
- Result in this pass: `12 passed`.

2. Canonical resumed observation smoke

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc \
  'QIKI_OBSERVATION_STYLE=slow QIKI_RESUME_XPDR_MODE=SPOOF python tools/orion_v_qiki_observation_objective_seed_smoke.py'
```

- Covers:
  - ORION procedure loading on the live stack;
  - observation seed selection from canonical public radar truth;
  - review -> hold -> resume continuity;
  - resumed `signature_changed` closeout on the same contour.
- Required proof markers:
  - `INITIAL_TARGET_SOURCE=orion_live_radar_cache`
  - `RESUME_ACTION=resume_observation`
  - `CONTINUATION_RESULT=signature_changed`
  - `FINAL_QIKI_STATUS=confirmed`

3. BIOS live support-tier smoke

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc \
  'NATS_URL=nats://nats:4222 python tools/bios_status_smoke.py'
```

- Covers:
  - live BIOS event contract on the Phase1 stack;
  - subject/source/version/payload sanity for `qiki.events.v1.bios_status`.
- Result in this pass: `OK: received bios status on qiki.events.v1.bios_status`

Pack intentionally excluded:

- broad full-stack test floods;
- legacy ORION acceptance;
- architecture revalidation work;
- duplicate smokes that do not add new failure detection for this slice.

## 6. Current canonical contour and operator path

- Canonical contour:
  - `docker-compose.phase1.yml` + `docker-compose.operator.yml`
  - `q-sim-service`
  - `q-core-intents`
  - `faststream-bridge`
  - `q-bios-service`
  - `operator-console` running ORION V
  - NATS as the event/control backbone
- Canonical operator path:
  - launch ORION V via `./scripts/run_orion_v_live.sh` or the canonical operator compose path;
  - operator action -> `qiki.intents`;
  - QIKI response -> `qiki.responses.qiki`;
  - objective truth/result projection -> `qiki.events.v1.operator.objectives`;
  - resumed observation continuity uses q-core contour identity plus live public-track identity from ORION radar truth.
- Canonical contour facts for this slice:
  - procedures resolve from canonical ORION V procedure directories;
  - resumed contour closure happens on the existing objective payload;
  - `signature_changed` does not require a second subject or a second truth source.

## 7. Non-canonical/support surfaces status

- Non-canonical surfaces:
  - legacy ORION path in `docker-compose.operator_legacy.yml` remains rollback/diagnostic only;
  - standalone `shell_os` remains a support/diagnostic overlay, not the canonical operator path;
  - historical `TASK_OUT` investigations remain reference artifacts, not live canon.
- Support-tier services:
  - BIOS is active support-tier and healthy on the live stack;
  - registrar contract sanity is relevant and worth keeping in the minimal regression pack;
  - faststream-bridge remains part of the canonical runtime contour for radar/system duties, but it is no longer the place to reopen emergency `signature_changed` investigation unless a new factual regression appears.

## 8. Remaining P1/P2 technical debt

- P1:
  - keep `bash scripts/run_minimal_regression_pack.sh` stable as the canonical minimal regression entry so future work cannot silently reopen resumed-contour regressions;
  - continue small doc/runbook drift cleanup when stale blocker wording is found;
  - keep resumed-path contour identity, q-core identity, public-track identity, comparison label, and result candidate observable in maintained diagnostics.
- P2:
  - widen support-tier runtime smokes only if they start catching real regressions;
  - clean historical proof-stage notes in reference artifacts when they become misleading, but without rewriting archives.

None of the remaining items justify reopening P0 blocker investigation.

## 9. Workstreams intentionally out of current maintenance scope

- treating `signature_changed` as unresolved on the canonical stack;
- repeated search for an alternate live trigger just to justify closure;
- treating procedure-loading diagnosis as the current primary cause;
- treating seed-smoke instability as the current primary cause;
- redesigning bridge/q-core/ORION ownership for this slice without fresh regression evidence.

These should return only if a fresh factual regression appears in the minimal pack above.

## 10. Recommended next workstream in current mode

- Start the next loop as `hardening / maintenance`, not as renewed blocker investigation.
- Recommended order:
  - run `bash scripts/run_minimal_regression_pack.sh` as the default minimal regression entry after changes in this area and before any broader validation;
  - do narrow residual doc/runbook cleanup where older operational wording is still misleading;
  - then move to the next P1/P2 ORION/QIKI hardening slice chosen by product need, not by emergency proof framing.
- Guardrail:
  - do not reopen contour/ownership redesign unless a new regression breaks the pack and gives concrete evidence that the canonical path is no longer stable.
