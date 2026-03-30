# OneContext: Hard Rules and Operating Model (2026-02-22)

## Purpose
This document defines strict usage rules for OneContext in QIKI_DTMP to keep retrieval reliable, reduce noise, and avoid false context from large raw logs.

## Proven Facts From Audit
1. Core DB is healthy (`integrity_check=ok`), schema is valid, and `turn_content` exists.
2. Worker backlog existed and worker was stopped; after worker start, queued jobs moved to done.
3. `watcher session list` can show duplicate discovered sessions with the same `session_id` from multiple `codex_homes/*` paths.
4. Content payload is very large (`turn_content` total ~5.8 MB for 36 turns, max turn >2 MB), so unscoped content search can return heavy noise.
5. In sandboxed environments, `onecontext search -t content` may fail with `unable to open database file` due to filesystem write restrictions outside allowed roots. Running outside sandbox works.

## Principles
1. Retrieval-first, not dump-first: use metadata-level search before opening raw content.
2. Scope aggressively: always narrow by session/turn before content search.
3. Determinism over breadth: fixed windows and explicit IDs instead of global fuzzy scans.
4. Health before trust: if worker is down or queue has `queued/processing` stuck jobs, context is incomplete.
5. Noise is expected in raw content; summaries/titles are primary signal.

## Non-Negotiable Query Rules
1. Start with:
```bash
scripts/onecontext_safe.sh context show
```
2. Then run broad search only on turn/session:
```bash
scripts/onecontext_safe.sh search "<regex>" -t session --count
scripts/onecontext_safe.sh search "<regex>" -t turn --count
scripts/onecontext_safe.sh search "<regex>" -t turn --from 0 --to 30
```
3. Only after selecting turn IDs, run content search scoped by turns:
```bash
scripts/onecontext_safe.sh search "<regex>" -t content --turns <turn1,turn2> --from 0 --to 20 --snippet-context 120
```
4. Never run unscoped `-t content` on broad regex in normal flow.
5. For large investigations, page windows explicitly (`--from/--to`) and record the window used.

## Operational Health Gate
Run before critical use:
```bash
scripts/onecontext_safe.sh watcher status
scripts/onecontext_safe.sh worker status
```

Pass conditions:
1. `Watcher: Running`
2. `Worker: Running`
3. Jobs queue has no stale `queued/processing` growth

If worker is stopped:
```bash
scripts/onecontext_safe.sh worker start
```

If job state is inconsistent:
```bash
scripts/onecontext_safe.sh worker repair
```

## Mandatory Runtime Guard
For stability in restricted/sandboxed environments, run OneContext with:
```bash
SQLITE_TMPDIR=/tmp
```
Project wrapper:
```bash
scripts/onecontext_safe.sh <command...>
```
Example:
```bash
scripts/onecontext_safe.sh search "database" -t content --limit 1
```

## Anti-Noise Policy
1. Prefer `-t turn` for decision discovery; use `-t content` only for evidence extraction.
2. Ignore giant command-output blobs unless directly relevant.
3. Treat repeated discovered sessions with same `session_id` as discovery-level duplication, not independent history.
4. For reports to humans: synthesize findings; do not paste raw OneContext output unless explicitly requested.

## Troubleshooting
### Symptom: `unable to open database file`
Checklist:
1. Confirm DB path exists in `scripts/onecontext_safe.sh version`.
2. Check worker/watcher status.
3. If running inside sandbox/isolated executor, rerun command outside sandbox permissions.
4. Retry with narrow scope (`-t turn`, then `-t content --turns ...`).

## Definition of Done (OneContext-ready)
1. Health gate passes (`watcher` and `worker` running).
2. Search works in broad-to-deep flow.
3. Required decision evidence is retrievable via scoped `--turns` queries.
4. No reliance on unscoped raw-content scans.

## Operational References
1. Runbook: `docs/operations/ONECONTEXT_RUNBOOK.md`
2. Baseline snapshot: `docs/operations/ONECONTEXT_BASELINE_2026-02-22.md`
3. Automated acceptance: `scripts/onecontext_acceptance.sh`
