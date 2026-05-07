# TUI_OPERATOR_PLAN

Generated: 2026-05-03

## Completed in this pass

- New-base audit against the previous unified release.
- New-base acceptance and direct script bootstrap fix.
- Provider negative-path test hardening.
- Missing artifact validator test hardening.
- Malformed LLM response hardening.
- Scanner edge-case hardening.
- TUI smoke baseline via existing tests; direct tmux smoke skipped because tmux is unavailable.
- Initial operator-state building blocks:
  - `artifact_freshness.py`
  - `artifact_resolver.py`
  - `operator_state.py`

## Completed in the operator-state wiring continuation

- Wired `tui_client.py` artifact loading through `artifact_resolver.py`.
- Replaced direct freshness reasoning in render paths with `artifact_freshness.py` primitives where practical.
- Extended `operator_state.py` with run-directory discovery and analyzer-backed input support.
- Adapted TUI dashboard/status rendering to consume `OperatorState` incrementally.

## Next recommended tasks

1. Convert module detail / inspector rendering to consume `OperatorState` module rows and evidence sections.
2. Add visual dashboard health cards instead of plain text dashboard lines.
3. Add module-table filters for stale, degraded, missing enrichment, routes and env/config.
4. Add inspector panel evidence sections for routes, env vars, CLI options, Pydantic models and class attributes.
5. Add structured action log/progress panel.
6. Expand hotkeys and update `docs/TUI_GUIDE.md`.
7. Re-run tmux smoke in an environment with tmux and Textual installed.
