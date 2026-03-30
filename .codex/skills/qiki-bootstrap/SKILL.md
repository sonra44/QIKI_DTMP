---
name: qiki-bootstrap
description: QIKI_DTMP session bootstrap. Loads sovereign-memory context, reads canon entrypoints, and produces a concise "where we are / what's next" summary.
---

# QIKI_DTMP — Session Bootstrap

## Goal
Start every new Codex session in a **non-amnesiac** state: memory loaded, canons opened, and the next step explicit.

## Procedure (strict order)

1) Load sovereign memory in one call:
   - `mcp__sovereign-memory__load_context(project="QIKI_DTMP", include_server=true, limit_per_topic=5)`

2) Deterministic tag recalls (proof-friendly):
   - `mcp__sovereign-memory__recall_by_tags(project="QIKI_DTMP", topic="STATUS", limit=5)`
   - `mcp__sovereign-memory__recall_by_tags(project="QIKI_DTMP", topic="TODO_NEXT", limit=5)`
   - `mcp__sovereign-memory__recall_by_tags(project="QIKI_DTMP", topic="DECISIONS", limit=5)`
   - `mcp__sovereign-memory__recall_by_tags(project="QIKI_DTMP", topic="TASKS", limit=5)`
   - `mcp__sovereign-memory__recall_by_tags(project="QIKI_DTMP", topic="DEV_METHODS", limit=5)`

3) Read canon entrypoints (do not infer; read files):
   - `~/MEMORI/OPERATIVE_CORE_QIKI_DTMP.md`
   - `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`
   - `~/MEMORI/DEV_WORK_PROTOCOL_QIKI_DTMP.md`
   - `QIKI_DTMP/LOG.MD` (product schema source; not implementation canon, but mandatory meaning-layer)
   - `QIKI_DTMP/docs/design/canon/INDEX.md`
   - `QIKI_DTMP/docs/INDEX.md` (recommended canon entrypoint)

4) Output a summary (8–12 lines max):
   - Where we stopped (facts, not guesses)
   - What is important right now (from `ACTIVE_TASKS`)
   - Product schema in 2-3 lines (from `LOG.MD`: what the project really is, how QIKI behaves, what truth-policy governs UI/data)
   - Next step (from `TODO_NEXT`), with exact command(s)/file(s)

## Guardrails
- Docker-first / Serena-first / memory-proof discipline are mandatory (see `~/MEMORI/OPERATIVE_CORE_QIKI_DTMP.md`).
- Never reduce the product to “digital twin platform” language if `LOG.MD` and active canons describe a harder sim-game/operator/QIKI model.
- If any canon conflicts are detected, stop and run `$qiki-drift-audit` before coding.
- Keep the trust hierarchy explicit:
  `code verification > active canon/docs > working evidence > handoff/snapshot > archive/reference`.
- If you consult `/home/sonra44/QIKI_DTMP/.codex/imp`, treat it as a governance/reference pack only.
  Do not import its slice status, blockers, or closure claims without revalidating against current board, memory, and runtime.
- Separate three kinds of statements in the bootstrap summary:
  `fact` = current code/board/runtime truth,
  `inference` = analytical reading,
  `policy` = adopted workflow or canon rule.
