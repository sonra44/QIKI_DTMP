# Repository Guidelines

## Project Structure & Module Organization

- `src/qiki/` — main Python codebase (shared models, services, infrastructure).
- `src/qiki/services/operator_console/` — ORION (Textual TUI “Shell OS”) entrypoints and UI code.
- `docs/` — design docs and system references (e.g. `docs/design/operator_console/`).
- `proto/`, `protos/` — protobuf sources; `generated/` may contain generated stubs (often ignored in git).
- `docker-compose*.yml`, `Dockerfile*` — runtime stacks and local/dev orchestration.
- `tests/` and service-local `*/tests/` — automated tests.

## Build, Test, and Development Commands

- Start Phase1 + operator console: `docker compose -f docker-compose.phase1.yml -f docker-compose.operator.yml up -d --build operator-console`
- Start Shell OS overlay: `docker compose -f docker-compose.phase1.yml -f docker-compose.shell_os.yml up -d --build shell-os`
- Run operator console tests: `pytest -q src/qiki/services/operator_console/tests`
- Regenerate protobuf stubs (when needed): `bash tools/gen_protos.sh`

## Coding Style & Naming Conventions

- Python: 4-space indentation, type hints where practical.
- Prefer clear, descriptive identifiers; avoid UI abbreviations in user-facing strings.
- Tools: `ruff.toml` is present; run `ruff`/`mypy` when applicable to the area you touch.

## Testing Guidelines

- Add tests close to the code under `src/qiki/services/<service>/tests/` when changing service behavior.
- Prefer small deterministic tests over long integration suites.

## Commit & Pull Request Guidelines

- Commits follow a pragmatic style seen in history (e.g. `Fix ...`, `Align ...`, `feat: ...`).
- Keep commits focused; include a short rationale in the message if the change is non-obvious.

## Agent-Specific Instructions

- “ПРОЧТИ ЭТО” bootstrap: follow `~/MEMORI/ПРОЧТИ_ЭТО_QIKI_DTMP.md` (sovereign-memory workflow).
- Save durable decisions as `core` memory; session state / next steps as `episodic`.
