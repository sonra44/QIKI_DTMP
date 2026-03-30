# Contributing to QIKI_DTMP

This repository uses a strict, reproducible workflow.  
В этом репозитории используется строгий воспроизводимый workflow.

## Branching Model / Модель Ветвления

1. Start from fresh `main`.
2. Create one task branch per task.
3. Open exactly one PR for that branch.

Required branch format:
- `task-<4+digits>-<slug>`
- Example: `task-0042-github-normalization`

## Local Pre-PR Checks / Локальные Проверки Перед PR

Run from repo root:

```bash
bash scripts/branch_policy_check.sh
bash scripts/quality_gate_docker.sh
bash scripts/qiki_drift_audit.sh --strict
```

If your slice needs extra validation, run targeted tests and include command output in PR body.

## GitHub Review Gate (Mandatory) / Обязательный GitHub-гейт

Merge to `main` is allowed only after:
1. Required checks are green:
   - `load`
   - `Sourcery review`
   - `CodeRabbit`
2. At least one PR approval exists.
3. Review conversations are resolved.
4. Bot/human feedback is analyzed and addressed (or explicitly justified).
5. `@codex review` is requested and processed.

## PR Quality / Качество PR

Use `.github/pull_request_template.md` and fill all mandatory sections:
- What changed / Why
- Reproduction command
- Before/After
- Impact metric
- Scope / Non-goals

Keep PR scope single-purpose. Mixed scopes are not accepted.

## Operational Rules / Операционные Правила

- Docker-first validation.
- No-mocks in operator UI (`N/A/—` instead of invented values).
- Do not commit local runtime artifacts (including `.onecontext/`).
