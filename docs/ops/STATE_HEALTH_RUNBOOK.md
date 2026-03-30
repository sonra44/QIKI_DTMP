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

Important boundary for `qiki-bios-phase1`:
- container `healthy` means the HTTP process answers `/healthz`;
- it does not prove `q-sim-service` readiness beyond whatever the last BIOS payload observed;
- it does not prove NATS publishability;
- it does not prove that `/bios/status` is freshly recomputed at this exact moment.

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
- `mcp__serena__search_for_pattern(relative_path="src/qiki/services/operator_console/main_orion_v.py", substring_pattern="OrionVApp")`

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
curl -sf http://127.0.0.1:8080/healthz
curl -sf http://127.0.0.1:8080/bios/status
docker exec -i qiki-operator-console python - <<'PY'
import asyncio
import qiki.services.operator_console.main_orion_v as main_orion_v
async def main():
    app = main_orion_v.OrionVApp()
    async with app.run_test(size=(140, 44)) as pilot:
        app.action_show_screen("radar")
        await pilot.pause()
asyncio.run(main())
print("OK: orion smoke minimal")
PY
```

Interpretation:
- `GET /healthz` is process liveness only.
- `GET /bios/status` is the support-tier readiness/freshness surface to inspect when BIOS semantics matter.
- In canonical contour with `BIOS_PUBLISH_ENABLED=1`, HTTP freshness is bounded by the next publisher refresh interval (`BIOS_PUBLISH_INTERVAL_SEC`, default `5s`) because `/bios/status` serves cached `_last_payload`.
- With publishing disabled, `/bios/status` may stay sticky until `POST /bios/reload` or another recomputation path clears/rebuilds `_last_payload`.

## 5) Decision policy: reindex Serena or not
- Reindex **only if** symbol tools show degraded behavior (missed symbols/references, repeated index errors).
- If symbol tools are stable and fast, keep current index.

## 6) End-of-loop memory proof
Save:
- `STATUS` (episodic), `TODO_NEXT` (episodic), `DECISIONS` (core if long-lived).

Immediately recall by tags and capture returned IDs in the session report.

## 7) Anti-loop gate (hard rule)
```bash
bash scripts/ops/anti_loop_gate.sh
```

Expected:
- Product changes have a task dossier with visible operator scenario + before/after + impact metric.
- No silent "evidence-only" cycle for product code.
