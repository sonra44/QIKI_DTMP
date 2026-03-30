# Active Docs Consistency Cleanup

Date: 2026-03-25

## 1. Какие документы проверены

Active/current baseline files checked:
- [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md)
- [TASK_OUT/observation_contour_dossier.md](/home/sonra44/QIKI_DTMP/TASK_OUT/observation_contour_dossier.md)
- [TASK_OUT/resumed_path_observability_hardening.md](/home/sonra44/QIKI_DTMP/TASK_OUT/resumed_path_observability_hardening.md)
- [TASK_OUT/minimal_regression_pack_wrapper.md](/home/sonra44/QIKI_DTMP/TASK_OUT/minimal_regression_pack_wrapper.md)
- [docs/CUTOVER_PLAN.md](/home/sonra44/QIKI_DTMP/docs/CUTOVER_PLAN.md)
- [docs/ORION_V_RUNBOOK.md](/home/sonra44/QIKI_DTMP/docs/ORION_V_RUNBOOK.md)

Separately checked for drift risk:
- [TASK_OUT/qbios_contract_and_resilience.md](/home/sonra44/QIKI_DTMP/TASK_OUT/qbios_contract_and_resilience.md)
- [QIKI_CODEX_AUDIT_FOR_TASKING.md](/home/sonra44/QIKI_DTMP/QIKI_CODEX_AUDIT_FOR_TASKING.md)

Repo-wide sanity pass targets:
- active `docs/**` and `TASK_OUT/**` for stale claims that `signature_changed` is still open/proof-stage
- stale claims that procedure-loading remains the primary blocker
- stale claims that seed-smoke instability remains the primary blocker

## 2. Какие несостыковки были найдены

1. [TASK_OUT/qbios_contract_and_resilience.md](/home/sonra44/QIKI_DTMP/TASK_OUT/qbios_contract_and_resilience.md) still described the ORION BIOS first-load projection drift (`components` vs `post_results`) as an active mismatch and as a current next-task candidate.

2. [QIKI_CODEX_AUDIT_FOR_TASKING.md](/home/sonra44/QIKI_DTMP/QIKI_CODEX_AUDIT_FOR_TASKING.md) still read like a live tasking baseline even though it contains blocker-era statements such as `signature_changed` being proof-stage / not yet live-proven.

3. The checked current baseline files were already aligned on the main post-closure truth:
- `signature_changed` closed with evidence
- procedure loading not the blocker
- seed-smoke instability not the blocker
- current mode = hardening/regression/cleanup

## 3. Что исправлено

1. In [TASK_OUT/qbios_contract_and_resilience.md](/home/sonra44/QIKI_DTMP/TASK_OUT/qbios_contract_and_resilience.md):
- added a top current-baseline note
- changed the downstream ORION BIOS projection wording so current baseline now states device count comes from `post_results`
- converted the old `components` drift entry into explicit historical/resolved wording
- replaced `Minimal next task candidates` with status-oriented follow-up notes so the file no longer reopens that already-fixed drift as current work

2. In [QIKI_CODEX_AUDIT_FOR_TASKING.md](/home/sonra44/QIKI_DTMP/QIKI_CODEX_AUDIT_FOR_TASKING.md):
- added a prominent top marker: `Historical / superseded pre-closure audit`
- linked the current source-of-truth files for this slice
- explicitly warned that proof-stage/open-blocker statements below belong to historical context only

## 4. Что помечено как historical / superseded

- [QIKI_CODEX_AUDIT_FOR_TASKING.md](/home/sonra44/QIKI_DTMP/QIKI_CODEX_AUDIT_FOR_TASKING.md) is now explicitly marked as a historical / superseded pre-closure audit.
- Within [TASK_OUT/qbios_contract_and_resilience.md](/home/sonra44/QIKI_DTMP/TASK_OUT/qbios_contract_and_resilience.md), the old ORION BIOS projection drift is now marked as historical/resolved rather than current work.
- Pre-closure `signature_changed` investigations remain historical/reference-only artifacts, with the active baseline carried by the current post-closure docs.

## 5. Какие active docs теперь считаются current source of truth

Primary current baseline for this slice:
- [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md)
- [TASK_OUT/observation_contour_dossier.md](/home/sonra44/QIKI_DTMP/TASK_OUT/observation_contour_dossier.md)
- [TASK_OUT/resumed_path_observability_hardening.md](/home/sonra44/QIKI_DTMP/TASK_OUT/resumed_path_observability_hardening.md)
- [TASK_OUT/minimal_regression_pack_wrapper.md](/home/sonra44/QIKI_DTMP/TASK_OUT/minimal_regression_pack_wrapper.md)
- [docs/CUTOVER_PLAN.md](/home/sonra44/QIKI_DTMP/docs/CUTOVER_PLAN.md)
- [docs/ORION_V_RUNBOOK.md](/home/sonra44/QIKI_DTMP/docs/ORION_V_RUNBOOK.md)
- [TASK_OUT/qbios_contract_and_resilience.md](/home/sonra44/QIKI_DTMP/TASK_OUT/qbios_contract_and_resilience.md) for the BIOS support-tier contract/resilience semantics

## 6. Остались ли ещё документные конфликты

- No explicit pre-closure contradiction was found in the checked active/current docs for:
  - `signature_changed` still being open/proof-stage
  - procedure-loading still being the primary blocker
  - seed-smoke instability still being the primary blocker
- Historical artifacts still exist in the repo, but the main blocker-era audit is now clearly labeled so the next agent should not confuse it with the current baseline.
- Some older non-baseline BIOS design/task references mentioned inside [TASK_OUT/qbios_contract_and_resilience.md](/home/sonra44/QIKI_DTMP/TASK_OUT/qbios_contract_and_resilience.md) may still contain legacy contract wording, but they are not active/current source-of-truth files for this slice and were not reopened as a new task stream in this cleanup.
