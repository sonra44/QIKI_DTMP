---
name: qiki-checkpoint
description: End-of-loop checkpoint for QIKI_DTMP. Requires STATUS/TODO_NEXT/DECISIONS save with recall proof (IDs) plus git state evidence, without hard-blocking work (soft gate).
---

# QIKI_DTMP — End-of-Loop Checkpoint (Soft Gate)

## Goal
Prevent drift between sessions by producing **two independent proofs**:
1) Git state (what changed)
2) Sovereign Memory evidence (saved + recall IDs)

## Procedure (strict order)

1) Capture repo evidence:
   - Run `git status --porcelain` and `git rev-parse HEAD`.
   - If there are uncommitted changes: state why they exist and what they are (1–3 lines).

2) Write 2–3 memories (short, 5–15 lines each):
   - `STATUS` (episodic): what is done / what is working / what is not done.
   - `TODO_NEXT` (episodic): the next concrete step with exact commands and expected output.
   - `DECISIONS` (core): ONLY long-lived invariants/decisions; skip if no new decisions.

Use:
   - `mcp__sovereign-memory__add_memory(...)` with `project="QIKI_DTMP"` and `topic="STATUS"/"TODO_NEXT"/"DECISIONS"`.

3) Immediate proof (must show IDs):
   - `mcp__sovereign-memory__recall_by_tags(project="QIKI_DTMP", topic="STATUS", limit=5)`
   - `mcp__sovereign-memory__recall_by_tags(project="QIKI_DTMP", topic="TODO_NEXT", limit=5)`
   - If `DECISIONS` was written: `mcp__sovereign-memory__recall_by_tags(project="QIKI_DTMP", topic="DECISIONS", limit=5)`

4) Report (concise):
   - Print the memory IDs you just created and the `git rev-parse HEAD`.

## Soft gate behavior
- If MCP is down or recall fails: print a WARN and switch to “manual capture” in `QIKI_DTMP/TASKS/<task>.md` (evidence section) until MCP is restored.

