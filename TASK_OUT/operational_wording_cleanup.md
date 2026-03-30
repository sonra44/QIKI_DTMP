# Operational Wording Cleanup

Date: 2026-03-25

## 1. Docs checked

Active operational docs / baseline notes checked:
- [docs/ORION_V_RUNBOOK.md](/home/sonra44/QIKI_DTMP/docs/ORION_V_RUNBOOK.md)
- [docs/CUTOVER_PLAN.md](/home/sonra44/QIKI_DTMP/docs/CUTOVER_PLAN.md)
- [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md)
- [TASK_OUT/canonical_runtime_maintenance_runbook.md](/home/sonra44/QIKI_DTMP/TASK_OUT/canonical_runtime_maintenance_runbook.md)
- [TASK_OUT/resumed_path_observability_hardening.md](/home/sonra44/QIKI_DTMP/TASK_OUT/resumed_path_observability_hardening.md)
- [TASK_OUT/minimal_regression_pack_wrapper.md](/home/sonra44/QIKI_DTMP/TASK_OUT/minimal_regression_pack_wrapper.md)

## 2. Residual blocker-era wording found

1. [docs/CUTOVER_PLAN.md](/home/sonra44/QIKI_DTMP/docs/CUTOVER_PLAN.md) still used a `Recovery note` section and wording that leaned on blocker closure framing more than current maintenance framing.

2. [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md) still had a section titled `Tasks no longer needed` with several bullets phrased as emergency/blocker investigations, even though the document already defines the slice as hardening/maintenance/regression.

3. [TASK_OUT/canonical_runtime_maintenance_runbook.md](/home/sonra44/QIKI_DTMP/TASK_OUT/canonical_runtime_maintenance_runbook.md) still used a couple of `post-blocker` / `blocker-proof replay` / `blocker-era framing` phrases where simpler maintenance wording was enough.

## 3. Fixes made

1. In [docs/CUTOVER_PLAN.md](/home/sonra44/QIKI_DTMP/docs/CUTOVER_PLAN.md):
- changed `Recovery note` to `Current baseline note`
- reframed the old `M4` reference as historical closure context
- changed the forward-looking wording to maintenance-oriented reproducibility/regression proof

2. In [TASK_OUT/final_stabilization_and_baseline.md](/home/sonra44/QIKI_DTMP/TASK_OUT/final_stabilization_and_baseline.md):
- renamed `Tasks no longer needed` to `Workstreams intentionally out of current maintenance scope`
- rephrased the bullets so they describe current out-of-scope framing instead of sounding like an active emergency docket
- softened `blocker-era wording` / `emergency proof gaps` wording in the next-workstream section to match the current maintenance mode

3. In [TASK_OUT/canonical_runtime_maintenance_runbook.md](/home/sonra44/QIKI_DTMP/TASK_OUT/canonical_runtime_maintenance_runbook.md):
- changed `post-blocker maintenance baseline` to `current maintenance baseline`
- changed `historical blocker-proof replay bundle` to a less blocker-centric historical-proof phrasing
- changed `without reopening blocker-era framing` to `without reverting to blocker-era framing`

## 4. What remains historical by design

- Historical/superseded investigation artifacts remain unchanged by design.
- Explicit references to historical closure are still allowed where they clarify that an old blocker is already closed and not current.
- Docs whose purpose is to document a cleanup or closure pass, such as [TASK_OUT/post_blocker_doc_cleanup.md](/home/sonra44/QIKI_DTMP/TASK_OUT/post_blocker_doc_cleanup.md), still naturally mention blocker-era wording because that is their subject.

## 5. Current operational framing now

- Active operational docs now read the current slice primarily as `hardening / maintenance / regression`.
- Canonical contour remains the default runtime path, not an emergency workaround.
- Minimal regression pack remains the default operational gate for the slice, without reading like blocker replay.
- Historical blocker closure stays documented, but the operational docs no longer frame day-to-day work as emergency investigation mode.
