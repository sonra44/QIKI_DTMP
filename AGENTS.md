# Repository Guidelines

## Project Structure & Module Organization

- `src/qiki/` — primary Python package (shared models, converters, services).
- `src/qiki/services/operator_console/` — ORION Operator Console (“Shell OS” TUI on Textual).
- `generated/` — generated protobuf stubs (`*_pb2.py`), required by runtime and tests.
- `protos/`, `proto/`, `proto_extensions/` — protobuf sources and extensions.
- `docs/design/operator_console/` — ORION UX + runbook + validation checklist.
- `docs/design/hardware_and_physics/` — bot “physics” / form-factor source of truth.
- `docker-compose*.yml`, `Dockerfile*` — Docker-first orchestration.
- `scripts/`, `tools/` — smoke tests, proto generation, helper utilities.
- `tests/` — unit/integration/UI tests.

## Build, Test, and Development Commands

- Generate protobuf stubs (preferred, inside container): `docker compose -f docker-compose.phase1.yml run --rm qiki-dev bash -lc "bash tools/gen_protos.sh"`
- Start the default stack: `docker compose up -d --build`
- Start Phase1 + ORION Operator Console: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
- Run ORION interactively (foreground TUI): `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up operator-console`
- Attach to ORION TUI (if started with `-d`): `docker attach qiki-operator-console` (detach: `Ctrl+P` then `Ctrl+Q`)
- Run tests (preferred): `docker compose exec qiki-dev pytest -q tests`
- Smoke test: `docker compose exec qiki-dev bash /workspace/scripts/smoke_test.sh`

## Coding Style & Naming Conventions

- Python: 4-space indentation; use type hints where practical.
- Prefer clear, descriptive names.
- ORION UI strings: always bilingual `EN/RU` (no spaces around `/`) and avoid abbreviations in user-facing labels/values.
- Linting/typing: Ruff config in `ruff.toml` (`ruff check .`), plus `mypy.ini` where applicable.

## Testing Guidelines

- Frameworks: `pytest`, plus `pytest-asyncio` and `pytest-textual` where needed.
- Add unit tests under `tests/unit/`, integration tests under `tests/integration/`, and UI tests under `tests/ui/`.
- Keep tests deterministic; prefer small tests over long end-to-end suites.

## Commit & Pull Request Guidelines

- Commit history is mixed (Conventional Commits + free-form). For new work, prefer `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:` when practical.
- Keep PRs focused; include “what/why” + “how to run” steps.
- For TUI changes, attach a terminal capture (tmux screenshot/recording) and note the terminal size if layout-sensitive.
- If behavior changes, add/update tests and update relevant docs in `docs/`.

## Agent-Specific Instructions

- “ПРОЧТИ ЭТО” bootstrap: follow `~/MEMORI/ПРОЧТИ_ЭТО_QIKI_DTMP.md` (sovereign-memory workflow).
- Prefer Docker-first validation before claiming something works.
- ORION hotkeys: Events live/pause toggle is `Ctrl+Y` (avoid `Ctrl+P` conflicts with tmux / `docker attach` escape).
