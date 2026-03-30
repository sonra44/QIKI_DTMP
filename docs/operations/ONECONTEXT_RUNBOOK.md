# ONECONTEXT Runbook (QIKI_DTMP)

Date: 2026-02-22

## Scope
Operational runbook for OneContext in this repository only.

Hard rules:
1. Run OneContext only via `scripts/onecontext_safe.sh`.
2. Keep project-local DB path: `.onecontext/aline.db` (repo-root relative).
3. Acceptance script DB policy is configurable via `EXPECTED_DB_PATH` (default: `<repo>/.onecontext/aline.db`).
4. Never commit runtime data from `.onecontext/`.

Example override for non-default workspace root:
```bash
EXPECTED_DB_PATH="$HOME/QIKI_DTMP/.onecontext/aline.db" scripts/onecontext_acceptance.sh
```

## Start-of-Day Procedure
1. Verify status:
```bash
scripts/onecontext_safe.sh watcher status
scripts/onecontext_safe.sh worker status
```
2. Verify context routing:
```bash
scripts/onecontext_safe.sh context show
```
3. Quick content smoke:
```bash
scripts/onecontext_safe.sh search "database" -t content --limit 1 --snippet-context 40
```

Pass condition:
1. Watcher is `Running`.
2. Worker is `Running`.
3. Content search returns snippets without `unable to open database file`.

## Incident Procedure
Symptom: `unable to open database file` or queue stuck.

1. Check status:
```bash
scripts/onecontext_safe.sh watcher status
scripts/onecontext_safe.sh worker status
```
2. Restart worker:
```bash
scripts/onecontext_safe.sh worker fresh
```
3. If still unstable, restart watcher:
```bash
scripts/onecontext_safe.sh watcher fresh
```
4. Retry smoke:
```bash
scripts/onecontext_safe.sh search "database" -t content --limit 1 --snippet-context 40
```
5. If queue shows stale processing, run:
```bash
scripts/onecontext_safe.sh worker repair
```

## Pre-Development Gate
Before switching back to feature work:
1. `watcher status` is running.
2. `worker status` is running.
3. Worker jobs are not accumulating in `queued/processing`.
4. Content search smoke is green.

If all checks pass, proceed to development tasks.
