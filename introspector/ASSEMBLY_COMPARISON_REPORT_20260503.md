# Assembly comparison report — 2026-05-03

## Verdict

The correct final assembly must be based on `introspector_tui_operator_datatable_20260503.zip`, not on the locally available `introspector_final_handoff_20260503.zip`.

Reason: the local `final_handoff` archive contains the handoff status file, but its TUI code is older than the DataTable increment. In particular, it lacks the DataTable-backed overview table wiring and helper functions that are present in `introspector_tui_operator_datatable_20260503.zip`.

## Compared inputs

- `introspector_source_clean_20260503T015146Z.zip`
- `introspector_tui_operator_release_20260503.zip`
- `introspector_tui_operator_state_20260503.zip`
- `introspector_tui_operator_visual_20260503.zip`
- `introspector_tui_operator_polish_20260503.zip`
- `introspector_tui_operator_datatable_20260503.zip`
- `introspector_final_handoff_20260503.zip`
- `introspector_unified_release_20260502_FINAL.zip`

## Key comparison result

`introspector_tui_operator_datatable_20260503.zip` has 117 files.
`introspector_final_handoff_20260503.zip` has 116 files.

File-list difference:

- Present only in DataTable archive:
  - `docs/TUI_GUIDE.md`
  - `TUI_OPERATOR_DATATABLE_REPORT_20260503.md`
- Present only in local final handoff archive:
  - `FINAL_HANDOFF_STATUS_20260503.md`

Common files that differ:

- `src/project_introspector/tui_app.py`
- `src/project_introspector/tui_render.py`
- `src/project_introspector/tui_table_model.py`
- `src/project_introspector/tui_text.py`
- `tests/test_tui_table_model.py`

The differences show that the local handoff archive rolls back the DataTable increment. Therefore the correct merge is:

1. Use DataTable archive as the code base.
2. Add handoff/status documentation from the handoff archive.
3. Add a release gate script and testing handoff documentation.
4. Verify the result with compile, pytest, offline run, validation, CLI run, and zip integrity.

## Changes added in this final correct assembly

Added:

- `docs/TESTING_HANDOFF.md`
- `scripts/release_test_gate.sh`
- `tests/test_release_test_gate.py`
- `FINAL_HANDOFF_STATUS_20260503.md`
- `FINAL_RELEASE_GATE_LOG_20260503.txt`
- `ASSEMBLY_COMPARISON_REPORT_20260503.md`
- `FINAL_CORRECT_ASSEMBLY_STATUS_20260503.md`

Preserved from DataTable archive:

- `docs/TUI_GUIDE.md`
- `TUI_OPERATOR_DATATABLE_REPORT_20260503.md`
- DataTable-backed overview table in `tui_app.py`
- table filters and widget-ready helpers in `tui_table_model.py`
- DataTable-related TUI text keys in `tui_text.py`
- DataTable tests in `tests/test_tui_table_model.py`

## Acceptance performed

- `python -m compileall -q src analyzer scripts tests` — OK.
- `python -m pytest -q tests` with plugin autoload disabled — `126 passed, 3 skipped`.
- `bash scripts/release_test_gate.sh` — reached `RELEASE_TEST_GATE_OK`.
- Direct offline run — wrote `run_result.json` with `completed_with_limits`.
- Direct validator — `OK: run_result.json matches run contract`.
- CLI offline run — wrote `run_result.json` with `completed_with_limits`.
- CLI validator — `OK: run_result.json matches run contract`.
- tmux smoke — skipped because tmux is not installed.

## Remaining caveats

This is ready for controlled testing, not a claim of fully verified live production behavior.

Remaining live-environment checks:

- TUI live path with Textual extra installed.
- Provider live path with real credentials.
- tmux smoke in an environment where tmux is installed.
