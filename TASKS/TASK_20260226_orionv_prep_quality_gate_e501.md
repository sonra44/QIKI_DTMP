# TASK: ORION V prep + quality gate E501 cleanup

Status: completed  
Date: 2026-02-26  
Branch: ORION

## Operator Scenario (visible outcome)
Operator starts Phase1 stack and can run either legacy ORION or ORION V.  
ORION V launches without crashing and shows NATS connectivity state in header/cockpit.

## Reproduction Command
```bash
ruff check src tests --select E501
bash scripts/quality_gate_docker.sh

docker compose -f docker-compose.phase1.yml up -d --build
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml -f docker-compose.operator_orionv.yml up -d --build operator-console
docker attach qiki-operator-console
```

## Before / After
Before:
- `scripts/quality_gate_docker.sh` failed on `ruff E501`.
- ORION V entrypoint/skeleton were absent from main repo.

After:
- `ruff E501` violations resolved for tracked code paths.
- ORION V bootstrap path exists (`main_orion_v.py`, `orion_v/`, overlay compose, quickstart doc).
- Operator can run ORION V in parallel with legacy path.

## Impact Metric
- `ruff check src tests --select E501`: fail -> pass.
- `scripts/quality_gate_docker.sh`: expected pass after dossier and lint cleanup.
- ORION V startup smoke: operator-console container running with ORION V command and visible NATS state label.

## Final verification (2026-03-01)
- Command: `bash scripts/quality_gate_docker.sh`
- Result: `exit 0`
- Tail evidence:
  - `[anti-loop] Dossier check passed: TASKS/TASK_20260226_orion_v_levels_overlay_and_bounded_events.md`
  - `[anti-loop] OK`
  - `[quality-gate] OK`
