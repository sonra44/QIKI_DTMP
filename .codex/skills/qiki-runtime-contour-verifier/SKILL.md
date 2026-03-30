---
name: qiki-runtime-contour-verifier
description: Verify that work is targeting the canonical QIKI_DTMP runtime contour before debugging, triage, or declaring a fix. Use for compose/entrypoint/ownership confusion, post-restart validation, and "is this the live contour?" checks.
---

# QIKI Runtime Contour Verifier

Confirm that the agent is reasoning about the real canonical contour, not a stale or secondary launch path.

## Use when

- runtime behavior is being debugged
- compose or entrypoint files changed
- a service owner or subject owner is unclear
- a fix claim depends on the stack that is actually running

## Do not use when

- the task is pure code editing with no runtime claim
- the request is broad architecture mapping; use existing canon/passport workflows instead

## Required invariants

- Reuse `qiki-bootstrap` first if session context is not fresh.
- Docker-first for runtime proof.
- Serena-first for repo reading and search where practical.
- Current code and active board beat stale RE or historical notes.
- Do not create a second canon or alternate runtime map.

## Evidence targets

- `docker-compose.phase1.yml`
- `docker-compose.operator.yml`
- `scripts/run_orion_v_live.sh`
- `docs/ORION_V_RUNBOOK.md`
- `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
- current runtime state: `docker compose ... ps`, health endpoints, tmux pane capture if ORION live is relevant

## Procedure

1. State the contour claim in one line: what stack the task assumes is canonical.
2. Read the active board and current runbook/compose files.
3. Verify actual entrypoints and service names from code and scripts.
4. If runtime matters, prove live state with one short Docker check and one service-specific proof:
   - `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps`
   - health or log proof for the relevant service
   - tmux capture if the live ORION path is in scope
5. Identify subject or ownership expectations only after the contour is proven.
6. Output the smallest safe next command or file to inspect.

## Output

- `Contour:` canonical or not-canonical
- `Evidence:` exact files/commands that support the verdict
- `Mismatch:` missing service, wrong entrypoint, wrong compose pair, or none
- `Next safe step:` one concrete command or file

## Rules

- Prefer a short verdict over a long essay.
- If the contour is not proven, do not claim the bug is fixed.
- If docs and runtime disagree, mark docs as stale instead of inventing a blended truth.
