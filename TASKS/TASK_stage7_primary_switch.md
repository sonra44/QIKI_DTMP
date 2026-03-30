# TASK: Stage 7.1 + 7.2 + 7.3 — ORION V default switch, legacy isolation, short stability

## Status

- `done` (2026-02-26)

## Scope

1. Make ORION V default console entrypoint.
2. Isolate legacy runtime behind explicit profile/override.
3. Run short stability verification (restart/burst/health/quality gate).

## Changes

- Default operator command switched to ORION V:
  - `docker-compose.operator.yml`: `command: python main_orion_v.py`
  - `docker-compose.yml`: `command: python main_orion_v.py`
- Root compose operator service aligned with ORION V runtime imports:
  - added `QIKI_REPO_ROOT=/workspace`
  - added `PYTHONPATH=/workspace/src:/workspace/generated:/app`
  - mounted `./src`, `./generated`, `./docs`, `./scripts`, `./tools`, `./config`
- Added isolated legacy overlay:
  - `docker-compose.operator_legacy.yml`
  - `operator-console.command: python -m qiki.services.operator_console.legacy.main_orion`
  - `profiles: ["legacy"]`
- Added legacy package namespace:
  - `src/qiki/services/operator_console/legacy/__init__.py`
  - `src/qiki/services/operator_console/legacy/main_orion.py`
- ORION V entrypoint made dual-context safe (`/app` and package mode):
  - `src/qiki/services/operator_console/main_orion_v.py` with import fallback
- Doc sync:
  - `docs/CUTOVER_PLAN.md`
  - `docs/ORION_V_RUNBOOK.md`
  - `docs/ORION_V_QUICKSTART.md`

## Evidence

### E1: Default compose boots ORION V without extra overlays

```bash
docker compose up -d --build operator-console
docker compose ps -a | rg -n "operator-console|qiki-operator-console" -N
docker logs --tail=120 qiki-operator-console | rg -n "ORION V|NATS:" | tail -n 20
```

Observed:
- `qiki-operator-console ... Up ...`
- ORION log lines include `ORION V | F1 Cockpit | NATS: Connected`.

### E2: Legacy isolated fallback works only with explicit profile/override

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_legacy.yml --profile legacy up -d --build operator-console
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_legacy.yml --profile legacy ps
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_legacy.yml --profile legacy down -v
```

Observed:
- legacy command path starts only in profile mode;
- default ORION V compose path does not require legacy files.

### E3: Short stability verification

#### Reconnect loop

```bash
for i in 1 2 3 4 5; do docker restart qiki-nats-phase1 >/dev/null; sleep 3; done
```

Observed:
- stack remains healthy (`operator-console`, `nats`, `q-sim-service` up).

#### Burst load

3 bursts to `qiki.events.v1.audit`, each 2500 events (`total=7500`).

Observed:
- no service crash/restart loop;
- ORION V event counter grows and bounded store remains capped at configured limit.

#### Canonical operator actions subject probe

Observed:
- publish/receive on `qiki.events.v1.operator.actions` succeeded (`operator_actions_seen 1`).

### E4: Quality gate

```bash
bash scripts/quality_gate_docker.sh
```

Observed:
- `[quality-gate] OK`

## DoD mapping

- ORION V starts by default entrypoint: `yes`
- Legacy not auto-started in default operator path: `yes`
- Legacy available only via explicit profile/override: `yes`
- NATS connect + health + reconnect smoke: `yes`
- Short stability (restarts + bursts + no crash): `yes`
- Quality gate: `yes`

## Notes

- Legacy code is mirrored under `operator_console/legacy/` for isolation and explicit profile runtime.
- Compatibility mirror of `main_orion.py` is kept to avoid breaking existing tests/tooling paths during transition.
