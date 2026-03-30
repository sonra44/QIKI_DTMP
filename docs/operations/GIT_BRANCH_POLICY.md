# Git Branch Policy (Hard Rule)

## Core Contract

- One task = one branch = one PR.
- New task must start from fresh `main`.
- Mixed scopes in one branch are forbidden.

## Branch Naming

- Required pattern: `task-<id>-<slug>`
- Example: `task-0034-onecontext-audit-fixes`

## Linear Flow

1. `git checkout main`
2. `git pull --ff-only origin main`
3. `git checkout -b task-XXXX-short-name`
4. Implement only this task.
5. Run checks.
6. `git push -u origin task-XXXX-short-name`
7. Open one PR for this branch.
8. After merge: delete local and remote branch.

## GitHub Review Gate (Mandatory)

- Any push to GitHub must be followed by GitHub-side checks and review signals inspection.
- Merge to `main` is allowed only after:
  1. Required GitHub checks are green (`load`, `Sourcery review`, `CodeRabbit`).
  2. Review bots/reviewers (CodeRabbit/GitHub reviewers/CI annotations) feedback is analyzed.
  3. Required fixes are applied (or explicitly justified in PR discussion).
  4. `@codex review` was requested and findings were addressed.
- If checks fail, do not merge; fix and push again, then re-check.
- If no PR exists, create PR first; `main` is updated only through PR merge.

## Hard Prohibitions

- Do not start a second task in an existing branch.
- Do not keep long-lived mixed-purpose branches.
- Do not continue committing to a merged branch.

## Sync Policy

- Before PR: sync branch with `main` via `rebase`.
- Use one strategy per branch: either rebase-only or merge-only.
- Default: rebase-only.

## Pre-PR Checklist

- Branch matches `task-<id>-<slug>`.
- Changes match one task scope.
- Local checks are green.
- `git status` has no unrelated files.
- GitHub checks/review gate plan is prepared (who/what is required to pass).

## Automation

Use `scripts/branch_policy_check.sh` before push/PR:

```bash
bash scripts/branch_policy_check.sh
```
