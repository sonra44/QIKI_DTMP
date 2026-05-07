# QIKI_DTMP Documentation Index

This index points only to documentation kept in the clean public source tree.
Local archives, generated reports, agent memory, and scratch workspaces are not
part of this published documentation set.

## Read First

1. `README.md` - product frame, runtime path, quick start, and source-of-truth rules.
2. `GITHUB_RESEARCH_GUIDE.md` - public orientation guide for external researchers.
3. `docs/ARCHITECTURE.md` - services, dataflow, health, and operational topology.
4. `docs/design/canon/INDEX.md` - active design canon entrypoint.
5. `docs/CONTRACT_POLICY.md` - contract evolution rules for proto, NATS, and API surfaces.
6. `docs/operator_console/REAL_DATA_MATRIX.md` - what ORION displays and where values come from.

## Product And Canon

- `docs/NEW_QIKI_PLATFORM_DESIGN.md` - product direction and operating principles.
- `docs/design/game/` - game layer, lore, intent, and sector notes.
- `docs/design/hardware_and_physics/` - physical-system, sensor, power, thermal, and hardware notes.
- `docs/design/q-core-agent/` - QIKI core-agent design notes.
- `docs/design/operator_console/` - ORION operator-console contracts and interaction design.
- `docs/design/canon/ADR/` - architecture and design decisions.

## Runtime And Operations

- `docs/ORION_V_QUICKSTART.md`
- `docs/ORION_V_RUNBOOK.md`
- `docs/ORION_V_HARDWARE_VIEW_MODEL.md`
- `docs/operations/GIT_BRANCH_POLICY.md`
- `docs/ops/`
- `docs/asyncapi/`

## Tasks

- `TASKS/00_INDEX.md` is the task dossier entrypoint.
- Current implementation claims should be checked against the relevant `TASKS/TASK_*.md` file.
- Historical task files are reference material, not automatic current truth.

## Trust Order

Use this order when a claim conflicts:

1. Runtime code, tests, and live service evidence.
2. Current task dossier in `TASKS/`.
3. Active canon under `docs/design/canon/`.
4. Public docs and runbooks.
5. Historical notes and local memory.
