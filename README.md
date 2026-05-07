# QIKI_DTMP

QIKI_DTMP is a space-simulation game project built around operator telemetry, radar, sensor trust, and an autonomous QIKI entity. It is not a generic dashboard or a marketing "digital twin" demo. The player does not look at an external 3D scene; the player reads the world through ORION, telemetry, radar, sensor state, command proposals, and QIKI's responses.

The hard rule is truth first. Runtime state must come from simulation, NATS/JetStream messages, service contracts, or explicit operator policy. UI text may summarize that truth, but it must not invent it.

## Product Frame

- `q-sim-service` owns simulation truth: world state, telemetry, radar contacts, sensor effects, subsystem state, and command consequences.
- QIKI is an autonomous in-world system, not a decorative chatbot. Operator access depends on protocol, legality, trust, and game-state permissions.
- ORION is the primary operator surface. It displays telemetry, radar, system status, command affordances, and consequences.
- Sensors do not collapse to fake numbers. Healthy sensors show exact data; degraded sensors show uncertainty; failed or disabled sensors state why data is absent.
- Pause and slowdown are game mechanics. Human time and machine/QIKI decision time may diverge.

## Runtime Path

Core services:

- `qiki-nats-phase1`: NATS and JetStream transport.
- `q-sim-service`: simulation truth and event source.
- `qiki-faststream-bridge-phase1`: message routing and normalization.
- `qiki-operator-console`: ORION operator console.
- `qiki-dev-phase1`: test and tooling container.

Main loop:

1. Simulation publishes truth.
2. Bridge routes and normalizes messages.
3. ORION renders an operator view.
4. Operator/QIKI commands go back through legality, execution, ack, and audit paths.

## Quick Start

Use Docker first.

```bash
docker compose -f docker-compose.phase1.yml up -d --build
docker compose -f docker-compose.phase1.yml ps
```

Start ORION:

```bash
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up operator-console
```

Run the main quality gate:

```bash
bash scripts/quality_gate_docker.sh
```

If protobuf stubs are missing:

```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev bash -lc "bash tools/gen_protos.sh"
```

## Repository Map

- `src/qiki/`: runtime services, shared models, ORION code, simulation logic, and tools.
- `tests/`: unit and integration tests.
- `docs/`: public architecture, operations, canon, and runbooks.
- `docs/design/canon/`: active design canon entrypoint and product-critical execution canons.
- `docs/design/operator_console/`: ORION operator-surface design and contracts.
- `docs/design/game/`: game/lore layer that belongs to the active product frame.
- `docs/design/hardware_and_physics/`: hardware, sensor, power, thermal, and physical-system design notes.
- `TASKS/`: task dossiers used to ground implementation work.
- `schemas/`, `protos/`, `proto_extensions/`: contracts and schemas.
- `scripts/`, `tools/`: repeatable project operations and smoke checks.

## Source Of Truth

Use this order when checking a claim:

1. Runtime code, tests, and live service evidence.
2. Current task dossier in `TASKS/`.
3. Active canon under `docs/design/canon/`.
4. Public docs and runbooks.
5. Historical notes only when explicitly marked as reference.

Start here:

- Documentation index: `docs/INDEX.md`
- Architecture: `docs/ARCHITECTURE.md`
- Canon index: `docs/design/canon/INDEX.md`
- Git policy: `docs/operations/GIT_BRANCH_POLICY.md`
- Documentation update protocol: `DOCUMENTATION_UPDATE_PROTOCOL.md`

## What Is Not Published

The public repository intentionally excludes local agent state, virtual environments, archives, generated reports, exported zip bundles, and scratch workspaces. Examples:

- `.venv/`, `.serena/`, `.qwen/`, `.codex/`, `.claude/`
- `_archive/`, `TASK_OUT/`, `tmp/`, `introspector/`
- generated analysis directories and one-off report dumps
- local package exports such as `*.zip`

These files may exist on a developer machine, but they are not part of the project source tree.

## Workflow

- One task should have one branch and one PR.
- `main` is protected.
- Use Docker-first verification before review.
- Keep code, docs, canon, and task dossiers synchronized when behavior changes.
- Do not commit secrets, local credentials, shell history, provider keys, or agent memory.
