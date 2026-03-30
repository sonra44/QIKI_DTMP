---
name: qiki-intent-ownership-guardian
description: Verify single ownership of the QIKI intent path on the canonical contour. Use when touching qiki.intents, response subjects, proposal accept/reject flow, or when duplicate replies are suspected.
---

# QIKI Intent Ownership Guardian

Protect the canonical intent path from double handling, stale subscribers, and hidden legacy overlap.

## Use when

- `qiki.intents` behavior is being changed or debugged
- duplicate QIKI replies are suspected
- proposal accept/reject flow looks inconsistent
- compose or env changes may have altered subscriber ownership

## Do not use when

- the task is generic runtime contour proof with no intent-path question
- the issue is a legacy cleanup proposal; use `qiki-legacy-split-audit` for broad keep/remove work

## Required invariants

- First prove the canonical contour with `qiki-runtime-contour-verifier` if stack ownership is unclear.
- There must be one active owner per intent path on the current contour.
- Do not infer ownership from old docs if compose/env/code disagree.
- Mark legacy paths as residue, not active canon, unless runtime proof says otherwise.

## Evidence targets

- `docker-compose.phase1.yml`
- `src/qiki/services/faststream_bridge/app.py`
- `src/qiki/services/q_core_agent/qiki_orion_intents_service.py`
- `src/qiki/services/qiki_chat/handler.py`
- `src/qiki/services/operator_console/orion_v/app.py`
- `src/qiki/shared/models/qiki_chat.py`

## Procedure

1. Name the exact intent path or reply path under question.
2. Check compose/env/runtime contour to see which services are expected live.
3. Inspect subscribers and publishers for the relevant subjects.
4. Separate canonical path, disabled path, and legacy residue.
5. Report the single-owner verdict and the nearest double-reply risk.

## Output

- `Intent path:` subject or flow under review
- `Canonical owner:` service/module
- `Other subscribers/publishers:` list or `none`
- `Risk:` double reply / stale legacy / none
- `Safe edit zone:` exact file/module

## Rules

- Do not accept "probably disabled" without compose or code evidence.
- If two owners are live, treat it as a defect until disproven.
- Keep the result contour-specific; ownership can differ across historical modes.
