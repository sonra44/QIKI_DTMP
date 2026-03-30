# Post-Blocker Doc Cleanup

Date: 2026-03-25

## Scope

Narrow cleanup after closure of the `signature_changed` blocker.

Applied constraints:
- no documentation rewrite;
- only confirmed stale statements were changed;
- historical investigation artifacts were preserved, but explicitly marked as historical where they could be mistaken for the current baseline.

## Current canon held explicitly

- canonical stack: `docker-compose.phase1.yml` + `docker-compose.operator.yml`
- canonical operator path: ORION V
- current mode for this slice: `hardening / maintenance / regression cleanup`
- do not reopen contour or ownership redesign without fresh regression evidence

## Confirmed stale statements cleaned

1. Active runbook stale rebaseline wording
- File: [docs/ORION_V_RUNBOOK.md](/home/sonra44/QIKI_DTMP/docs/ORION_V_RUNBOOK.md)
- Removed stale language implying `M4` was still open and pilot/default wording remained conditionally blocked by rebaseline status.
- Replaced with current baseline wording: ORION V is the supported canonical path on `docker-compose.phase1.yml` + `docker-compose.operator.yml`, and follow-up is hardening/regression work.

2. Active cutover plan conditional blocker wording
- File: [docs/CUTOVER_PLAN.md](/home/sonra44/QIKI_DTMP/docs/CUTOVER_PLAN.md)
- Updated `ORION V only` mode so it no longer reads as conditional on a still-open blocker.
- Kept rollback/cutover structure intact.

3. Active contour dossier stale proof-stage wording
- File: [TASK_OUT/observation_contour_dossier.md](/home/sonra44/QIKI_DTMP/TASK_OUT/observation_contour_dossier.md)
- Updated `signature_changed` from `Proof-stage` to `Closed with evidence`.
- Replaced stale unresolved/proof-stage language with the current post-closure baseline.
- Explicitly retained the rule that redesign should not be reopened without fresh regression evidence.

## Historical artifacts preserved as historical

1. Investigation artifact
- File: [TASK_OUT/signature_changed_blocker_investigation.md](/home/sonra44/QIKI_DTMP/TASK_OUT/signature_changed_blocker_investigation.md)
- Added a top historical note stating that the file is superseded by the later canonical live proof and stabilization baseline.

2. Failed pre-closure proof artifact
- File: [TASK_OUT/live_signature_changed_proof.md](/home/sonra44/QIKI_DTMP/TASK_OUT/live_signature_changed_proof.md)
- Added a top historical note stating that the file preserves the earlier failed proof attempt and is not the current truth.

## Left unchanged on purpose

- [TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md](/home/sonra44/QIKI_DTMP/TASKS/TASK_20260313_g3_qiki_second_observation_result_signature_changed.md)
  already reflects closure plus a clearly separated historical section, so no additional rewrite was needed.

## Done check

- Active docs/runbooks no longer state that `signature_changed` is still proof-stage or an open blocker.
- Active canonical wording consistently points to `docker-compose.phase1.yml` + `docker-compose.operator.yml` and ORION V as the operator path.
- Historical artifacts remain available, but now identify themselves as superseded historical context instead of current truth.
