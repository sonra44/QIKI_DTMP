# Resumed Observability Baseline Lock

Date: 2026-03-25

## 1. Current observability fields

Maintained resumed-path observability points on the current canonical slice:

1. ORION `Resume live snapshot: ...`
- contour/objective identity: `objective_id`, `request_id`, `target`
- previous contour state: `previous_track_id`, `previous_label`
- q-core identity: `qcore_track_id`, `qcore_label`
- public-track identity: `public_track_id`, `public_label`, `live_track_id`, `live_label`

2. ORION `Resume comparison: ...`
- contour/objective identity: `objective_id`, `request_id`, `target`
- q-core/contour identity: `previous_track_id`, `comparison_track_id`
- public-track identity: `previous_public_track_id`, `previous_public_label`, `comparison_public_track_id`, `comparison_public_label`
- comparison surface: `comparison_label`, `result_candidate`, `fallback_reason`

3. q-core helper `Resume objective lookup: ...`
- contour/objective identity: `objective_id`, `request_id`
- q-core identity: `qcore_track_id`, `qcore_label`
- public-track identity: `public_track_id`, `public_label`

## 2. Why they remain important post-closure

- The blocker is closed, but the resumed contour still depends on identity continuity being legible when future changes touch this slice.
- These fields are the maintained observability surface that shows whether the same contour is still being resumed honestly.
- They are needed to distinguish:
  - contour identity
  - q-core identity
  - public-track identity
  - comparison label semantics
  - final `result_candidate`
- Without these fields, future regressions risk looking like vague runtime flakiness instead of a localized continuity or comparison problem.

Post-closure rule:
- treat these logs as supported maintained diagnostics for the canonical resumed-observation slice
- do not treat them as temporary blocker-era investigation residue

## 3. Any wording fixes made

- In [TASK_OUT/resumed_path_observability_hardening.md](/home/sonra44/QIKI_DTMP/TASK_OUT/resumed_path_observability_hardening.md), added a current-baseline note stating that the surface is maintained post-closure and not temporary blocker instrumentation.
- In [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md), clarified that resumed-path observability belongs to the maintained hardening baseline.
- In [docs/ORION_V_RUNBOOK.md](/home/sonra44/QIKI_DTMP/docs/ORION_V_RUNBOOK.md), expanded the minimal regression entry guidance so future changes touching resumed-path observability explicitly run the same minimal regression gate.
- In [TASK_OUT/minimal_regression_pack_wrapper.md](/home/sonra44/QIKI_DTMP/TASK_OUT/minimal_regression_pack_wrapper.md), noted that the targeted unit slice preserves the maintained resumed-path observability surface.

## 4. Any narrow regression guard added

Added one narrow helper-side regression guard:
- [tests/unit/test_qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/tests/unit/test_qiki_orion_intents_service.py)
  - `test_find_resumable_observation_objective_logs_qcore_and_public_identity`

Existing ORION-side guards remain in place:
- [tests/unit/test_orion_v_qiki_loop.py](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_qiki_loop.py)
  - `test_live_observation_track_snapshot_logs_public_identity_without_format_noise`
  - `test_resume_comparison_log_keeps_qcore_and_public_identities`

Minimal pack update:
- [scripts/run_minimal_regression_pack.sh](/home/sonra44/QIKI_DTMP/scripts/run_minimal_regression_pack.sh) now includes the helper-side observability guard in its targeted unit regression step.

## 5. Current baseline recommendation

For the current post-closure resumed-observation slice:
- keep these fields as the supported resumed-path observability baseline
- preserve them when touching ORION resumed comparison logic or q-core resumable objective lookup
- treat loss of contour/q-core/public-track identity visibility as a regression against the maintained baseline, even when business logic is unchanged

Operationally:
- use `bash scripts/run_minimal_regression_pack.sh` after changes that touch this slice
- if the pack stays green, the maintained observability surface is still intact
- do not widen logging beyond this surface unless a new concrete regression requires it
