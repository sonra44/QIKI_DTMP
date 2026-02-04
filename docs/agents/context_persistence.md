# Context Persistence (QIKI_DTMP) — “Nothing gets lost”

## Goals
- New session must start with context (no “amnesia”).
- Progress must be provable and recoverable (git + sovereign-memory + backups).
- Canon drift must be detected early (no second boards, no duplicate plans).

## Canon entrypoints (read first)
- Session bootstrap: `~/MEMORI/ПРОЧТИ_ЭТО_QIKI_DTMP.md`
- Operational invariants: `~/MEMORI/OPERATIVE_CORE_QIKI_DTMP.md`
- Canon task board: `~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md` (**single source of truth** for Now/Next)
- Dev protocol: `~/MEMORI/DEV_WORK_PROTOCOL_QIKI_DTMP.md`
- Design canon entrypoint: `docs/design/canon/INDEX.md`

## Skills (recommended)
Repo-tracked skills live in `QIKI_DTMP/.codex/skills/` and are installed into `~/.codex/skills/` via symlinks.

Install/update:
```bash
bash QIKI_DTMP/scripts/install_codex_skills.sh
```

### What to use
- `$qiki-bootstrap`: load memory + open canon + concise summary.
- `$qiki-checkpoint`: end-of-loop save (`STATUS/TODO_NEXT/(DECISIONS)`) + recall proof + git state.
- `$qiki-drift-audit`: detect canon drift (second boards / missing canon entrypoints).
- `$sovmem-health`: verify MCP + logs + backups (soft gate by default).

## End-of-loop contract (soft gate)
At the end of every “task loop”:
1) Save:
   - `STATUS` (episodic)
   - `TODO_NEXT` (episodic)
   - `DECISIONS` (core) only if new invariants/decisions were introduced
2) Immediately recall-by-tags and show the **IDs** as proof.
3) Capture `git status --porcelain` + `git rev-parse HEAD` (even if no commit yet).

If sovereign-memory is down:
- Do not “continue as if fine”.
- Write the checkpoint into the current `TASKS/TASK_*.md` evidence section and fix MCP before relying on memory again.

## Backups (DB + MEMORI)
We back up:
- `/opt/sovereign-memory/memory.db` (agent memory DB)
- `~/MEMORI/` (canonical board + protocols + reports)

Install the daily backup timer:
```bash
bash QIKI_DTMP/scripts/install_context_timers.sh
```

Health check:
```bash
bash QIKI_DTMP/scripts/qiki_sovmem_health.sh
```

Restore drill: see `docs/analysis/context_persistence_restore_drill.md`.

