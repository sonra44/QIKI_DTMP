# QIKI_DTMP Agent Guidelines

This file is consumed by agentic coding assistants. Keep instructions practical, reproducible, and Docker-first.

## Project Structure (High Signal)

- `src/qiki/` — primary Python package (shared models, converters, services).
- `src/qiki/services/operator_console/` — ORION Operator Console (Textual TUI).
- `generated/` — generated protobuf stubs (`*_pb2.py`), required by runtime and tests.
- `protos/`, `proto/`, `proto_extensions/` — protobuf sources and extensions.
- `docs/design/operator_console/` — ORION UX + runbook + validation checklist.
- `docs/design/hardware_and_physics/` — bot “physics” / form-factor source of truth.
- `docker-compose*.yml`, `Dockerfile*` — Docker-first orchestration (dev uses Python 3.12).
- `scripts/`, `tools/` — quality gate, smoke tests, proto generation, helper utilities.
- `tests/` — unit/integration/UI tests.

## Build / Lint / Test (Docker-first)

### Start / Run

- Start default stack: `docker compose up -d --build`
- Phase1 + ORION Operator Console:
  - Background: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
  - Foreground TUI: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up operator-console`
  - Attach to TUI: `docker attach qiki-operator-console` (detach: `Ctrl+P` then `Ctrl+Q`)

Logs / status:
- Status: `docker compose -f docker-compose.phase1.yml ps`
- Tail logs: `docker compose -f docker-compose.phase1.yml logs -f --tail=200 <service>`

### Quality Gate (preferred)

- Run default gate: `bash scripts/quality_gate_docker.sh`
- Useful toggles:
  - `QUALITY_GATE_RUFF_FORMAT_CHECK=1 bash scripts/quality_gate_docker.sh`
  - `QUALITY_GATE_RUN_INTEGRATION=1 bash scripts/quality_gate_docker.sh`
  - `QUALITY_GATE_RUN_MYPY=1 bash scripts/quality_gate_docker.sh`
  - `QUALITY_GATE_SCOPE=src/qiki/services/operator_console bash scripts/quality_gate_docker.sh`

### Ruff (lint/format)

- Lint all: `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check .`
- Lint one file: `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff check path/to/file.py`
- Format (check): `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff format --check .`
- Format (write): `docker compose -f docker-compose.phase1.yml exec -T qiki-dev ruff format .`

Ruff config: `ruff.toml` (line length 120; rules include `TID252` so prefer absolute imports / avoid relative imports).

### Pytest (unit + fast integration selection)

Important: `pytest.ini` uses `addopts = -q -m "not integration"`.

- Run all non-integration tests: `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q`
- Run a single test file: `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_foo.py`
- Run a single test function: `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q tests/unit/test_foo.py::test_bar`
- Run by keyword: `docker compose -f docker-compose.phase1.yml exec -T qiki-dev pytest -q -k "keyword"`

Integration tests (marked `@pytest.mark.integration`) must override addopts:

- Preferred wrapper:
  - Folder: `./scripts/run_integration_tests_docker.sh tests/integration`
  - Single file: `./scripts/run_integration_tests_docker.sh tests/integration/test_radar_flow.py`
  - Single test: `./scripts/run_integration_tests_docker.sh tests/integration/test_radar_flow.py::test_name`

Smoke tests:
- Stage 0 smoke: `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash /workspace/scripts/smoke_test.sh`

### Mypy (optional)

- Run (when enabled): `docker compose -f docker-compose.phase1.yml exec -T qiki-dev mypy --config-file mypy.ini src`

Note: `mypy.ini` ignores some services (`q_core_agent`, `q_sim_service`, `faststream_bridge`) to keep signal-to-noise reasonable.

### Protobuf Stubs

- Generate stubs (preferred): `docker compose -f docker-compose.phase1.yml run --rm qiki-dev bash -lc "bash tools/gen_protos.sh"`
- Output goes to: `generated/`

## ORION Operator Console (TUI) Rules

- UI strings must be bilingual `EN/RU` with no spaces around `/`.
- No-mocks: missing data must render as `N/A/—`; do not invent zeros.
- No auto-actions: destructive/irreversible commands require explicit operator confirmation.
- Mechanical overrides can exist but should be hidden by default and gated by an explicit env flag.

Useful ORION env flags:
- `OPERATOR_CONSOLE_DEV_DOCKING_COMMANDS=1` (enable dev-only mechanical docking CLI commands)
- `ORION_TELEMETRY_DICTIONARY_PATH=docs/design/operator_console/TELEMETRY_DICTIONARY.yaml` (override dictionary path)

Telemetry semantics are canonical and dictionary-driven:

- Canonical dictionary: `docs/design/operator_console/TELEMETRY_DICTIONARY.yaml`
- Drift guards:
  - `tests/unit/test_telemetry_dictionary.py` validates dictionary paths against real payloads built by `q_sim_service`.
  - It also validates that ORION Inspector `Source keys` are covered by the dictionary.
- Live audit (real NATS):
  - `docker compose -f docker-compose.phase1.yml exec -T qiki-dev bash -lc "NATS_URL=nats://nats:4222 python tools/telemetry_smoke.py --audit-dictionary --subsystems power,thermal,sensors,propulsion,comms,system,docking"`

ORION TUI specialist playbook:
- See `docs/agents/orion_tui_agent.md` (process/invariants/DoD).

## Python Code Style

- Formatting: 4-space indentation; max line length 120 (Ruff).
- Imports:
  - Prefer absolute imports (`from qiki...`) over relative imports.
  - Prefer `qiki.radar.*`; `radar.*` is legacy shim.
- Types:
  - Add type hints for public APIs and non-trivial logic.
  - Avoid `Any` unless you are at a boundary (JSON/NATS payloads, proto messages).
- Naming:
  - Modules/functions/vars: `snake_case`.
  - Classes: `PascalCase`.
  - Constants: `UPPER_SNAKE_CASE`.
- Error handling:
  - Don’t swallow exceptions silently; log context and re-raise or convert to a clear domain error.
  - For external I/O (NATS/gRPC/files), use timeouts and return actionable errors.
  - Prefer explicit “N/A” states to misleading defaults.

## Testing Conventions

- Tests live in `tests/unit/`, `tests/integration/`, `tests/ui/`.
- Keep tests deterministic (no sleeps unless unavoidable; prefer polling with timeouts).
- For Textual UI, prefer headless tests (`pytest-textual` / `App.run_test`) and assert on state.

## Docs / Contracts

- Operator control semantics: `docs/design/operator_console/SIMULATION_CONTROL_CONTRACT.md`
- ORION system model + data plane: `docs/design/operator_console/ORION_OS_SYSTEM.md`
- ORION canonical UX spec: `docs/design/operator_console/CANONICAL_SPEC_ORION_QIKI.md`

## Git / PR Hygiene

- Keep changes scoped; do not mix refactors with functional changes.
- If you touch telemetry/UI semantics, update `TELEMETRY_DICTIONARY.yaml` and keep `tests/unit/test_telemetry_dictionary.py` green.
- For ORION UI changes, include tmux evidence (capture-pane / screenshot) and note terminal size if layout-sensitive.

## Cursor / Copilot Rules

- No `.cursor/rules/`, `.cursorrules`, or `.github/copilot-instructions.md` were found in this repository.

## Agent Workflow Hooks

- “ПРОЧТИ ЭТО” bootstrap: follow `~/MEMORI/ПРОЧТИ_ЭТО_QIKI_DTMP.md` (sovereign-memory workflow).
- Prefer Docker-first validation before claiming something works.
- ORION hotkeys: Events live/pause toggle is `Ctrl+Y` (avoid `Ctrl+P` conflicts with tmux / `docker attach` escape).
