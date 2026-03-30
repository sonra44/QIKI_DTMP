# QIKI_DTMP

Digital-twin simulation platform with an operator TUI (ORION) and simulation-truth telemetry pipeline.  
Платформа цифрового двойника с операторским TUI (ORION) и конвейером телеметрии от симуляции.

## What This Is / Что Это

EN:
- `q-sim-service` generates world state and publishes telemetry/radar truth.
- ORION (`operator-console`) renders operational state for humans.
- No-mocks policy: if data is missing, UI must show honest `N/A/—`.

RU:
- `q-sim-service` генерирует состояние мира и публикует телеметрию/радар.
- ORION (`operator-console`) показывает операторское состояние в реальном времени.
- Политика no-mocks: если данных нет, UI обязан показать честное `N/A/—`.

## Architecture at a Glance / Архитектура Кратко

Core components:
- `qiki-nats-phase1` (NATS + JetStream)
- `q-sim-service` (simulation truth)
- `qiki-faststream-bridge-phase1` (routing/normalization)
- `qiki-operator-console` (ORION TUI)
- `qiki-dev-phase1` (tests, tooling, development)

Key path:
1. Sim publishes truth -> NATS/JetStream.
2. Bridge normalizes and routes messages.
3. ORION renders semantic operator view.
4. Operator commands return to simulation loop.

## Quick Start (Docker-first) / Быстрый Старт (Docker-first)

```bash
# 1) Start Phase1
docker compose -f docker-compose.phase1.yml up -d --build
docker compose -f docker-compose.phase1.yml ps

# 2) Start ORION console
docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up operator-console
```

Health checks:

```bash
curl -sf http://localhost:8222/healthz
bash scripts/quality_gate_docker.sh
```

If protobuf stubs are missing:

```bash
docker compose -f docker-compose.phase1.yml run --rm qiki-dev bash -lc "bash tools/gen_protos.sh"
```

## Current Workflow Contract / Контракт Рабочего Процесса

- One task = one branch = one PR.
- Branch format: `task-<4+digits>-<slug>`.
- Merge to `main` only after:
  - required checks are green: `load`, `Sourcery review`, `CodeRabbit`
  - review feedback is addressed
  - PR conversation is resolved
  - `@codex review` is requested and processed
- Direct push to `main` is not part of normal flow.

Details: `CONTRIBUTING.md`, `docs/operations/GIT_BRANCH_POLICY.md`.

## Source of Truth Links / Где Истина

- Docs index: `docs/INDEX.md`
- Design canon entrypoint: `docs/design/canon/INDEX.md`
- Architecture: `docs/ARCHITECTURE.md`
- Task dossiers: `TASKS/00_INDEX.md`
- Operator semantics: `docs/design/operator_console/SIMULATION_CONTROL_CONTRACT.md`

## For Reviewers and LLMs / Для Ревьюеров и LLM

Minimal verification path:
1. Read this README and `CONTRIBUTING.md`.
2. Run Phase1 and ORION using commands above.
3. Run `bash scripts/quality_gate_docker.sh`.
4. Run `bash scripts/qiki_drift_audit.sh --strict` if the slice touched board, dossier, canon, or reference/status docs.
4. Validate claims in relevant `TASKS/TASK_*.md` dossier.
