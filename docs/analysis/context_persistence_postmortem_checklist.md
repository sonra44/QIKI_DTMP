# Postmortem Checklist — Context Drift / “Agent forgot” incidents

Use this when you notice any of:
- “We lost the plan” / “agent insists on wrong canon”
- “work was done but not saved”
- “two task boards appeared” / “multiple plans diverged”

## Facts to collect (no guesses)
1) What session/time window? (UTC timestamp)
2) What was the **canon board** state (`~/MEMORI/ACTIVE_TASKS_QIKI_DTMP.md`) at that moment?
3) Sovereign memory health:
   - `tail -n 50 ~/logs/sovereign-memory-smoke.log`
   - `tail -n 50 ~/logs/sovereign-memory-smoke-write.log`
   - `bash QIKI_DTMP/scripts/qiki_sovmem_health.sh --strict`
4) Evidence of save:
   - Did we run end-of-loop checkpoint (`STATUS/TODO_NEXT`) and show recall IDs?
   - If not, why?
5) Drift indicators:
   - `bash QIKI_DTMP/scripts/qiki_drift_audit.sh --strict`
6) Git reality:
   - `git rev-parse HEAD`
   - `git status --porcelain`

## Root cause classification
- Memory pipeline down (MCP unreachable / tool failures)
- Human process gap (no checkpoint / no proof)
- Canon conflict (second board / stale doc treated as canon)
- Tooling gap (no automation / missing drift guard)

## Preventative actions (choose smallest effective)
- Add or tighten a skill/guard script.
- Add a timer or a restore drill step.
- Clarify canon in one file (do not create a second canon).

