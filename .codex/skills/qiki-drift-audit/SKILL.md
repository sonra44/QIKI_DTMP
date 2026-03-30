---
name: qiki-drift-audit
description: Detects canon drift for QIKI_DTMP (second task boards, conflicting docs, missing canon entrypoints). Produces a mismatch→fix list, without applying changes automatically.
---

# QIKI_DTMP — Drift Audit (Canon Guard)

## Goal
Detect “small errors → drift → catastrophe” patterns early: second sources of truth, doc conflicts, and missing evidence.

## Procedure

1) Canon priority board must be single:
   - Canon board is **only** `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`.
   - Repository must not contain competing Now/Next/Backlog boards.

2) Run repo guard script (primary):
   - `bash QIKI_DTMP/scripts/check_no_second_task_board.sh`
   - `bash QIKI_DTMP/scripts/check_reference_truth_boundaries.sh`

3) Verify design canon entrypoint exists:
   - `QIKI_DTMP/docs/design/canon/INDEX.md`

4) Verify archive is treated as reference-only:
   - `QIKI_DTMP/docs/Архив/**` is NOT canon (must be labelled as such in canon docs).
   - `/home/sonra44/QIKI_DTMP/.codex/imp/**` is governance/reference material, not active canon.

5) Check status-bearing reference docs for stale claims:
   - If a reference/governance pack names an old active slice, blocker, or closure state, flag it as drift unless the same claim appears in current board/memory/runtime evidence.
   - If such files lack an explicit current-truth override preamble, treat that as a guard failure, not a cosmetic wording issue.

## Output
- Produce a list:
  - `Mismatch:` what is wrong (file path / symptom)
  - `Risk:` why it causes drift
  - `Fix:` smallest safe change (exact file/command)

## Rules
- Do not create “v2” or duplicate canons; repair the existing canon.
- If multiple plans exist, prefer the board (`~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`) + repo dossiers in `QIKI_DTMP/TASKS/`.
- Use the trust hierarchy when resolving conflicts:
  `code/runtime > active canon > working evidence > handoff/snapshot > archive/reference`.
