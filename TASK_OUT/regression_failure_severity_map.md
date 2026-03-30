# Regression Failure Severity Map

Date: 2026-03-25

## 1. Regression steps

Current minimal regression pack entry:

```bash
bash scripts/run_minimal_regression_pack.sh
```

Current steps:
1. Targeted unit regression pack
2. Canonical resumed observation smoke
3. BIOS live support-tier smoke

Operational baseline:
- this pack is a narrow gate for the current post-closure resumed-observation slice
- a red step is not automatically a reopened P0
- P0 should be reopened only when a failure directly falsifies the already-closed canonical slice claim

## 2. Blocker-level failures

Treat as blocker-level only when the failure directly breaks the current closed canonical slice on the live resumed-observation contour.

Blocker-level for this pack means:
- the canonical resumed-observation path is no longer closing on the same contour as expected
- the live canonical slice can no longer honestly produce the already-closed `signature_changed` result where this pack expects it
- ORION procedure loading on the canonical resumed smoke path is broken badly enough that the canonical resumed smoke cannot execute

Concrete blocker-level cases:
- Canonical resumed observation smoke fails before reaching the intended resumed contour closeout on the canonical stack.
- Canonical resumed observation smoke runs but misses required markers proving the closed contour:
  - `INITIAL_TARGET_SOURCE=orion_live_radar_cache`
  - `RESUME_ACTION=resume_observation`
  - `CONTINUATION_RESULT=signature_changed`
  - `FINAL_QIKI_STATUS=confirmed`
- ORION procedure loading failure on this exact resumed-smoke path prevents the canonical smoke from executing the supported procedure from `/workspace/config/orion_v/procedures`.
- Unit failure clearly shows that same-objective resumed closeout / `signature_changed` semantics are broken again, not merely that auxiliary diagnostics changed.

Interpretation rule:
- blocker-level here means `blocker-candidate for the current slice`
- reopen P0 only after confirming the failure is on the current canonical path, not a legacy path, not an environment accident, and not only diagnostic noise

## 3. Maintenance-level failures

Maintenance-level failures mean the minimal gate is red and needs fixing, but the evidence does not by itself justify reopening the old blocker narrative.

Maintenance-level cases:
- BIOS smoke fails to validate the support-tier BIOS contract on `qiki.events.v1.bios_status`.
- BIOS smoke misses its required marker:
  - `OK: received bios status on qiki.events.v1.bios_status`
- Targeted unit regression pack fails on BIOS contract sanity or registrar contract sanity.
- Targeted unit regression pack fails on ORION procedure-engine baseline in a way that does not by itself prove the live canonical resumed smoke path is broken.
- Pack preflight fails because one required service is not running.
- Wrapper executes but one step exits non-zero before there is enough evidence to say the closed resumed-observation slice itself has regressed.

Specific classification notes:
- ORION procedure loading failures:
  - blocker-level when they break the canonical resumed observation smoke path itself
  - maintenance-level when they appear only in narrower unit/procedure-engine checks without proving the live canonical closeout is broken
- Resumed observation failures:
  - blocker-level when they break the live canonical resumed contour expected by this pack
  - maintenance-level when they are confined to narrower regression scaffolding without live contour break evidence
- `signature_changed` failures:
  - blocker-level when the canonical resumed smoke can no longer produce the already-closed same-contour result
  - maintenance-level when only auxiliary/unit assertions drift without re-breaking the live closed contour
- BIOS smoke failures:
  - maintenance-level by default for this slice
  - they indicate support-tier contract degradation, not automatic P0 reopening of the closed resumed-observation blocker
- Logging/diagnostic noise:
  - maintenance-level only if it causes an asserted regression test in the pack to fail

## 4. Warnings / non-blocking drift

Warnings / non-blocking drift do not fail the current minimal pack semantics by themselves.

Examples:
- extra logging noise or wording drift outside asserted checks / required markers
- less-readable diagnostics where the step still passes and required proof markers are present
- comment/help/runbook drift around the pack, as long as the pack still runs and proves the same slice
- stale historical artifacts elsewhere in the repo that do not change the result of this current pack

Specific note on logging/diagnostic noise:
- if the pack still passes, logging noise is warning/non-blocking drift
- if a targeted regression test for supported diagnostics fails, that becomes maintenance-level, not blocker-level

## 5. Any small output improvements made

Small wrapper-output improvements were added in [scripts/run_minimal_regression_pack.sh](/home/sonra44/QIKI_DTMP/scripts/run_minimal_regression_pack.sh):
- the help text now points to this severity map
- each step prints a short operational interpretation before execution
- failure output repeats the step interpretation so the next agent can see whether the failure is blocker-candidate or maintenance-level by default

No scenario semantics were changed:
- no new heavy checks
- no changed proof markers
- no changed pass/fail gates

## 6. Recommended interpretation rules

1. Start from the narrow rule: red does not automatically mean P0.

2. Treat the canonical resumed observation smoke as the strongest signal in this pack.
- If it fails in a way that breaks the already-closed same-contour resumed `signature_changed` path, treat that as blocker-candidate for the current slice.

3. Treat BIOS smoke and auxiliary contract/unit failures as maintenance-level unless they clearly prove the canonical resumed closeout claim is false.

4. Treat logging/diagnostic regressions as maintenance-level at most.
- They matter for operability and debugging quality, but they do not by themselves reopen the old blocker.

5. Reopen blocker investigation only with fresh evidence from the current canonical path.
- not from legacy ORION
- not from historical proof artifacts
- not from doc drift
- not from a generic stack-start accident alone

6. If the pack fails and the severity is ambiguous, classify it as maintenance-level first, then escalate only after proving that the closed canonical resumed-observation baseline is actually broken.
