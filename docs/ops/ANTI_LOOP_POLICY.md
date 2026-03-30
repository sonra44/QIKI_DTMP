# Anti-Loop Policy (QIKI_DTMP)

## Goal
Prevent development loops where we produce evidence/checklists without a clear operator-facing outcome.

## Hard rules

1. One cycle MUST produce one new operator scenario.
2. Product changes MUST include a task dossier (`TASKS/TASK_*.md`) with:
   - `## Operator Scenario (visible outcome)`
   - `## Reproduction Command`
   - `## Before / After`
   - `## Impact Metric`
3. Missing these sections blocks the gate.

## Enforcement

- Gate script: `scripts/ops/anti_loop_gate.sh`
- Integrated into: `scripts/quality_gate_docker.sh` (`QUALITY_GATE_RUN_ANTI_LOOP=1` by default)

## Churn guard

- If `main_orion.py` churn exceeds `ANTILOOP_MAX_MAIN_ORION_COMMITS` (default `5`) in one range, gate fails in strict mode (`ANTILOOP_STRICT=1`).

## Notes

- For non-product maintenance changes, anti-loop gate allows pass.
- PR templates must include operator-visible delta and impact metric.
