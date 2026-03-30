# ONECONTEXT Baseline Report

Date: 2026-02-22
Project: `QIKI_DTMP`

## Runtime
1. Watcher status: `Running` (PID `243360`)
2. Worker status: `Running` (PID `249238`)
3. Worker jobs: `done: 3`, no active turn jobs

## Version and DB Routing
1. Package version: `0.8.3`
2. Schema version (code/db): `V28/V28`
3. Configured DB path: `.onecontext/aline.db` (repo-root relative; environment-specific absolute path omitted)

## Database Health
1. `PRAGMA integrity_check = ok`
2. `sessions = 1`
3. `turns = 45`
4. `turn_content = 45`

## Acceptance
Script: `scripts/onecontext_acceptance.sh`
Result: `ACCEPTANCE_OK` (all checks passed, including 10x content search reliability)
