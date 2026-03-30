# Resumed Path Observability Hardening

Date: 2026-03-25

Current baseline note:
- This observability surface is part of the current maintained hardening baseline for the canonical resumed-observation slice.
- Treat these log fields as supported post-closure observability, not as temporary blocker-era instrumentation.

## Goal

Keep the resumed observation path diagnostically observable after future changes, without changing ORION/q-core decision semantics.

## Scope

Narrow hardening only:
- ORION resumed-path diagnostic logs;
- the q-core helper log that exposes resumable contour lookup;
- one narrow regression test for key diagnostic fields.

No business-logic changes were made to ORION, q-core, or bridge decision rules.

## Current supported and maintained diagnostic surface

### ORION live snapshot log

File:
- [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py)

Log point:
- `Resume live snapshot: ...`

Fields kept visible:
- contour identity: `objective_id`, `request_id`, `target`
- previous contour state: `previous_track_id`, `previous_label`
- q-core identity: `qcore_track_id`, `qcore_label`
- public-track identity: `public_track_id`, `public_label`, `live_track_id`, `live_label`
- source/freshness: `source`, `source_ts`, `freshness_s`, `label_source`

### ORION comparison log

File:
- [src/qiki/services/operator_console/orion_v/app.py](/home/sonra44/QIKI_DTMP/src/qiki/services/operator_console/orion_v/app.py)

Log point:
- `Resume comparison: ...`

Hardening applied:
- kept contour identity visible;
- added explicit previous/comparison public-track identity fields so comparison logs no longer rely on implicit inference from `comparison_track_id` alone.

Fields now visible:
- contour identity: `objective_id`, `request_id`, `target`
- contour/q-core comparison identity: `previous_track_id`, `comparison_track_id`
- public-track identity: `previous_public_track_id`, `previous_public_label`, `comparison_public_track_id`, `comparison_public_label`
- comparison label/result surface: `comparison_label`, `result_candidate`, `fallback_reason`
- provenance/freshness: `comparison_source`, `comparison_label_source`, `comparison_source_ts`, `comparison_freshness_s`

### q-core resumable objective lookup

File:
- [src/qiki/services/q_core_agent/qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/src/qiki/services/q_core_agent/qiki_orion_intents_service.py)

Log point:
- `Resume objective lookup: ...`

Hardening applied:
- normalized field names away from ambiguous `previous_*`;
- now logs `qcore_track_id`, `qcore_label`, `public_track_id`, `public_label`.

This keeps the helper terminology aligned with the ORION resumed-path logs.

## What was fragile before

- `Resume live snapshot` already exposed both q-core and public identities, but `Resume comparison` did not explicitly preserve public-track identity in the log line.
- The q-core lookup helper used older `previous_*` names, which made cross-reading with ORION logs less stable.
- That combination made future regressions harder to localize when the resumed path still worked but identity visibility drifted.

## Changes made

1. Normalized helper field names
- q-core resume lookup now uses:
  - `qcore_track_id`
  - `qcore_label`
  - `public_track_id`
  - `public_label`

2. Strengthened ORION comparison diagnostics
- comparison log now explicitly includes:
  - `previous_public_track_id`
  - `previous_public_label`
  - `comparison_public_track_id`
  - `comparison_public_label`

3. Added narrow regression guards
- File: [tests/unit/test_orion_v_qiki_loop.py](/home/sonra44/QIKI_DTMP/tests/unit/test_orion_v_qiki_loop.py)
- New test:
  - `test_resume_comparison_log_keeps_qcore_and_public_identities`
- File: [tests/unit/test_qiki_orion_intents_service.py](/home/sonra44/QIKI_DTMP/tests/unit/test_qiki_orion_intents_service.py)
- New test:
  - `test_find_resumable_observation_objective_logs_qcore_and_public_identity`

These tests assert that the maintained resumed-path logs keep:
- contour identity;
- q-core identity;
- public-track identity;
- `comparison_label`;
- `result_candidate`;
- `fallback_reason`.

## Verification

Ran:

```bash
docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q \
  tests/unit/test_orion_v_qiki_loop.py::test_live_observation_track_snapshot_logs_public_identity_without_format_noise \
  tests/unit/test_orion_v_qiki_loop.py::test_resume_comparison_log_keeps_qcore_and_public_identities \
  tests/unit/test_qiki_orion_intents_service.py::test_find_resumable_observation_objective_logs_qcore_and_public_identity \
  tests/unit/test_orion_v_qiki_loop.py::test_resumed_safe_observation_uses_public_track_binding_for_live_signature_change
```

Result:
- `4 passed`

## Done check

- resumed path remains diagnostically readable at the supported ORION/q-core log points;
- contour identity, q-core identity, public-track identity, comparison label, and result candidate remain visible;
- narrow regression guards now cover both ORION-side and q-core helper-side loss of these key diagnostic fields;
- decision rules and business semantics were not changed.
