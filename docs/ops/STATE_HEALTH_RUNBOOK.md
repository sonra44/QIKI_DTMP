# State Health Runbook (QIKI_DTMP)

## Scope
- Sovereign Memory health.
- Serena readiness (project config + symbol tooling viability).
- Docker hygiene without breaking running stack.

## 1) Preflight
```bash
git status -sb
git rev-list --left-right --count origin/main...main
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps
```

Expected:
- `main` is synchronized (`0 0`) or divergence is explicitly known.
- Core services (`qiki-operator-console`, `qiki-nats-phase1`, `qiki-sim-phase1`, `qiki-bios-phase1`) are `healthy`.

## 2) Memory + Serena health
```bash
bash scripts/ops/health_memory_serena.sh
```

Expected:
- `qiki_sovmem_health.sh` checks pass.
- `.serena/project.yml` exists.
- `.serena/memories` exists.

Manual MCP confirmations (from agent session):
- `mcp__sovereign-memory__recall_by_tags(project="QIKI_DTMP", topic="STATUS|TODO_NEXT|DECISIONS")`
- `mcp__serena__find_symbol(name_path_pattern="OrionApp", relative_path="src/qiki/services/operator_console/main_orion.py")`

## 3) Docker hygiene
Safe (default):
```bash
bash scripts/ops/docker_hygiene.sh safe
```

Deep (maintenance window only):
```bash
bash scripts/ops/docker_hygiene.sh deep --confirm-deep
```

Notes:
- `safe` mode prunes dangling images and old builder cache (`BUILDER_UNTIL`, default `168h`).
- `deep` mode removes unused images, containers, networks, and volumes.

## 4) Post-check
```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml ps
docker exec -i qiki-operator-console python - <<'PY'
import asyncio
import qiki.services.operator_console.main_orion as main_orion
async def main():
    app = main_orion.OrionApp()
    async with app.run_test(size=(140, 44)) as pilot:
        app.action_show_screen("radar")
        await pilot.pause()
asyncio.run(main())
print("OK: orion smoke minimal")
PY
```

## 5) Decision policy: reindex Serena or not
- Reindex **only if** symbol tools show degraded behavior (missed symbols/references, repeated index errors).
- If symbol tools are stable and fast, keep current index.

## 6) End-of-loop memory proof
Save:
- `STATUS` (episodic), `TODO_NEXT` (episodic), `DECISIONS` (core if long-lived).

Immediately recall by tags and capture returned IDs in the session report.
