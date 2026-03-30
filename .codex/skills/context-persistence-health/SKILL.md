---
name: context-persistence-health
description: Hard evidence check that agent context will survive session restarts (SovMem smoke + backups + systemd timer install status + cron drift warning).
---

# Context Persistence — Health (QIKI_DTMP)

## Goal
Be radically confident that context will not be lost across sessions:
- MCP memory is alive (smoke)
- backups exist and are fresh
- systemd timer is installed + active (single scheduler source of truth)
- cron is not duplicating memory jobs

## Procedure (single best path)

1) Run the health script:

```bash
bash QIKI_DTMP/scripts/qiki_context_persistence_health.sh --strict
```

2) If it warns about missing/disabled timers, install them (canon):

```bash
bash QIKI_DTMP/scripts/install_context_timers.sh
```

3) If it warns about cron duplicates, remove cron jobs and keep systemd as the only scheduler.

## Evidence
- Keep the output in the current session `STATUS` memory (SovMem) and include the latest `git rev-parse HEAD`.

